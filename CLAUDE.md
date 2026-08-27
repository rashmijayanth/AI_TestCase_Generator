# CLAUDE.md

Automatic Test Case Generation AI — converts healthcare software requirements into compliant, traceable test cases (FDA / IEC 62304 / ISO 9001 / ISO 13485 / ISO 27001), with human-approved traceability and live Jira sync.

**Before writing any code, read [docs/DESIGN.md](docs/DESIGN.md) in full** — it is the locked source of truth for architecture, agent roles, data model, and tech stack. Do not re-litigate decisions made there. Then read [docs/PROGRESS.md](docs/PROGRESS.md) for current phase status, the decision log, and the "Next Action" line.

## Architecture at a glance

```
Requirements → Understanding → Regulatory Grounding → Test Generation
   → Compliance Validation → Human Approval → [Traceability locked + Audit entry] → Jira sync
```

A LangGraph `StateGraph` (fixed, deterministic topology — not a free-form agent conversation) orchestrates seven agents: Requirement Analyst, Regulatory Researcher, Test Strategist, Test Case Generator, Test Data Synthesizer, Compliance Critic, Traceability Agent — each with its own scoped role/tools. RAG runs twice (draft + independent re-check by the Critic). Nothing reaches ALM sync without a persisted human-approval record (a genuine LangGraph `interrupt()`).

Bounded contexts (hexagonal, ports & adapters at the edges), each under `src/testgen/`: `ingestion`, `knowledge`, `generation`, `traceability`, `compliance`, `integrations`, `api`, `ui`, `worker`, `platform`.

Stack: Python 3.11 · FastAPI · Streamlit (incl. the human-approval screen) · SQLAlchemy 2.0 + Alembic · PostgreSQL · Gemini · LangGraph/LangChain · Milvus (embedded lite locally / standalone in prod) · Celery + Redis · Presidio (PHI redaction) · Terraform (written, not applied) · GitHub Actions.

## Workflow rules for this repo

- Build one phase at a time (see the status table in `docs/PROGRESS.md`). After each phase: `ruff check .`, `mypy src tests`, `pytest` must all be green before moving to the next phase.
- Update `docs/PROGRESS.md` (status table + decision log + "Next Action" line) at the end of every phase — that's how a future session resumes without re-reading everything.
- Commit after each phase is verified green, so there's always a clean rollback point.
- This is a solo portfolio build for a staff/principal-level interview, not a production system with real users — see DESIGN.md §1 and §8.
