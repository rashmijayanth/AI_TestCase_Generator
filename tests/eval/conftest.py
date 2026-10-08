"""Fixtures shared by tests/eval/*.

These tests make real calls to Gemini's API (embeddings + chat) and real
Milvus Lite -- intentionally NOT part of the default `pytest -m "not eval"`
sweep every verification run in docs/PROGRESS.md uses. Run them explicitly
with `pytest -m eval` once a real GEMINI_API_KEY is configured in .env.

Skip (not fail) without a key, so a plain `pytest` with no marker filter
still exits green -- this file only adds honest, closeable-later gaps, never
a red CI run for someone who hasn't configured Gemini locally.
"""

from pathlib import Path

import pytest

from testgen.generation.agents import AgentDeps
from testgen.generation.llm import get_chat_model
from testgen.knowledge.corpus import seed_regulatory_corpus
from testgen.knowledge.embeddings import EMBEDDING_DIMENSION, GeminiEmbedder
from testgen.knowledge.vector_store import MilvusVectorStore
from testgen.platform.config import get_settings


@pytest.fixture(autouse=True)
def _require_gemini_key() -> None:
    if not get_settings().gemini_api_key:
        pytest.skip(
            "tests/eval needs a real GEMINI_API_KEY in .env -- see "
            "docs/PROGRESS.md's Gemini live-call caveat (Decision 22)."
        )


@pytest.fixture
def real_seeded_store(tmp_path: Path) -> tuple[GeminiEmbedder, MilvusVectorStore]:
    """Real GeminiEmbedder + a fresh, real Milvus Lite file, seeded with the
    real regulatory corpus -- everything test_generation_graph.py fakes out
    (DeterministicFakeEmbedder), made real for this eval only.
    """
    settings = get_settings()
    embedder = GeminiEmbedder(
        api_key=settings.gemini_api_key, model=settings.gemini_embedding_model
    )
    store = MilvusVectorStore(uri=str(tmp_path / "eval.db"), dimension=EMBEDDING_DIMENSION)
    seed_regulatory_corpus(embedder, store)
    return embedder, store


@pytest.fixture
def real_default_deps(real_seeded_store: tuple[GeminiEmbedder, MilvusVectorStore]) -> AgentDeps:
    """Same shape as generation.agents.build_default_deps(), but pointed at
    this test's own tmp_path-scoped store/corpus rather than the app's
    configured one, so eval runs never touch real project data.
    """
    embedder, store = real_seeded_store
    settings = get_settings()
    return AgentDeps(
        chat_model_factory=lambda **kwargs: get_chat_model(settings, **kwargs),
        embedder=embedder,
        vector_store=store,
    )
