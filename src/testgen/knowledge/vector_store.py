"""VectorStorePort: Milvus-backed clause storage/retrieval.

Embedded 'Milvus Lite' locally -- confirmed to install and work end-to-end on
this Windows machine (create/insert/search/drop all verified directly; see
docs/PROGRESS.md, which corrects DESIGN.md §7's assumption that milvus-lite is
Linux/macOS-only). Full Milvus standalone in prod; same pymilvus client code
either way, only the `uri` passed to MilvusClient changes.
"""

import hashlib
from dataclasses import dataclass
from typing import Protocol

from pymilvus import MilvusClient

from testgen.knowledge.embeddings import EMBEDDING_DIMENSION
from testgen.platform.config import Settings, get_settings

_COLLECTION_NAME = "regulatory_clauses"


def stable_clause_id(key: str) -> int:
    """Deterministic positive int64 id, derived from a human-meaningful string key.

    Milvus's default collection schema (pymilvus's simple create_collection helper)
    requires an int64 primary key -- confirmed empirically; a string id raises
    DataNotMatchException. clause_ref/standard stay as separate string fields.
    """
    digest = hashlib.sha256(key.encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, "big") & 0x7FFFFFFFFFFFFFFF


@dataclass(frozen=True)
class ClauseRecord:
    clause_id: int
    standard: str
    clause_ref: str
    text: str
    vector: list[float]


@dataclass(frozen=True)
class ClauseMatch:
    standard: str
    clause_ref: str
    text: str
    score: float


class VectorStorePort(Protocol):
    def upsert_clauses(self, clauses: list[ClauseRecord]) -> None: ...
    def search(self, query_vector: list[float], top_k: int = 5) -> list[ClauseMatch]: ...


class MilvusVectorStore:
    def __init__(self, uri: str, dimension: int = EMBEDDING_DIMENSION) -> None:
        self._client = MilvusClient(uri=uri)
        if not self._client.has_collection(_COLLECTION_NAME):
            self._client.create_collection(
                collection_name=_COLLECTION_NAME,
                dimension=dimension,
                metric_type="COSINE",
            )

    def upsert_clauses(self, clauses: list[ClauseRecord]) -> None:
        data = [
            {
                "id": clause.clause_id,
                "vector": clause.vector,
                "standard": clause.standard,
                "clause_ref": clause.clause_ref,
                "text": clause.text,
            }
            for clause in clauses
        ]
        self._client.upsert(collection_name=_COLLECTION_NAME, data=data)

    def search(self, query_vector: list[float], top_k: int = 5) -> list[ClauseMatch]:
        results = self._client.search(
            collection_name=_COLLECTION_NAME,
            data=[query_vector],
            limit=top_k,
            output_fields=["standard", "clause_ref", "text"],
        )
        matches: list[ClauseMatch] = []
        for hit in results[0]:
            entity = hit["entity"]
            matches.append(
                ClauseMatch(
                    standard=entity["standard"],
                    clause_ref=entity["clause_ref"],
                    text=entity["text"],
                    score=hit["distance"],
                )
            )
        return matches


def get_vector_store(settings: Settings | None = None) -> VectorStorePort:
    settings = settings or get_settings()
    return MilvusVectorStore(uri=settings.milvus_uri, dimension=EMBEDDING_DIMENSION)
