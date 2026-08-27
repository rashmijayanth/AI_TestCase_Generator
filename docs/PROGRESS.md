# PROGRESS.md — Build Status

> If resuming this project in a new session: read `docs/DESIGN.md` first (locked source of truth for *what* to build), then this file (tracks *how far we've gotten* and *what to do next*). Don't re-derive anything below by re-reading the whole codebase — it's kept current on purpose.

**Next Action:** Begin Phase 1 (domain/platform). Implement `testgen.platform`: pydantic-settings `Settings` (reading `.env`, mirroring `.env.example`), structlog configuration, SQLAlchemy declarative base + engine/session factory, and `alembic init` wired against real models for the tables in DESIGN.md §5 (start with `organizations`, `users`, `roles`, `projects`). Bring up `postgres`/`redis` via `docker compose up -d` first and point the Alembic env at the local Postgres container.

---

## Phase Status

| # | Phase | Status | Notes |
|---|-------|--------|-------|
| 0 | Scaffolding | Done (2026-08-27) | Repo skeleton, tooling, CI, docker-compose (Postgres+Redis) |
| 1 | Domain / platform | Not started | Config, logging, DB base, initial Alembic migration |
| 2 | Ingestion | Not started | PDF/DOCX/ReqIF/XML/Markdown → Requirement objects |
| 3 | Knowledge / RAG | Not started | Milvus + regulatory corpus — see risk note below |
| 4 | Generation (multi-agent) | Not started | LangGraph StateGraph, 7 agents |
| 5 | Traceability / compliance | Not started | RTM, coverage gaps, Presidio redaction, GDPR rights |
| 6 | Integrations | Not started | Jira (live), Azure DevOps + Polarion (contract-tested) |
| 7 | API / worker | Not started | **Previous attempt failed here** — see History |
| 8 | UI | Not started | Streamlit, incl. human-approval screen |
| 9 | Infra | Not started | Terraform (written, not applied); Dockerfiles for api/worker/ui |
| 10 | Docs | Not started | ADRs, compliance mapping docs |
| 11 | Verification | Not started | Full `docker-compose up` walkthrough per DESIGN.md §10 |

---

## History

- **2026-08-27** — Fresh restart, this repo. A previous implementation attempt lives at a sibling path, `Automatic_TestCase_Generation_AI/Automatic_TestCase_Generation_AI/` (different folder, same machine), and reached Phase 7 (API/worker) before hitting a bad loop of repeated errors/edits. Verified via `git log`/`git status` in that directory: `git init` had been run but there were zero commits, only untracked files — so nothing was actually lost by abandoning it. That directory is left on disk, untouched, and not used going forward. `docs/DESIGN.md` in *this* repo was copied verbatim from that project's design doc, which remains the single source of truth. The new repo directory (`AI_TestCase_Generator/AI_TestCase_Generator`) was already a bare, empty `git init` with no commits — confirmed genuinely blank before building on it.

---

## Key Decisions Log

Decisions made while executing DESIGN.md that aren't spelled out verbatim in it, but are consistent with it (packaging/tooling mechanics, not architecture):

1. **Root package name: `testgen`**, at `src/testgen/`. DESIGN.md §9 shows bounded contexts directly under `src/` (e.g. `src/platform/`). A top-level module literally named `platform` would shadow Python's stdlib `platform` module the moment anything did `import platform`, so all ten bounded contexts are nested one level under a single installable root package instead: `src/testgen/platform/`, `src/testgen/ingestion/`, etc. Import path becomes `testgen.platform`, `testgen.ingestion`, ... — bounded-context boundaries and responsibilities are unchanged from §6.
2. **Dependency declaration vs. installation.** `pyproject.toml` declares the *full* tech stack from DESIGN.md §7 up front, grouped into optional-dependency extras (`api`, `db`, `llm`, `vectorstore`, `queue`, `ingestion`, `compliance`, `ui`, `observability`, `integrations`, plus an `all` convenience group) — so the target dependency surface is documented now rather than discovered piecemeal. Only `pydantic`/`pydantic-settings` are base (needed almost immediately, in Phase 1) and only the `dev` extra (ruff, mypy, pytest, pytest-asyncio, pytest-cov, pre-commit, faker, types-redis) is actually installed in Phase 0 — Phase 0's code doesn't touch FastAPI/LangGraph/Milvus/Presidio/etc. yet. Each later phase installs the extra(s) it needs when it starts writing code against them (e.g. Phase 1 will add `pip install -e ".[dev,db]"`). Avoids resolving/installing heavy ML/infra dependencies (and hitting any platform-specific wheel issues — see Milvus note below) before there's code to exercise them.
3. **`alembic/` not yet initialized.** DESIGN.md §9 lists it at repo root, but `alembic init` wires a migration env against real SQLAlchemy models, which don't exist until Phase 1. An empty/half-wired `alembic/` now would be misleading scaffolding. Deferred to Phase 1 (see Next Action above).
4. **`docker-compose.yml` in Phase 0 has only `postgres` + `redis`.** `api`/`worker`/`ui` need Dockerfiles that don't exist yet (those land in the Infra phase per the build-phase ordering the user specified, which puts `infra` near the end, after UI). Local dev services are added to compose incrementally as each phase produces something runnable. `docker compose config` validated clean.
5. **Risk flagged, not yet resolved: `milvus-lite` on Windows.** DESIGN.md §7 assumes the embedded `milvus-lite` needs "no extra container" for local dev. `milvus-lite` has historically shipped Linux/macOS wheels only, not Windows — and this machine is Windows (win32). **To verify at the start of Phase 3** (Knowledge/RAG) by actually attempting the install. Fallback if unavailable: run Milvus standalone as an extra `docker-compose` service (Docker Desktop 28.3.2 is already confirmed installed on this machine) — preserves the "self-hosted, data never leaves own infra" property DESIGN.md §7 cares about, just containerized instead of embedded-in-process. Only changes the *local dev footprint* line in §7, not the architecture.
6. **Package/build backend: hatchling**, `src`-layout, `packages = ["src/testgen"]`. Chosen over setuptools for simpler pyproject-only config (no `setup.py`/`setup.cfg`). Editable install confirmed working (see Verification below).

---

## Environment (this machine)

- Windows 11, Python 3.11.3, pip 26.2.1, git 2.55.0, Docker 28.3.2 — all confirmed present.
- No `uv` installed; using stdlib `venv` + `pip`. Venv at `.venv/` (gitignored). Bootstrap script: `scripts/setup_dev.ps1`.

---

## Phase 0 Verification (2026-08-27)

All green:

- `pip install -e ".[dev]"` — clean install, no resolution conflicts (pydantic 2.13.4, mypy 2.3.1, ruff 0.16.4, pytest 9.1.1, etc.)
- `ruff format .` — 22 files, no changes needed
- `ruff check .` — all checks passed
- `mypy src tests` (strict mode) — no issues in 17 source files
- `pytest --cov=testgen` — 3 passed, 100% coverage (scaffold-only smoke tests: Python version, package importability, all 10 bounded-context packages importable and docstringed)
- `docker compose config` — `docker-compose.yml` syntax valid

**Real bug hit + fix:** first draft of `tests/unit/test_scaffolding.py` used `@pytest.mark.unit` without importing `pytest` — caught on self-review before running any check, fixed by adding `import pytest`. No red test/lint/type-check runs in this phase; noted here for honesty about the process, not because a gate failed.

**Committed:** yes — see git log for the Phase 0 commit.
