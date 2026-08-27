from pathlib import Path

import pytest

from testgen.knowledge.corpus import SEED_CORPUS, seed_regulatory_corpus
from testgen.knowledge.embeddings import EMBEDDING_DIMENSION, DeterministicFakeEmbedder
from testgen.knowledge.service import search_clauses
from testgen.knowledge.vector_store import MilvusVectorStore
from testgen.platform.enums import Standard


@pytest.mark.integration
def test_seed_regulatory_corpus_inserts_all_clauses(tmp_path: Path) -> None:
    embedder = DeterministicFakeEmbedder(dimension=EMBEDDING_DIMENSION)
    store = MilvusVectorStore(uri=str(tmp_path / "corpus.db"), dimension=EMBEDDING_DIMENSION)

    count = seed_regulatory_corpus(embedder, store)

    assert count == len(SEED_CORPUS)


@pytest.mark.integration
def test_seeded_corpus_covers_every_standard() -> None:
    seen_standards = {clause.standard for clause in SEED_CORPUS}

    assert seen_standards == set(Standard)


@pytest.mark.integration
def test_exact_text_match_retrieves_the_right_clause(tmp_path: Path) -> None:
    """DeterministicFakeEmbedder isn't semantically meaningful (see its own
    docstring), so this only proves storage/retrieval plumbing is wired
    correctly end-to-end -- not retrieval *quality*, which needs a real
    embedding model to evaluate (GeminiEmbedder, untested live -- see
    docs/PROGRESS.md).
    """
    embedder = DeterministicFakeEmbedder(dimension=EMBEDDING_DIMENSION)
    store = MilvusVectorStore(uri=str(tmp_path / "corpus.db"), dimension=EMBEDDING_DIMENSION)
    seed_regulatory_corpus(embedder, store)

    target = next(c for c in SEED_CORPUS if c.clause_ref == "Art.17")
    results = search_clauses(target.text, embedder, store, top_k=1)

    assert len(results) == 1
    assert results[0].clause_ref == "Art.17"
    assert results[0].standard == Standard.GDPR.value
