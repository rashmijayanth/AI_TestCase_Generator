"""Retrieval-quality eval: real Gemini embeddings + real Milvus Lite against
the seeded regulatory corpus (testgen.knowledge.corpus.SEED_CORPUS).

Closes docs/PROGRESS.md Decision 22's stated gap: DeterministicFakeEmbedder
(used everywhere else in the test suite, including test_generation_graph.py)
proves storage/retrieval *plumbing* works, not retrieval *quality* -- a
hash-based fake has no notion of semantic similarity. Only a real embedding
model can answer "does search_clauses actually find the right clause for a
realistic requirement," which is what this file measures.

Not run by default -- see conftest.py's _require_gemini_key.
"""

from dataclasses import dataclass

import pytest

from testgen.knowledge.embeddings import GeminiEmbedder
from testgen.knowledge.service import search_clauses
from testgen.knowledge.vector_store import MilvusVectorStore

pytestmark = pytest.mark.eval


@dataclass(frozen=True)
class _GoldenQuery:
    query: str
    expected_clause_refs: set[str]


GOLDEN_SET: list[_GoldenQuery] = [
    _GoldenQuery(
        "The infusion pump software shall be verified under both normal and "
        "boundary/anomalous conditions before release.",
        {"5.5.3"},
    ),
    _GoldenQuery(
        "Patients shall be able to request permanent erasure of their "
        "personal health data from the system without undue delay.",
        {"Art.17"},
    ),
    _GoldenQuery(
        "Access to the clinical database shall be restricted to authorized "
        "staff based on a documented access control policy.",
        {"A.9.1"},
    ),
    _GoldenQuery(
        "Every access to a patient's electronic record shall be logged in a "
        "secure, tamper-evident audit trail.",
        {"11.10"},
    ),
    _GoldenQuery(
        "Before release, the device's design shall be validated against "
        "user needs using production-equivalent units under real operating "
        "conditions.",
        {"820.30(g)"},
    ),
    _GoldenQuery(
        "Any nonconformity found during a quality review shall be "
        "investigated with corrective action to prevent it recurring.",
        {"10.2"},
    ),
    _GoldenQuery(
        "Patient-identifying fields shall be pseudonymized or encrypted "
        "before being stored, appropriate to the risk.",
        {"Art.32"},
    ),
    _GoldenQuery(
        "The manufacturer shall monitor post-market feedback to catch "
        "device quality problems as early as possible.",
        {"8.2.1"},
    ),
]

MIN_RECALL_AT_5 = 0.75


def test_retrieval_recall_at_5_against_golden_set(
    real_seeded_store: tuple[GeminiEmbedder, MilvusVectorStore],
) -> None:
    embedder, store = real_seeded_store
    misses: list[tuple[str, set[str], set[str]]] = []

    for item in GOLDEN_SET:
        matches = search_clauses(item.query, embedder, store, top_k=5)
        retrieved_refs = {m.clause_ref for m in matches}
        if retrieved_refs.isdisjoint(item.expected_clause_refs):
            misses.append((item.query, item.expected_clause_refs, retrieved_refs))

    recall = (len(GOLDEN_SET) - len(misses)) / len(GOLDEN_SET)
    failure_detail = "\n".join(
        f"  MISS: {query!r}\n    expected one of {expected}, retrieved {got}"
        for query, expected, got in misses
    )
    assert recall >= MIN_RECALL_AT_5, (
        f"Retrieval recall@5 = {recall:.2f} (need >= {MIN_RECALL_AT_5}) "
        f"over {len(GOLDEN_SET)} golden queries.\n{failure_detail}"
    )
