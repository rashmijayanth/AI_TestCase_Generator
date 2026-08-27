"""Seeds the regulatory corpus (knowledge/corpus.py) into the real vector
store, using the real Gemini embedder -- the gap flagged in docs/PROGRESS.md
Phase 9: nothing else calls seed_regulatory_corpus() outside of tests, so a
fresh docker-compose/Terraform-provisioned stack's Milvus collection starts
empty and the Regulatory Researcher agent has nothing to retrieve.

Run once per environment (idempotent -- Decision 20: each clause's id is a
deterministic hash of standard+clause_ref, so re-running just overwrites the
same rows in place, it doesn't duplicate them):

    python scripts/seed_corpus.py

Needs a real GEMINI_API_KEY (the corpus must be embedded with the same
model that will embed queries against it later -- seeding with a different
or fake embedder would make retrieval meaningless). Fails loudly via
get_embedder()'s existing ValueError if one isn't configured, rather than
silently falling back to a fake.
"""

from testgen.knowledge.corpus import SEED_CORPUS, seed_regulatory_corpus
from testgen.knowledge.embeddings import get_embedder
from testgen.knowledge.vector_store import get_vector_store
from testgen.platform.config import get_settings


def main() -> None:
    settings = get_settings()
    embedder = get_embedder(settings)
    store = get_vector_store(settings)

    seeded = seed_regulatory_corpus(embedder, store)
    print(f"Seeded {seeded}/{len(SEED_CORPUS)} clauses into {settings.milvus_uri}")


if __name__ == "__main__":
    main()
