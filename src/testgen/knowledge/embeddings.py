"""EmbeddingPort: turns text into vectors.

GeminiEmbedder is real, working integration code (its request/response shapes
were verified against the installed google-genai 2.20.0 SDK by introspection),
but it has NOT been exercised against the live API in this environment -- no
GEMINI_API_KEY is available here (see docs/PROGRESS.md). Smoke-test it once a
real key is configured. DeterministicFakeEmbedder is what the automated test
suite actually runs against, so tests never need network access or a real key.

Model note: text-embedding-004 was retired by Google on 2026-01-14. This uses
its replacement, gemini-embedding-001, which defaults to 3072-dim output --
we pin output_dimensionality=EMBEDDING_DIMENSION (768) via EmbedContentConfig
so it stays compatible with the existing Milvus collection schema (see
vector_store.py) without needing to recreate the collection at a new
dimension.
"""

import hashlib
from typing import Protocol

from testgen.platform.config import Settings, get_settings

EMBEDDING_DIMENSION = 768  # pinned via output_dimensionality; see module docstring


class EmbeddingPort(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _extract_vectors(result: object) -> list[list[float]]:
    """Split out from GeminiEmbedder.embed so the response-shape mapping is
    testable with a plain fake object, without needing a real SDK client.
    """
    embeddings = getattr(result, "embeddings", None) or []
    return [list(getattr(embedding, "values", None) or []) for embedding in embeddings]


class GeminiEmbedder:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-embedding-001",
        output_dimensionality: int = EMBEDDING_DIMENSION,
    ) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required to construct GeminiEmbedder")
        from google import genai  # lazy: the fake-embedder path never needs this SDK installed

        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._output_dimensionality = output_dimensionality

    def embed(self, texts: list[str]) -> list[list[float]]:
        from google.genai import types

        # list[str] is a valid runtime argument (confirmed via signature
        # introspection: contents accepts list[str | Image | File | Part | ...]),
        # but mypy's strict invariant-generics rule doesn't consider list[str]
        # assignable to a differently-parameterized list[...] union member.
        result = self._client.models.embed_content(
            model=self._model,
            contents=texts,  # type: ignore[arg-type]
            config=types.EmbedContentConfig(output_dimensionality=self._output_dimensionality),
        )
        return _extract_vectors(result)


class DeterministicFakeEmbedder:
    """Hash-based: same text -> same vector, different text -> a different vector.

    Not semantically meaningful (similar meanings won't cluster) -- only useful
    for exercising storage/retrieval plumbing without a real embedding model.
    """

    def __init__(self, dimension: int = EMBEDDING_DIMENSION) -> None:
        self._dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        repeats = (self._dimension // len(digest)) + 1
        raw = (digest * repeats)[: self._dimension]
        return [(b / 127.5) - 1.0 for b in raw]


def get_embedder(settings: Settings | None = None) -> EmbeddingPort:
    settings = settings or get_settings()
    return GeminiEmbedder(api_key=settings.gemini_api_key, model=settings.gemini_embedding_model)
