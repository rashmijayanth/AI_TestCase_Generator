# FastAPI service (DESIGN.md §7). Needs every extra generation/graph.py and
# requirements.py import transitively pull in at module scope -- confirmed by
# reading the actual import chain, not guessed: embeddings/vectorstore/llm
# because generation.agents imports get_embedder/get_vector_store/get_chat_model
# eagerly even though the API's own read-only deps (Decision 40) never call
# them for real; queue because requirements.py imports generate_test_cases_task,
# which imports testgen.worker.celery_app; integrations for the Jira sync call
# on approve. compliance (presidio+spaCy) is deliberately excluded -- PHI
# redaction only runs inside the worker's data_synthesizer_node via a lazy
# import (Decision 34), so the API never needs it even transitively.
FROM python:3.11-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --root-user-action=ignore \
    ".[api,db,ingestion,llm,embeddings,vectorstore,integrations,queue,observability]"

FROM python:3.11-slim AS runtime

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY alembic.ini ./
COPY alembic/ ./alembic/

# docker-compose.yml mounts the appdata named volume at /app/data (Milvus
# Lite's db file + LocalFilesystemStorage's uploaded-document blobs). A
# fresh named volume is seeded from whatever's already at that path in the
# image, ownership included -- pre-creating it here as root, owned by the
# non-root `app` user below, is what lets that user actually write into it.
# Confirmed live in Phase 11: without this, ingest_document()'s first real
# upload crashed with PermissionError: [Errno 13] '/app/data/storage'.
RUN mkdir -p /app/data && chown app:app /app/data

ENV PYTHONUNBUFFERED=1

USER app
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" || exit 1

CMD ["sh", "-c", "alembic upgrade head && uvicorn testgen.api.app:app --host 0.0.0.0 --port 8000"]
