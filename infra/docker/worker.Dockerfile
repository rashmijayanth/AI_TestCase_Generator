# Celery worker (DESIGN.md §7: "background processing for slow LLM jobs").
# Runs the real generation graph end to end, so unlike the API it needs
# `compliance` for real -- data_synthesizer_node's lazy `redact_dataset_rows`
# import (Decision 34) resolves for real here, on the actual generation path.
# No `api`/`integrations` extras: the worker never imports testgen.api, and
# Jira sync happens in the API's approve endpoint, not here.
FROM python:3.11-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --root-user-action=ignore \
    ".[db,ingestion,llm,embeddings,vectorstore,compliance,queue,observability]" \
    && python -m spacy download en_core_web_sm

FROM python:3.11-slim AS runtime

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY scripts/seed_corpus.py ./scripts/seed_corpus.py

# Same appdata-volume ownership issue as api.Dockerfile -- see the comment
# there. The worker writes Milvus Lite's db file into /app/data too.
RUN mkdir -p /app/data && chown app:app /app/data

ENV PYTHONUNBUFFERED=1

USER app

# scripts/seed_corpus.py isn't run automatically here -- it's a one-time
# operational step (Phase 11), invoked explicitly via `docker compose exec
# worker python scripts/seed_corpus.py` (local dev) or from
# user_data.sh.tftpl after the stack comes up (EC2). This container already
# has the embeddings/vectorstore extras and the real env vars the script
# needs, which is why it lives here rather than in a bare venv.
#
# --concurrency=1: Milvus Lite (knowledge/vector_store.py) is a single-process
# embedded engine -- it file-locks its .db file, so two Celery child processes
# opening their own MilvusClient at once raises DataDirLockedError. Without
# this flag, Celery's default prefork pool spawns one child per CPU core,
# and two "Generate" clicks close together reliably hit that race. Production
# swaps Milvus Lite for full Milvus standalone (see vector_store.py's module
# docstring), which supports real concurrent access -- at that point this
# flag can be relaxed.
CMD ["celery", "-A", "testgen.worker.celery_app", "worker", "--loglevel=info", "--concurrency=1"]
