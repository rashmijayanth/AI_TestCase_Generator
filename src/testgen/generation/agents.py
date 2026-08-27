"""The seven agents from DESIGN.md §3, as LangGraph node functions.

Each node takes `(state, *, deps)` — `deps` is bound via functools.partial when the
graph is built (see graph.py), which keeps every node a plain, directly-callable,
unit-testable function: `some_node(state, deps=fake_deps)` works with no graph
machinery involved.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel

from testgen.generation.llm import content_str, get_chat_model
from testgen.generation.schemas import (
    ComplianceCritiqueOutput,
    RequirementAnalysisOutput,
    SufficiencyCheckOutput,
    TestCaseGeneratorOutput,
    TestDatasetDraftOutput,
    TestPlanOutput,
)
from testgen.generation.state import GenerationState
from testgen.knowledge.embeddings import EmbeddingPort, get_embedder
from testgen.knowledge.service import search_clauses
from testgen.knowledge.vector_store import ClauseMatch, VectorStorePort, get_vector_store
from testgen.platform.config import Settings, get_settings
from testgen.platform.enums import SafetyClass, TestPriority, TestType


@dataclass
class AgentDeps:
    chat_model_factory: Callable[..., BaseChatModel]
    embedder: EmbeddingPort
    vector_store: VectorStorePort
    max_retrieval_iterations: int = 3


def build_default_deps(settings: Settings | None = None) -> AgentDeps:
    """Real production dependencies -- constructed explicitly (not as dataclass
    defaults) so building an AgentDeps for tests never accidentally requires a
    real GEMINI_API_KEY.
    """
    settings = settings or get_settings()
    return AgentDeps(
        chat_model_factory=lambda **kwargs: get_chat_model(settings, **kwargs),
        embedder=get_embedder(settings),
        vector_store=get_vector_store(settings),
    )


def _format_clauses(clauses: list[dict[str, Any]] | list[ClauseMatch]) -> str:
    lines = []
    for clause in clauses:
        if isinstance(clause, ClauseMatch):
            lines.append(f"- [{clause.standard} {clause.clause_ref}] {clause.text}")
        else:
            lines.append(f"- [{clause['standard']} {clause['clause_ref']}] {clause['text']}")
    return "\n".join(lines) if lines else "(none retrieved)"


# --- 1. Requirement Analyst -------------------------------------------------

_REQUIREMENT_ANALYST_PROMPT = """You are a requirements analyst for a medical device \
software company subject to IEC 62304.

Classify the following software requirement into an IEC 62304 software safety class:
- A: no injury or damage to health is possible
- B: non-serious injury is possible
- C: death or serious injury is possible

Requirement: {requirement_text}

Respond with the safety class ("A", "B", or "C") and a one-sentence rationale."""


def requirement_analyst_node(state: GenerationState, *, deps: AgentDeps) -> dict[str, Any]:
    llm = deps.chat_model_factory(response_schema=RequirementAnalysisOutput.model_json_schema())
    prompt = _REQUIREMENT_ANALYST_PROMPT.format(requirement_text=state["requirement_text"])
    response = llm.invoke(prompt)
    parsed = RequirementAnalysisOutput.model_validate_json(content_str(response))
    safety_class = SafetyClass(parsed.safety_class.strip().upper())
    return {"safety_class": safety_class.value, "analysis_rationale": parsed.rationale}


# --- 2. Regulatory Researcher (ReAct-style, bounded retrieval loop) --------

_SUFFICIENCY_PROMPT = """You are researching regulatory grounding for a healthcare \
software requirement.

Requirement: {requirement_text}

Clauses retrieved so far:
{clauses_summary}

Is this sufficient grounding to verify compliance for this requirement? If not, \
suggest a refined search query focusing on what's missing."""


def regulatory_researcher_node(state: GenerationState, *, deps: AgentDeps) -> dict[str, Any]:
    query = state["requirement_text"]
    all_matches: list[ClauseMatch] = []
    seen_refs: set[str] = set()

    for _ in range(deps.max_retrieval_iterations):
        matches = search_clauses(query, deps.embedder, deps.vector_store, top_k=5)
        for match in matches:
            key = f"{match.standard}:{match.clause_ref}"
            if key not in seen_refs:
                seen_refs.add(key)
                all_matches.append(match)

        llm = deps.chat_model_factory(response_schema=SufficiencyCheckOutput.model_json_schema())
        prompt = _SUFFICIENCY_PROMPT.format(
            requirement_text=state["requirement_text"], clauses_summary=_format_clauses(all_matches)
        )
        response = llm.invoke(prompt)
        check = SufficiencyCheckOutput.model_validate_json(content_str(response))

        if check.sufficient or not check.refined_query:
            break
        query = check.refined_query

    return {
        "retrieved_clauses": [
            {"standard": m.standard, "clause_ref": m.clause_ref, "text": m.text, "score": m.score}
            for m in all_matches
        ]
    }


# --- 3. Test Strategist (plan-and-execute, no tools) -----------------------

_TEST_STRATEGIST_PROMPT = """You are a test strategist for healthcare software, \
planning test coverage per IEC 62304 for the following requirement \
(safety class {safety_class}):

Requirement: {requirement_text}

Relevant regulatory grounding:
{clauses_summary}

Decide which test types are needed from this list: functional, negative, boundary, \
safety_critical, performance, security, privacy, data_driven. Apply safety_critical \
only for safety class B or C. Respond with the chosen test types and a rationale."""


def strategist_node(state: GenerationState, *, deps: AgentDeps) -> dict[str, Any]:
    llm = deps.chat_model_factory(response_schema=TestPlanOutput.model_json_schema())
    prompt = _TEST_STRATEGIST_PROMPT.format(
        safety_class=state["safety_class"],
        requirement_text=state["requirement_text"],
        clauses_summary=_format_clauses(state["retrieved_clauses"]),
    )
    response = llm.invoke(prompt)
    parsed = TestPlanOutput.model_validate_json(content_str(response))
    test_types = [TestType(t.strip().lower()) for t in parsed.test_types]
    return {
        "planned_test_types": [t.value for t in test_types],
        "strategist_rationale": parsed.rationale,
    }


# --- 4. Test Case Generator (also the retry target) ------------------------

_TEST_CASE_GENERATOR_PROMPT = """You are drafting structured test cases for a \
healthcare software requirement.

Requirement: {requirement_text}
Safety class: {safety_class}
Required test types: {test_types}

Relevant regulatory grounding:
{clauses_summary}
{feedback_section}
For each required test type, draft one structured test case: title, preconditions, \
numbered steps (action + expected per step), overall expected result, and priority \
(low, medium, high, critical). Ground each test case in the regulatory clauses \
where relevant."""


def case_generator_node(state: GenerationState, *, deps: AgentDeps) -> dict[str, Any]:
    llm = deps.chat_model_factory(response_schema=TestCaseGeneratorOutput.model_json_schema())
    feedback_section = (
        f"\nThe previous draft was rejected with this feedback -- address it:\n"
        f"{state['critic_feedback']}\n"
        if state.get("critic_feedback")
        else ""
    )
    prompt = _TEST_CASE_GENERATOR_PROMPT.format(
        requirement_text=state["requirement_text"],
        safety_class=state["safety_class"],
        test_types=", ".join(state["planned_test_types"]),
        clauses_summary=_format_clauses(state["retrieved_clauses"]),
        feedback_section=feedback_section,
    )
    response = llm.invoke(prompt)
    parsed = TestCaseGeneratorOutput.model_validate_json(content_str(response))

    draft_test_cases = [
        {
            "title": tc.title,
            "test_type": TestType(tc.test_type.strip().lower()).value,
            "preconditions": tc.preconditions,
            "steps": [step.model_dump() for step in tc.steps],
            "expected_result": tc.expected_result,
            "priority": TestPriority(tc.priority.strip().lower()).value,
        }
        for tc in parsed.test_cases
    ]
    return {"draft_test_cases": draft_test_cases, "retry_count": state["retry_count"] + 1}


# --- 5. Test Data Synthesizer ----------------------------------------------

_TEST_DATA_SYNTHESIZER_PROMPT = """You are generating synthetic test data for a \
data-driven healthcare software test case. All values must be clearly synthetic/fake \
-- do not generate anything that could be mistaken for a real patient's information \
(use placeholder-style values like "Patient_001", fictitious dates, and round \
numeric values).

Test case: {title}
Test type: {test_type}
Steps: {steps_summary}

Generate 5-10 rows of synthetic input data appropriate to this test case, as a \
named dataset."""


def data_synthesizer_node(state: GenerationState, *, deps: AgentDeps) -> dict[str, Any]:
    data_driven_cases = [
        tc for tc in state["draft_test_cases"] if tc["test_type"] == TestType.DATA_DRIVEN.value
    ]
    if not data_driven_cases:
        return {"draft_test_datasets": []}

    datasets: list[dict[str, Any]] = []
    for test_case in data_driven_cases:
        llm = deps.chat_model_factory(response_schema=TestDatasetDraftOutput.model_json_schema())
        steps_summary = "; ".join(f"{s['step_no']}. {s['action']}" for s in test_case["steps"])
        prompt = _TEST_DATA_SYNTHESIZER_PROMPT.format(
            title=test_case["title"], test_type=test_case["test_type"], steps_summary=steps_summary
        )
        response = llm.invoke(prompt)
        parsed = TestDatasetDraftOutput.model_validate_json(content_str(response))
        # phi_redacted is deliberately False here: Presidio redaction is the
        # compliance bounded context's job (Phase 5, not yet built) -- see
        # docs/PROGRESS.md for the cross-phase note on wiring it in.
        datasets.append({"name": parsed.name, "data": parsed.rows, "phi_redacted": False})

    return {"draft_test_datasets": datasets}


# --- 6. Compliance Critic (independent re-retrieval) ------------------------

_COMPLIANCE_CRITIC_PROMPT = """You are an independent compliance reviewer checking \
draft test cases against regulatory grounding for a healthcare software requirement. \
Re-retrieve your own grounding rather than trusting the drafts' claims.

Requirement (safety class {safety_class}): {requirement_text}

Your independently retrieved grounding:
{clauses_summary}

Draft test cases:
{test_cases_summary}

Do these test cases adequately verify compliance with the cited/relevant clauses? \
Reject if any required test type is missing, if a safety-critical requirement lacks \
a failure-mode test, or if a test case isn't actually grounded in the retrieved \
clauses. Provide specific, actionable feedback."""


def compliance_critic_node(state: GenerationState, *, deps: AgentDeps) -> dict[str, Any]:
    independent_matches = search_clauses(
        state["requirement_text"], deps.embedder, deps.vector_store, top_k=5
    )

    llm = deps.chat_model_factory(response_schema=ComplianceCritiqueOutput.model_json_schema())
    test_cases_summary = "\n".join(
        f"- [{tc['test_type']}] {tc['title']}: {tc['expected_result']}"
        for tc in state["draft_test_cases"]
    )
    prompt = _COMPLIANCE_CRITIC_PROMPT.format(
        safety_class=state["safety_class"],
        requirement_text=state["requirement_text"],
        clauses_summary=_format_clauses(independent_matches),
        test_cases_summary=test_cases_summary or "(none drafted)",
    )
    response = llm.invoke(prompt)
    parsed = ComplianceCritiqueOutput.model_validate_json(content_str(response))

    return {"critic_approved": parsed.approved, "critic_feedback": parsed.feedback}


# --- 7. Traceability Agent ---------------------------------------------------


def traceability_agent_node(state: GenerationState, *, deps: AgentDeps) -> dict[str, Any]:
    """Flags coverage gaps between the strategist's plan and what was actually
    drafted. This is a pure, in-memory check on the graph's own state.

    Actually building/persisting TraceabilityLink rows (DESIGN.md §5) and the
    audit log entry -- the real "DB read"/write DESIGN.md §3 mentions -- is the
    orchestration layer's job (Phase 7, API/worker): it has the real DB session
    and the approving user's identity, neither of which belongs in graph state.
    """
    del deps  # not needed for this node; kept for a uniform node signature
    planned = set(state["planned_test_types"])
    covered = {tc["test_type"] for tc in state["draft_test_cases"]}
    gaps = sorted(planned - covered)
    return {"coverage_gaps": gaps}
