# Streamlit UI (DESIGN.md §6: talks to the FastAPI backend only over HTTP --
# never imports testgen.api/testgen.generation/etc., so needs only the `ui`
# extra, not the rest of the stack).
FROM python:3.11-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --root-user-action=ignore ".[ui]"

FROM python:3.11-slim AS runtime

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

ENV PYTHONUNBUFFERED=1

USER app
EXPOSE 8501

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=2)" || exit 1

# streamlit run needs a real file path, not a module path (unlike uvicorn's
# module:attribute or celery -A's module path) -- resolved dynamically from
# wherever pip actually installed testgen.ui.app, rather than hardcoding the
# site-packages path or copying src/ a second time.
CMD ["sh", "-c", "streamlit run \"$(python -c 'import testgen.ui.app as m; print(m.__file__)')\" --server.address=0.0.0.0 --server.port=8501"]
