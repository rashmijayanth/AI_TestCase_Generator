# Automatic Test Case Generation AI

AI-powered system that converts healthcare software requirements into compliant, traceable test cases (FDA / IEC 62304 / ISO 9001 / ISO 13485 / ISO 27001), with human-approved traceability and live Jira sync.

Full design: [docs/DESIGN.md](docs/DESIGN.md). Build status / current phase: [docs/PROGRESS.md](docs/PROGRESS.md).

## Local development

Requires Python 3.11 and Docker Desktop.

```powershell
scripts\setup_dev.ps1   # creates .venv, installs dev tooling
docker compose up -d postgres redis
pytest
ruff check .
mypy src tests
```

Run the API and UI directly against those two containers while developing:

```powershell
.venv\Scripts\uvicorn testgen.api.app:app --reload
scripts\run_ui.ps1
```

## Full stack (Docker)

```powershell
cp .env.example .env   # fill in GEMINI_API_KEY / JIRA_* if you have them
docker compose up -d --build
```

Brings up Postgres, Redis, and the `api` (`:8000`)/`worker`/`ui` (`:8501`) containers built from `infra/docker/*.Dockerfile` — see `infra/docker/README.md`. `infra/terraform/` has the matching AWS IaC (written to a real standard, not applied — see `infra/terraform/README.md` and DESIGN.md §8).

## Repo layout

See `docs/DESIGN.md` §9. Bounded contexts live under `src/testgen/`: `ingestion`, `knowledge`, `generation`, `traceability`, `compliance`, `integrations`, `api`, `ui`, `worker`, `platform`.
