"""Integration tests for agent nodes that need a real dependency beyond a
scripted LLM: Regulatory Researcher and Compliance Critic need a working
vector store (real Milvus Lite, tmp_path); Test Data Synthesizer now needs
real Presidio redaction (Phase 5) rather than a scripted/fake pass.
"""

from pathlib import Path

import pytest

from testgen.generation.agents import (
    AgentDeps,
    compliance_critic_node,
    data_synthesizer_node,
    regulatory_researcher_node,
)
from testgen.generation.state import new_generation_state
from testgen.knowledge.corpus import seed_regulatory_corpus
from testgen.knowledge.embeddings import EMBEDDING_DIMENSION, DeterministicFakeEmbedder
from testgen.knowledge.vector_store import MilvusVectorStore
from tests.fakes import ScriptedChatModelFactory, UnusedEmbedder, UnusedVectorStore


def _seeded_store(tmp_path: Path, embedder: DeterministicFakeEmbedder) -> MilvusVectorStore:
    store = MilvusVectorStore(uri=str(tmp_path / "agents_test.db"), dimension=EMBEDDING_DIMENSION)
    seed_regulatory_corpus(embedder, store)
    return store


@pytest.mark.integration
def test_regulatory_researcher_iterates_until_sufficient(tmp_path: Path) -> None:
    embedder = DeterministicFakeEmbedder(dimension=EMBEDDING_DIMENSION)
    store = _seeded_store(tmp_path, embedder)
    factory = ScriptedChatModelFactory(
        {
            "SufficiencyCheckOutput": [
                '{"sufficient": false, "refined_query": "software safety classification"}',
                '{"sufficient": true, "refined_query": ""}',
            ]
        }
    )
    deps = AgentDeps(chat_model_factory=factory, embedder=embedder, vector_store=store)
    state = new_generation_state("req-1", "The pump shall stop infusion within 500ms.")

    result = regulatory_researcher_node(state, deps=deps)

    assert len(result["retrieved_clauses"]) > 0


@pytest.mark.integration
def test_regulatory_researcher_stops_at_max_iterations_even_if_never_sufficient(
    tmp_path: Path,
) -> None:
    embedder = DeterministicFakeEmbedder(dimension=EMBEDDING_DIMENSION)
    store = _seeded_store(tmp_path, embedder)
    always_insufficient = '{"sufficient": false, "refined_query": "still not enough"}'
    factory = ScriptedChatModelFactory(
        {"SufficiencyCheckOutput": [always_insufficient, always_insufficient, always_insufficient]}
    )
    deps = AgentDeps(
        chat_model_factory=factory,
        embedder=embedder,
        vector_store=store,
        max_retrieval_iterations=3,
    )
    state = new_generation_state("req-1", "The pump shall stop infusion within 500ms.")

    result = regulatory_researcher_node(state, deps=deps)

    assert len(result["retrieved_clauses"]) > 0


@pytest.mark.integration
def test_compliance_critic_retrieves_independently_and_parses_rejection(tmp_path: Path) -> None:
    embedder = DeterministicFakeEmbedder(dimension=EMBEDDING_DIMENSION)
    store = _seeded_store(tmp_path, embedder)
    factory = ScriptedChatModelFactory(
        {
            "ComplianceCritiqueOutput": [
                '{"approved": false, "feedback": "Missing a boundary-value test.", '
                '"cited_clause_refs": []}'
            ]
        }
    )
    deps = AgentDeps(chat_model_factory=factory, embedder=embedder, vector_store=store)
    state = new_generation_state("req-1", "The pump shall stop infusion within 500ms.")
    state["safety_class"] = "C"
    state["draft_test_cases"] = [
        {
            "test_type": "functional",
            "title": "Normal infusion",
            "expected_result": "Completes normally",
        }
    ]

    result = compliance_critic_node(state, deps=deps)

    assert result["critic_approved"] is False
    assert "boundary-value" in result["critic_feedback"]


@pytest.mark.integration
def test_compliance_critic_approves_when_scripted_to(tmp_path: Path) -> None:
    embedder = DeterministicFakeEmbedder(dimension=EMBEDDING_DIMENSION)
    store = _seeded_store(tmp_path, embedder)
    factory = ScriptedChatModelFactory(
        {
            "ComplianceCritiqueOutput": [
                '{"approved": true, "feedback": "", "cited_clause_refs": ["5.5.3"]}'
            ]
        }
    )
    deps = AgentDeps(chat_model_factory=factory, embedder=embedder, vector_store=store)
    state = new_generation_state("req-1", "The pump shall stop infusion within 500ms.")
    state["safety_class"] = "C"
    state["draft_test_cases"] = [
        {
            "test_type": "safety_critical",
            "title": "Occlusion halts infusion",
            "expected_result": "Halts",
        }
    ]

    result = compliance_critic_node(state, deps=deps)

    assert result["critic_approved"] is True


@pytest.mark.integration
def test_data_synthesizer_redacts_via_real_presidio_and_marks_phi_redacted() -> None:
    """Synthetic data is fake by construction (see the agent's prompt), but this
    confirms the actual Presidio pass (Phase 5) runs and the honest phi_redacted
    flag flips to True once it does -- not just that the prompt asked nicely.
    """
    response = (
        '{"name": "occlusion-timing-values", '
        '"rows": [{"delay_ms": 499, "patient_name": "Jane Doe"}, '
        '{"delay_ms": 500, "patient_name": "Jane Doe"}]}'
    )
    deps = AgentDeps(
        chat_model_factory=ScriptedChatModelFactory({"TestDatasetDraftOutput": [response]}),
        embedder=UnusedEmbedder(),
        vector_store=UnusedVectorStore(),
    )
    state = new_generation_state("req-1", "text")
    state["draft_test_cases"] = [
        {
            "title": "Boundary timing",
            "test_type": "data_driven",
            "steps": [{"step_no": 1, "action": "vary delay", "expected": "..."}],
        }
    ]

    result = data_synthesizer_node(state, deps=deps)

    [dataset] = result["draft_test_datasets"]
    assert dataset["name"] == "occlusion-timing-values"
    assert dataset["phi_redacted"] is True
    assert dataset["test_case_title"] == "Boundary timing"
    assert len(dataset["data"]) == 2
    assert dataset["data"][0]["delay_ms"] == 499
    assert "Jane Doe" not in dataset["data"][0]["patient_name"]
