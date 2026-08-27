"""Full graph integration tests: real Milvus Lite (tmp_path) + DeterministicFakeEmbedder
for retrieval, ScriptedChatModelFactory for every LLM call, real LangGraph
interrupt/resume mechanics (InMemorySaver). No live Gemini calls anywhere -- see
docs/PROGRESS.md on GeminiEmbedder/get_chat_model not being live-tested.
"""

from pathlib import Path

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from testgen.generation.agents import AgentDeps
from testgen.generation.graph import build_generation_graph
from testgen.generation.state import new_generation_state
from testgen.knowledge.corpus import seed_regulatory_corpus
from testgen.knowledge.embeddings import EMBEDDING_DIMENSION, DeterministicFakeEmbedder
from testgen.knowledge.vector_store import MilvusVectorStore
from tests.fakes import ScriptedChatModelFactory

_ANALYSIS_RESPONSE = '{"safety_class": "C", "rationale": "Failure could delay treatment."}'
_SUFFICIENT_RESPONSE = '{"sufficient": true, "refined_query": ""}'
_PLAN_RESPONSE = (
    '{"test_types": ["safety_critical", "functional"], '
    '"rationale": "Class C needs failure-mode coverage."}'
)
_ONE_TEST_CASE_RESPONSE = (
    '{"test_cases": [{"title": "Occlusion alarm stops infusion", "test_type": "safety_critical", '
    '"preconditions": "Pump running", "steps": [{"step_no": 1, "action": "Trigger occlusion", '
    '"expected": "Infusion halts within 500ms"}], '
    '"expected_result": "Infusion stops and alarm sounds", "priority": "critical"}, '
    '{"title": "Normal infusion completes", "test_type": "functional", '
    '"preconditions": "Pump idle", "steps": [{"step_no": 1, "action": "Start infusion", '
    '"expected": "Infusion runs to completion"}], '
    '"expected_result": "Infusion completes normally", "priority": "medium"}]}'
)
_APPROVED_RESPONSE = '{"approved": true, "feedback": "", "cited_clause_refs": ["5.5.3"]}'
_REJECTED_RESPONSE = (
    '{"approved": false, "feedback": "Missing a boundary-value test.", "cited_clause_refs": []}'
)


def _seeded_store(tmp_path: Path, embedder: DeterministicFakeEmbedder) -> MilvusVectorStore:
    store = MilvusVectorStore(uri=str(tmp_path / "graph_test.db"), dimension=EMBEDDING_DIMENSION)
    seed_regulatory_corpus(embedder, store)
    return store


@pytest.mark.integration
def test_graph_runs_end_to_end_with_immediate_critic_approval(tmp_path: Path) -> None:
    embedder = DeterministicFakeEmbedder(dimension=EMBEDDING_DIMENSION)
    store = _seeded_store(tmp_path, embedder)
    factory = ScriptedChatModelFactory(
        {
            "RequirementAnalysisOutput": [_ANALYSIS_RESPONSE],
            "SufficiencyCheckOutput": [_SUFFICIENT_RESPONSE],
            "TestPlanOutput": [_PLAN_RESPONSE],
            "TestCaseGeneratorOutput": [_ONE_TEST_CASE_RESPONSE],
            "ComplianceCritiqueOutput": [_APPROVED_RESPONSE],
        }
    )
    deps = AgentDeps(chat_model_factory=factory, embedder=embedder, vector_store=store)
    graph = build_generation_graph(deps, checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "req-1"}}

    initial_state = new_generation_state(
        "req-1", "The pump shall stop infusion within 500ms of an occlusion alarm."
    )
    result = graph.invoke(initial_state, config)

    assert "__interrupt__" in result
    assert result["safety_class"] == "C"
    assert result["critic_approved"] is True
    assert result["retry_count"] == 1
    assert len(result["draft_test_cases"]) == 2
    assert graph.get_state(config).next == ("human_approval",)

    final = graph.invoke(Command(resume={"approved": True, "approver_id": "user-42"}), config)

    assert final["human_approved"] is True
    assert final["human_approver_id"] == "user-42"
    assert final["coverage_gaps"] == []


@pytest.mark.integration
def test_graph_retries_generator_after_critic_rejection_then_approves(tmp_path: Path) -> None:
    embedder = DeterministicFakeEmbedder(dimension=EMBEDDING_DIMENSION)
    store = _seeded_store(tmp_path, embedder)
    factory = ScriptedChatModelFactory(
        {
            "RequirementAnalysisOutput": [_ANALYSIS_RESPONSE],
            "SufficiencyCheckOutput": [_SUFFICIENT_RESPONSE],
            "TestPlanOutput": [_PLAN_RESPONSE],
            "TestCaseGeneratorOutput": [_ONE_TEST_CASE_RESPONSE, _ONE_TEST_CASE_RESPONSE],
            "ComplianceCritiqueOutput": [_REJECTED_RESPONSE, _APPROVED_RESPONSE],
        }
    )
    deps = AgentDeps(chat_model_factory=factory, embedder=embedder, vector_store=store)
    graph = build_generation_graph(deps, checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "req-2"}}

    result = graph.invoke(
        new_generation_state("req-2", "The pump shall stop infusion within 500ms."), config
    )

    assert result["critic_approved"] is True
    assert result["retry_count"] == 2  # generator ran twice: initial draft + one retry
    assert graph.get_state(config).next == ("human_approval",)


@pytest.mark.integration
def test_graph_proceeds_to_human_approval_after_exhausting_retries(tmp_path: Path) -> None:
    embedder = DeterministicFakeEmbedder(dimension=EMBEDDING_DIMENSION)
    store = _seeded_store(tmp_path, embedder)
    factory = ScriptedChatModelFactory(
        {
            "RequirementAnalysisOutput": [_ANALYSIS_RESPONSE],
            "SufficiencyCheckOutput": [_SUFFICIENT_RESPONSE],
            "TestPlanOutput": [_PLAN_RESPONSE],
            "TestCaseGeneratorOutput": [_ONE_TEST_CASE_RESPONSE] * 3,
            "ComplianceCritiqueOutput": [_REJECTED_RESPONSE] * 3,
        }
    )
    deps = AgentDeps(chat_model_factory=factory, embedder=embedder, vector_store=store)
    graph = build_generation_graph(deps, checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "req-3"}}

    result = graph.invoke(
        new_generation_state("req-3", "The pump shall stop infusion within 500ms.", max_retries=3),
        config,
    )

    assert result["critic_approved"] is False
    assert result["retry_count"] == 3
    assert graph.get_state(config).next == ("human_approval",)


@pytest.mark.integration
def test_human_rejection_is_recorded_without_crashing(tmp_path: Path) -> None:
    embedder = DeterministicFakeEmbedder(dimension=EMBEDDING_DIMENSION)
    store = _seeded_store(tmp_path, embedder)
    factory = ScriptedChatModelFactory(
        {
            "RequirementAnalysisOutput": [_ANALYSIS_RESPONSE],
            "SufficiencyCheckOutput": [_SUFFICIENT_RESPONSE],
            "TestPlanOutput": [_PLAN_RESPONSE],
            "TestCaseGeneratorOutput": [_ONE_TEST_CASE_RESPONSE],
            "ComplianceCritiqueOutput": [_APPROVED_RESPONSE],
        }
    )
    deps = AgentDeps(chat_model_factory=factory, embedder=embedder, vector_store=store)
    graph = build_generation_graph(deps, checkpointer=InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "req-4"}}

    graph.invoke(
        new_generation_state("req-4", "The pump shall stop infusion within 500ms."), config
    )
    final = graph.invoke(Command(resume={"approved": False, "approver_id": "user-7"}), config)

    assert final["human_approved"] is False
    assert final["human_approver_id"] == "user-7"
