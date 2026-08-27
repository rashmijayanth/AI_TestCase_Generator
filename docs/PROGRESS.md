# PROGRESS.md — Build Status

> If resuming this project in a new session: read `docs/DESIGN.md` first (locked source of truth for *what* to build), then this file (tracks *how far we've gotten* and *what to do next*). Don't re-derive anything below by re-reading the whole codebase — it's kept current on purpose.

**Next Action:** Begin Phase 2 (ingestion). Build `testgen.ingestion`: parsers for PDF (`pypdf`), DOCX (`python-docx`), XML/ReqIF (`lxml`), and Markdown (`markdown-it-py`) that normalize into `Requirement` rows (already modeled in Phase 1) with `source_span_start`/`source_span_end` populated for traceability. Needs the `ingestion` extra installed (`pip install -e ".[dev,db,ingestion]"`). A `StoragePort` (local filesystem for dev, per DESIGN.md §7) for storing the uploaded `SourceDocument` file behind `storage_key` belongs here too, or could be split into its own `platform.storage` module if it turns out multiple contexts need it — decide when writing it, not before.

---

## Phase Status

| # | Phase | Status | Notes |
|---|-------|--------|-------|
| 0 | Scaffolding | Done (2026-08-27) | Repo skeleton, tooling, CI, docker-compose (Postgres+Redis) |
| 1 | Domain / platform | Done (2026-08-27) | Config, logging, tracing, full SQLAlchemy schema (13 tables), Alembic, hash-chained audit log |
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

- **2026-08-27** — Fresh restart, this repo. A previous implementation attempt lives at a sibling path, `Automatic_TestCase_Generation_AI/Automatic_TestCase_Generation_AI/` (different folder, same machine), and reached Phase 7 (API/worker) before hitting a bad loop of repeated errors/edits. Verified via `git log`/`git status` in that directory: `git init` had been run but there were zero commits, only untracked files — so nothing was actually lost by abandoning it. That directory is left on disk, untouched, and not used going forward. `docs/DESIGN.md` in *this* repo was copied verbatim from that project's design doc, which remains the single source of truth. The new repo directory (`AI_TestCase_Generator/AI_TestCase_Generator`) was already a bare, empty `git init` with no commits — confirmed genuinely blank before building on it. It also has a GitHub remote configured (`origin` → `github.com/rashmijayanth/AI_TestCase_Generator`) with no push yet made from this repo.
- **2026-08-27** — User asked to complete the whole project autonomously, phase-gated but without stopping to ask between phases (previous session had to be manually stopped after hitting ~70% context usage). Proceeding phase-by-phase on that basis; each phase still ends in a green, committed checkpoint so a future session (or a context-compaction event in this one) can resume cleanly from this file alone.

---

## Key Decisions Log

Decisions made while executing DESIGN.md that aren't spelled out verbatim in it, but are consistent with it:

1. **Root package name: `testgen`**, at `src/testgen/`. DESIGN.md §9 shows bounded contexts directly under `src/` (e.g. `src/platform/`); a top-level `platform` module would shadow Python's stdlib `platform`. Import path is `testgen.platform`, `testgen.ingestion`, etc. — bounded-context responsibilities unchanged from §6.
2. **Dependency declaration vs. installation.** Full §7 tech stack is declared in `pyproject.toml` as optional-dependency extras; only what a phase actually imports gets installed (`dev` in Phase 0; `+db,+observability` added in Phase 1). Avoids resolving/installing unused heavy deps early.
3. **Package/build backend: hatchling**, `src`-layout. Editable install confirmed working both phases.
4. **`docker-compose.yml` grows incrementally** — `postgres`+`redis` from Phase 0; `api`/`worker`/`ui` added once their Dockerfiles exist (Infra phase); a Milvus service added in Phase 3 if needed (see risk note below).
5. **Risk flagged, not yet resolved: `milvus-lite` on Windows.** Historically Linux/macOS-only wheels; this machine is Windows. **Verify at the start of Phase 3** by attempting the install. Fallback: Milvus standalone via docker-compose (Docker Desktop 28.3.2 confirmed installed) — same self-hosted property DESIGN.md §7 wants, just containerized instead of embedded.
6. **Domain model (Phase 1): all 13 tables from DESIGN.md §5 built now**, not spread across later phases, because they're the shared substrate every other phase writes to. Ownership split by bounded context onto one shared `Base`: `platform` owns `organizations`/`users`/`roles`/`user_roles`/`projects`/`audit_log` (cross-cutting entities); `ingestion` owns `source_documents`/`requirements`; `generation` owns `test_cases`/`test_datasets`/`llm_generation_runs`; `traceability` owns `traceability_links`; `compliance` owns `compliance_mappings`; `integrations` owns `alm_sync_records`. Shared enums live in `platform/enums.py` (as `enum.StrEnum`, Python 3.11+) to avoid circular imports between contexts that both reference e.g. `SafetyClass`.
7. **`JSON`, not Postgres `JSONB`**, for all JSON columns (`test_cases.steps`, `test_datasets.data`, `audit_log.payload`). DESIGN.md §5 explicitly wants SQLAlchemy to keep the DB engine "a connection-string-level decision" — `JSONB` is a Postgres-only optimization (indexing/containment queries) that would quietly compromise that portability. Trade-off is deliberate and one-directional: moving to a DB with real JSONB-equivalent support later just needs the column type changed, not a data model rethink.
8. **Enums stored as `native_enum=False`** (varchar + CHECK constraint) rather than native Postgres `ENUM` types. Native Postgres enums need `ALTER TYPE ... ADD VALUE` (can't run inside a transaction in older Postgres, awkward with Alembic autogenerate) every time the test-type/status vocabulary changes — likely, since this taxonomy (DESIGN.md §4) may grow. Varchar+CHECK is a plain `ALTER TABLE` migration instead.
9. **Audit hash chain is application-level** (`platform/audit.py`), not a DB trigger: `record_event()` reads the last row with `SELECT ... FOR UPDATE` (serializes concurrent appends), computes `sha256(prev_hash|action|entity_type|entity_id|canonical_json(payload))`, and inserts. `verify_chain()` walks the table and recomputes every hash. Chose application-level over a Postgres trigger/stored-procedure for testability (see `tests/integration/test_audit_hash_chain.py`, which tampers with a row directly via SQL and confirms `verify_chain` catches it) and because the hashing logic stays in the same language/codebase as everything else — a legitimate FDA-Part-11-style tamper-evidence property, verified for real rather than assumed.
10. **`llm_generation_runs.cost_usd` is `Float`, not `Numeric`/`Decimal`.** Cost tracking here is for observability/dashboards, not billing reconciliation — approximate is fine, and it avoids threading `Decimal` typing through the codebase.
11. **Sync SQLAlchemy, not async.** Celery workers are naturally sync; keeping the API's DB layer sync too avoids mixing async/sync session patterns across the worker/API boundary. Fine at this project's scale (portfolio build, not high-concurrency production).
12. **Local username/password auth implied by `users.hashed_password`.** DESIGN.md §7 says "OAuth2/JWT + RBAC" without naming an external IdP, so Phase 7 (API) will implement FastAPI's standard OAuth2-password-flow + self-issued JWTs rather than integrating a third-party identity provider — simplest thing that satisfies the stated requirement.
13. **pytest `python_classes = ["*Tests"]`** (suffix, not prefix). This domain's own vocabulary is full of `Test*`-prefixed names (`TestCase`, `TestType`, `TestPriority`, `TestCaseStatus`, and per DESIGN.md §3, agent names like "Test Strategist") that collide with pytest's default `Test*` class-collection pattern. Fixed once, globally, rather than adding `__test__ = False` to every such class as the codebase grows.
14. **`alembic/versions/` excluded from ruff's lint scope** (`extend-exclude` in `pyproject.toml`). Alembic's autogenerate template doesn't emit ruff-modern-style code (`Union[]` instead of `X | Y`, its own import order) and there's no value in hand-fixing that boilerplate on every future migration. `alembic/env.py` itself is hand-written wiring code and stays fully linted/typed.

---

## Environment (this machine)

- Windows 11, Python 3.11.3, pip 26.2.1, git 2.55.0, Docker 28.3.2 — all confirmed present.
- No `uv` installed; using stdlib `venv` + `pip`. Venv at `.venv/` (gitignored). Bootstrap script: `scripts/setup_dev.ps1`.
- Local Postgres/Redis running via `docker compose up -d postgres redis` (containers: `ai_testcase_generator-postgres-1`, `ai_testcase_generator-redis-1`).

---

## Phase 1 Verification (2026-08-27)

All green:

- `pip install -e ".[dev,db,observability]"` — clean, no conflicts (sqlalchemy 2.0.52, alembic 1.19.1, psycopg 3.3.4, structlog 26.1.0, opentelemetry-sdk 1.44.0)
- `alembic revision --autogenerate -m "initial schema"` — detected all 13 tables correctly on the first real attempt (after the datetime fix below); reviewed the generated DDL by hand before applying
- `alembic upgrade head` against the live Postgres container — confirmed via `\dt`: all 13 domain tables + `alembic_version` present
- `ruff format .` / `ruff check .` — clean
- `mypy src tests` (strict) — 0 issues, 36 source files
- `pytest --cov=testgen` — **13 passed, 0 warnings**, 86% coverage. `platform/logging.py` and `platform/tracing.py` are at 0% — deliberately deferred: they're thin config wrappers that only make sense to exercise once something real wires them up (FastAPI startup in the API phase), not in isolation.

**Real bugs hit + fixes this phase:**

1. First-draft models produced three timezone-*naive* `DateTime` columns (`TestCase.approved_at`, `ALMSyncRecord.last_synced_at`, `TraceabilityLink.locked_at`) — everywhere else used `DateTime(timezone=True)` via the shared mixins, but these three were hand-added without it. Caught by reading the autogenerated migration before applying it (not by a failing test) — fixed the models, deleted the migration, regenerated it.
2. `ruff check` flagged real issues on first run: import-sort order in several files, and `UP042` (prefer `enum.StrEnum` over `class X(str, enum.Enum)`, available since we're pinned to Python 3.11). Adopted `StrEnum` across `platform/enums.py` — a genuine improvement, not just a lint-silencer.
3. `mypy --strict` failed on `Settings(_env_file=None)` in the config tests — pydantic-settings' dunder init kwargs aren't in the type stub mypy sees. Rather than suppress with `type: ignore`, reworked the tests to use `monkeypatch.chdir(tmp_path)` so `Settings()` is called normally with no ambient `.env` — cleaner test design, not just a typing workaround.
4. `mypy --strict` also failed on `logging.get_logger`: `structlog.get_logger()` types as returning `Any`. Fixed with an explicit `cast(structlog.stdlib.BoundLogger, ...)`, matching structlog's own documented pattern for use under strict mypy.
5. `pytest` tried to collect `TestCase`, `TestDataset`, `TestType`, `TestPriority`, `TestCaseStatus` as test classes (pytest's default `Test*` collection pattern colliding with this domain's own vocabulary) and warned that each "cannot collect... because it has a `__init__` constructor." Fixed globally via `python_classes = ["*Tests"]` in pytest config (see Decision 13) rather than patching every current and future colliding class.
6. A real, if minor, test-fixture bug: `tests/integration/test_db_models.py::test_compliance_mapping_requires_exactly_one_artifact` deliberately triggers a flush-time `IntegrityError`. SQLAlchemy responds to that by auto-rolling-back the connection-bound transaction internally — which is the *same* transaction object the `db_session` fixture's `finally` block was unconditionally calling `.rollback()` on again, producing `SAWarning: transaction already deassociated from connection`. Fixed with an `if transaction.is_active:` guard in `tests/integration/conftest.py` before calling rollback in teardown.

**Committed:** yes — see git log.
