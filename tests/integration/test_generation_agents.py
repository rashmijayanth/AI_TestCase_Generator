"""Integration tests for the two agent nodes that genuinely need a working
vector store: Regulatory Researcher (bounded retrieval loop) and Compliance
Critic (independent re-retrieval). Real Milvus Lite (tmp_path) + the seeded
corpus + DeterministicFakeEmbedder; every LLM call is scripted.
"""

from pathlib import Path

import pytest

from testgen.generation.agents import AgentDeps, compliance_critic_node, regulatory_researcher_node
from testgen.generation.state import new_generation_state
from testgen.knowledge.corpus import seed_regulatory_corpus
from testgen.knowledge.embeddings import EMBEDDING_DIMENSION, DeterministicFakeEmbedder
from testgen.knowledge.vector_store import MilvusVectorStore
from tests.fakes import ScriptedChatModelFactory


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
