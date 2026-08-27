# Dockerfiles (Phase 9)

Three services, three Dockerfiles — each a multi-stage build (`python:3.11-slim`
builder → slim runtime, non-root user) installing only the `pyproject.toml`
extras that service's actual imports need (verified by reading the import
chains, not guessed — see `docs/PROGRESS.md` Phase 9 decisions):

| Dockerfile | Extras installed | Entrypoint |
|---|---|---|
| `api.Dockerfile` | `api,db,ingestion,llm,embeddings,vectorstore,integrations,queue,observability` | `alembic upgrade head && uvicorn testgen.api.app:app` |
| `worker.Dockerfile` | `db,ingestion,llm,embeddings,vectorstore,compliance,queue,observability` (+ the spaCy model) | `celery -A testgen.worker.celery_app worker` |
| `ui.Dockerfile` | `ui` only (DESIGN.md §6: the UI never imports `testgen.api`/`testgen.generation`) | `streamlit run <installed testgen.ui.app path>` |

`docker-compose.yml` (repo root) builds all three for local dev. All three
build and run for real — `docker compose up` was run against this machine's
Docker Desktop as part of Phase 9 verification; see `docs/PROGRESS.md`.

`docker-compose.prod.yml` is an override for production: `docker-compose -f
docker-compose.yml -f infra/docker/docker-compose.prod.yml up -d` swaps each
service's local `build:` for `image: ${ECR_REGISTRY}/testgen-ai/<service>:latest`
(via the compose-spec `!reset` tag — verified with `docker compose config`
that it actually drops `build:` rather than merging alongside it). Used by
`infra/terraform/user_data.sh.tftpl` on instance boot.
