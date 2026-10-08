"""Unit tests for agent nodes that don't need a vector store (Requirement Analyst,
Test Strategist, Test Case Generator, Test Data Synthesizer, Traceability Agent).
Regulatory Researcher and Compliance Critic are integration-tested instead (see
tests/integration/test_generation_agents.py) since they genuinely need a working
vector store.
"""

from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from testgen.generation.agents import (
    AgentDeps,
    case_generator_node,
    data_synthesizer_node,
    requirement_analyst_node,
    strategist_node,
    traceability_agent_node,
)
from testgen.generation.llm import extract_usage
from testgen.generation.state import new_generation_state
from tests.fakes import ScriptedChatModelFactory, UnusedEmbedder, UnusedVectorStore


def _deps(factory: ScriptedChatModelFactory) -> AgentDeps:
    return AgentDeps(
        chat_model_factory=factory, embedder=UnusedEmbedder(), vector_store=UnusedVectorStore()
    )


@pytest.mark.unit
def test_requirement_analyst_classifies_safety_class() -> None:
    deps = _deps(
        ScriptedChatModelFactory(
            {
                "RequirementAnalysisOutput": [
                    '{"safety_class": "C", "rationale": "Could cause serious harm."}'
                ]
            }
        )
    )
    state = new_generation_state(
        "req-1", "The pump shall stop infusion within 500ms of an occlusion alarm."
    )

    result = requirement_analyst_node(state, deps=deps)

    assert result["safety_class"] == "C"
    assert "serious harm" in result["analysis_rationale"]


@pytest.mark.unit
def test_test_strategist_plans_test_types() -> None:
    deps = _deps(
        ScriptedChatModelFactory(
            {
                "TestPlanOutput": [
                    '{"test_types": ["safety_critical", "functional"], '
                    '"rationale": "Safety class C needs failure-mode coverage."}'
                ]
            }
        )
    )
    state = new_generation_state("req-1", "The pump shall stop infusion within 500ms.")
    state["safety_class"] = "C"

    result = strategist_node(state, deps=deps)

    assert result["planned_test_types"] == ["safety_critical", "functional"]
    assert "failure-mode" in result["strategist_rationale"]


@pytest.mark.unit
def test_test_case_generator_drafts_structured_cases_and_increments_retry() -> None:
    response = (
        '{"test_cases": [{"title": "Occlusion alarm stops infusion", '
        '"test_type": "safety_critical", "preconditions": "Pump running", '
        '"steps": [{"step_no": 1, "action": "Trigger occlusion", '
        '"expected": "Infusion halts within 500ms"}], '
        '"expected_result": "Infusion stops and alarm sounds", "priority": "critical"}]}'
    )
    deps = _deps(ScriptedChatModelFactory({"TestCaseGeneratorOutput": [response]}))
    state = new_generation_state("req-1", "The pump shall stop infusion within 500ms.")
    state["safety_class"] = "C"
    state["planned_test_types"] = ["safety_critical"]

    result = case_generator_node(state, deps=deps)

    assert result["retry_count"] == 1
    [test_case] = result["draft_test_cases"]
    assert test_case["title"] == "Occlusion alarm stops infusion"
    assert test_case["test_type"] == "safety_critical"
    assert test_case["priority"] == "critical"
    assert test_case["steps"][0]["action"] == "Trigger occlusion"


@pytest.mark.unit
def test_test_case_generator_includes_critic_feedback_when_retrying() -> None:
    captured: dict[str, str] = {}
    canned = AIMessage(
        content='{"test_cases": [{"title": "t", "test_type": "functional", '
        '"preconditions": "", "steps": [], "expected_result": "", "priority": "low"}]}'
    )

    class CapturingChatModel(FakeMessagesListChatModel):
        def invoke(self, input: Any, *args: Any, **kwargs: Any) -> AIMessage:
            captured["prompt"] = str(input)
            result = super().invoke(input, *args, **kwargs)
            assert isinstance(result, AIMessage)
            return result

    deps = AgentDeps(
        chat_model_factory=lambda **_: CapturingChatModel(responses=[canned]),
        embedder=UnusedEmbedder(),
        vector_store=UnusedVectorStore(),
    )
    state = new_generation_state("req-1", "The pump shall stop infusion within 500ms.")
    state["planned_test_types"] = ["functional"]
    state["critic_feedback"] = "Missing a boundary-value test at exactly 500ms."

    case_generator_node(state, deps=deps)

    assert "Missing a boundary-value test at exactly 500ms." in captured["prompt"]


@pytest.mark.unit
def test_test_data_synthesizer_skips_when_no_data_driven_cases() -> None:
    deps = _deps(ScriptedChatModelFactory({}))
    state = new_generation_state("req-1", "text")
    state["draft_test_cases"] = [{"title": "t", "test_type": "functional", "steps": []}]

    result = data_synthesizer_node(state, deps=deps)

    assert result["draft_test_datasets"] == []


@pytest.mark.unit
def test_traceability_agent_flags_missing_coverage() -> None:
    deps = _deps(ScriptedChatModelFactory({}))
    state = new_generation_state("req-1", "text")
    state["planned_test_types"] = ["functional", "boundary", "safety_critical"]
    state["draft_test_cases"] = [{"test_type": "functional"}, {"test_type": "boundary"}]

    result = traceability_agent_node(state, deps=deps)

    assert result["coverage_gaps"] == ["safety_critical"]


@pytest.mark.unit
def test_traceability_agent_reports_no_gaps_when_fully_covered() -> None:
    deps = _deps(ScriptedChatModelFactory({}))
    state = new_generation_state("req-1", "text")
    state["planned_test_types"] = ["functional"]
    state["draft_test_cases"] = [{"test_type": "functional"}]

    result = traceability_agent_node(state, deps=deps)

    assert result["coverage_gaps"] == []


@pytest.mark.unit
def test_extract_usage_reads_real_usage_metadata() -> None:
    message = AIMessage(
        content="{}",
        usage_metadata={"input_tokens": 42, "output_tokens": 7, "total_tokens": 49},
    )

    assert extract_usage(message) == (42, 7)


@pytest.mark.unit
def test_extract_usage_defaults_to_zero_without_usage_metadata() -> None:
    # FakeMessagesListChatModel-produced messages (every other test in this
    # file) never set usage_metadata -- confirms tracking degrades safely
    # rather than raising, so it can't break any node's existing behavior.
    assert extract_usage(AIMessage(content="{}")) == (0, 0)


@pytest.mark.unit
def test_requirement_analyst_records_llm_usage() -> None:
    """A node's real call site should end up on deps.usage_log with the
    right agent_name, even though ScriptedChatModelFactory's fake responses
    (used by every other test in this file) don't set real token counts."""
    deps = _deps(
        ScriptedChatModelFactory(
            {"RequirementAnalysisOutput": ['{"safety_class": "A", "rationale": "Low risk."}']}
        )
    )
    state = new_generation_state("req-1", "The UI shall display the patient's name.")

    requirement_analyst_node(state, deps=deps)

    assert len(deps.usage_log) == 1
    assert deps.usage_log[0]["agent_name"] == "requirement_analyst"
    assert deps.usage_log[0]["input_tokens"] == 0  # ScriptedChatModelFactory sets no real usage
    assert "latency_ms" in deps.usage_log[0]
