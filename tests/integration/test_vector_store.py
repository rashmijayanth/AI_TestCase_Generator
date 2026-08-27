"""Uses a real (embedded, file-backed) Milvus Lite instance -- confirmed to work
end-to-end on this Windows machine (see docs/PROGRESS.md). Marked integration
for consistency with the other "local service" tests, even though Milvus Lite
needs no separately-running container.
"""

from pathlib import Path

import pytest

from testgen.knowledge.embeddings import DeterministicFakeEmbedder
from testgen.knowledge.vector_store import ClauseRecord, MilvusVectorStore, stable_clause_id


@pytest.mark.integration
def test_upsert_and_search_round_trip(tmp_path: Path) -> None:
    embedder = DeterministicFakeEmbedder(dimension=8)
    store = MilvusVectorStore(uri=str(tmp_path / "test_clauses.db"), dimension=8)

    texts = {
        "iec_62304:5.5.3": "Software verification shall include boundary condition testing.",
        "gdpr:Art.17": "Data subjects have the right to erasure of their personal data.",
    }
    vectors = embedder.embed(list(texts.values()))
    records = [
        ClauseRecord(
            clause_id=stable_clause_id(key),
            standard=key.split(":")[0],
            clause_ref=key.split(":")[1],
            text=text,
            vector=vector,
        )
        for (key, text), vector in zip(texts.items(), vectors, strict=True)
    ]

    store.upsert_clauses(records)

    query_vector = embedder.embed(
        ["Software verification shall include boundary condition testing."]
    )[0]
    results = store.search(query_vector, top_k=1)

    assert len(results) == 1
    assert results[0].clause_ref == "5.5.3"
    assert results[0].standard == "iec_62304"


@pytest.mark.integration
def test_stable_clause_id_is_deterministic_and_positive() -> None:
    assert stable_clause_id("iec_62304:5.5.3") == stable_clause_id("iec_62304:5.5.3")
    assert stable_clause_id("iec_62304:5.5.3") != stable_clause_id("gdpr:Art.17")
    assert stable_clause_id("iec_62304:5.5.3") > 0
