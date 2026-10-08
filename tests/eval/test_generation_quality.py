"""Pipeline-quality eval: runs real requirements through the full LangGraph
pipeline with real Gemini calls end-to-end, auto-approves the human gate, and
asserts on output *quality* -- safety classification correctness and minimum
test-type coverage -- not just JSON schema shape.

Not run by default -- see conftest.py's _require_gemini_key. Run with
`pytest -m eval -s` to see real per-requirement token/latency numbers.
"""

from dataclasses import dataclass
from typing import cast
import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from testgen.generation.agents import AgentDeps
from testgen.generation.graph import build_generation_graph
from testgen.generation.state import GenerationState, new_generation_state
from testgen.platform.enums import SafetyClass

pytestmark = pytest.mark.eval


@dataclass(frozen=True)
class _GoldenRequirement:
    text: str
    expected_safety_class: SafetyClass
    required_test_types: set[str]


GOLDEN_REQUIREMENTS: list[_GoldenRequirement] = [
    _GoldenRequirement(
        "The infusion pump shall stop delivery within 500ms of an occlusion "
        "alarm to prevent patient harm.",
        SafetyClass.C,
        {"functional", "safety_critical"},
    ),
    _GoldenRequirement(
        "The dashboard shall display the clinician's display name in the "
        "top-right corner of every screen.",
        SafetyClass.A,
        {"functional"},
    ),
]


def _run_to_approval(
    deps: AgentDeps, requirement_id: str, requirement_text: str, max_retries: int = 3
) -> GenerationState:
    graph = build_generation_graph(deps, checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": requirement_id}}
    initial_state = new_generation_state(requirement_id, requirement_text, max_retries=max_retries)

    interrupted = graph.invoke(initial_state, config)
    assert "__interrupt__" in interrupted, "pipeline should always reach the human_approval gate"

    final = graph.invoke(Command(resume={"approved": True, "approver_id": "eval-run"}), config)
    # graph.invoke()'s stub returns dict[str, Any] | Any (LangGraph's
    # CompiledStateGraph isn't generic-narrowed on the public invoke() type
    # signature) -- cast rather than loosen this function's own return type,
    # since every field this eval reads below really is a GenerationState key.
    return cast(GenerationState, final)


@pytest.mark.parametrize(
    "golden", GOLDEN_REQUIREMENTS, ids=lambda g: f"safety_class_{g.expected_safety_class.value}"
)
def test_pipeline_classifies_and_covers_required_test_types(
    golden: _GoldenRequirement, real_default_deps: AgentDeps
) -> None:
    deps = real_default_deps
    final = _run_to_approval(deps, f"eval-{golden.expected_safety_class.value}", golden.text)

    assert final["safety_class"] == golden.expected_safety_class.value, (
        f"expected safety class {golden.expected_safety_class.value}, "
        f"got {final['safety_class']} (rationale: {final['analysis_rationale']!r})"
    )
    assert golden.required_test_types <= set(final["planned_test_types"]), (
        f"missing required test types: "
        f"{golden.required_test_types - set(final['planned_test_types'])}"
    )
    assert final["critic_approved"] or final["retry_count"] >= final["max_retries"]
    assert len(final["draft_test_cases"]) >= len(golden.required_test_types)

    total_in = sum(call["input_tokens"] for call in deps.usage_log)
    total_out = sum(call["output_tokens"] for call in deps.usage_log)
    print(
        f"\n[{golden.expected_safety_class.value}] {len(deps.usage_log)} LLM calls, "
        f"{total_in} input / {total_out} output tokens, "
        f"{final['retry_count']} generator attempt(s)"
    )
