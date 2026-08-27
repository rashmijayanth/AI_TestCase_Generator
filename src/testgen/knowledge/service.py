"""Single-query convenience: embed + search in one call.

The iterative "keep querying until sufficient grounding" loop (DESIGN.md §3 --
Regulatory Researcher, Compliance Critic) is agent-level judgment and belongs to
the generation phase; this is the stateless building block it will call
repeatedly from its own ReAct loop.
"""

from testgen.knowledge.embeddings import EmbeddingPort
from testgen.knowledge.vector_store import ClauseMatch, VectorStorePort


def search_clauses(
    query_text: str,
    embedder: EmbeddingPort,
    store: VectorStorePort,
    top_k: int = 5,
) -> list[ClauseMatch]:
    [query_vector] = embedder.embed([query_text])
    return store.search(query_vector, top_k=top_k)
