# Automatic Test Case Generation AI

AI-powered system that converts healthcare software requirements into compliant, traceable test cases (FDA / IEC 62304 / ISO 9001 / ISO 13485 / ISO 27001), with human-approved traceability and live Jira sync.

Full design: [docs/DESIGN.md](docs/DESIGN.md). Build status / current phase: [docs/PROGRESS.md](docs/PROGRESS.md).

## Local development

Requires Python 3.11 and Docker Desktop.

```powershell
scripts\setup_dev.ps1   # creates .venv, installs dev tooling
docker compose up -d    # Postgres + Redis
pytest
ruff check .
mypy src tests
```

## Repo layout

See `docs/DESIGN.md` §9. Bounded contexts live under `src/testgen/`: `ingestion`, `knowledge`, `generation`, `traceability`, `compliance`, `integrations`, `api`, `ui`, `worker`, `platform`.
