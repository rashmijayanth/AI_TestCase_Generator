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

ENV PYTHONUNBUFFERED=1

USER app

CMD ["celery", "-A", "testgen.worker.celery_app", "worker", "--loglevel=info"]
