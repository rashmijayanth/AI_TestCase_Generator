"""Shared test doubles for the generation pipeline's LLM dependency."""

from typing import Any

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage


class ScriptedChatModelFactory:
    """Drop-in replacement for AgentDeps.chat_model_factory in tests.

    Routes each call to a canned JSON response based on the response_schema's
    Pydantic-generated "title" (== the schema class name), consuming each
    schema's response list in order -- so a node called multiple times (e.g.
    the Test Case Generator across retries) can be scripted to answer
    differently each time.
    """

    def __init__(self, responses_by_schema_title: dict[str, list[str]]) -> None:
        self._queues = {key: list(value) for key, value in responses_by_schema_title.items()}

    def __call__(
        self, *, response_schema: dict[str, Any] | None = None, **_: Any
    ) -> FakeMessagesListChatModel:
        title = (response_schema or {}).get("title", "")
        queue = self._queues.get(title)
        if not queue:
            raise AssertionError(f"No scripted response left for schema {title!r}")
        content = queue.pop(0)
        return FakeMessagesListChatModel(responses=[AIMessage(content=content)])


class UnusedVectorStore:
    """Placeholder VectorStorePort for tests whose node under test should never
    touch the vector store -- raises loudly if that assumption turns out wrong.
    """

    def upsert_clauses(self, clauses: Any) -> None:
        raise AssertionError("This test's node should not touch the vector store")

    def search(self, query_vector: Any, top_k: int = 5) -> Any:
        raise AssertionError("This test's node should not touch the vector store")


class UnusedEmbedder:
    def embed(self, texts: Any) -> Any:
        raise AssertionError("This test's node should not touch the embedder")
