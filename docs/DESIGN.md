# Design Document — Automatic Test Case Generation AI

Status: **Design locked, approved for build.** This is the single source of truth for the system design. If a chat session restarts, read this file (and `PROGRESS.md` next to it) before doing anything else.

---

## 1. Problem Statement

Healthcare QA teams manually convert requirements documents (PDF/Word/XML specs) into test cases, then must prove requirement-to-test traceability for FDA / IEC 62304 / ISO 9001 / ISO 13485 / ISO 27001 audits. This is slow and doesn't scale. The system automates the conversion while keeping every generated artifact traceable, compliant, and gated by human sign-off — because fully autonomous test generation for FDA-regulated software is not something a real healthcare company could actually deploy.

**Goal:** ingest requirements in multiple formats → generate compliant, structured test cases (+ synthetic test data) → maintain full requirement-to-test traceability → sync to existing enterprise ALM tools (Jira first, live).

**This is a portfolio build for a senior/staff engineering interview** — built to production-grade standards, not a demo, but honestly scoped: local-first, real Gemini calls, real Jira integration, cloud deployment expressed as working IaC rather than an applied AWS account.

---

## 2. End-to-End Flow

```
Requirements → Understanding → Regulatory Grounding → Test Generation
   → Compliance Validation → Human Approval → [Traceability locked + Audit entry]
   → Enterprise ALM sync (Jira)
```

Traceability (requirement ↔ test case link) is created continuously from the moment a test case is drafted, but only becomes an official, immutable, audited link at the Human Approval step. Nothing reaches ALM sync without a named human approval on record.

---

## 3. Multi-Agent Architecture

Each stage is a distinct agent — its own prompt/role and scoped tools — not one giant prompt. Orchestrated as a **LangGraph `StateGraph` with a fixed, deterministic topology** (not a free-form AutoGen-style autonomous conversation), because in an FDA-audit context the control flow itself must be inspectable and reproducible. The only bounded non-determinism is the Compliance Critic → Test Case Generator retry loop (max N attempts) and the Regulatory Researcher's own retrieval loop (it can re-query the vector store a few times if the first pass is insufficient).

| Agent | Role | Tools |
|---|---|---|
| **Requirement Analyst** | Extracts discrete requirements from parsed source text, disambiguates, classifies IEC 62304 software safety class (A/B/C) | requirement-parser, ontology lookup |
| **Regulatory Researcher** | ReAct-style — iteratively queries the vector store for relevant FDA/IEC/ISO/GDPR clauses until it has sufficient grounding | Milvus vector-search, clause-lookup |
| **Test Strategist** | Plan-and-Execute style — decides which test *types* are needed (functional, negative, boundary, safety-critical, performance, security, privacy, data-driven) based on requirement + safety class | none — plans over Analyst + Researcher output |
| **Test Case Generator** | Drafts structured test cases per the strategist's plan, grounded in retrieved clause text | schema-validator |
| **Test Data Synthesizer** | Generates PHI-safe synthetic datasets for data-driven test cases | PHI-redaction (Presidio) |
| **Compliance Critic** | Reflection agent — re-retrieves clause text independently and checks the draft against it; returns specific revision feedback on failure (bounded retries) | Milvus vector-search (independent re-check) |
| **Traceability Agent** | Builds/validates requirement↔test-case links, flags coverage gaps | DB read |

RAG happens in **two places**, deliberately: once when drafting (Test Case Generator), once when validating (Compliance Critic re-retrieves independently rather than trusting its own earlier reasoning) — so a miss in the first retrieval pass isn't fatal.

**Human-in-the-loop:** implemented as a genuine LangGraph `interrupt()` — the graph cannot reach the finalize step without a persisted approval record. This is not a UI nicety; it's what makes the audit trail meaningful.

---

## 4. Test Case Taxonomy

Generated per-requirement based on IEC 62304 safety class, not one-size-fits-all:

| Type | Verifies | Applies to |
|---|---|---|
| Functional/positive | Normal expected behavior | All requirements |
| Negative | Invalid input / error conditions | All requirements |
| Boundary | Exact edge values | Requirements with numeric thresholds |
| Safety-critical/failure-mode | Behavior when the safety mechanism itself fails | Class B/C requirements |
| Performance/timing | Time-bound requirements | Requirements with explicit timing |
| Security | Access control, data protection (ISO 27001) | Requirements touching PHI/access |
| Privacy/GDPR | Consent, retention, erasure | Requirements touching personal data |
| Data-driven | Same test across many input values | Requirements with input ranges |

**Structured record per test case** (not free text):
```
Test Case ID · Title · Linked Requirement ID(s) · IEC 62304 Safety Class
Test Type · Preconditions · Numbered Steps · Expected Result · Priority
Regulatory Clause Reference(s) · Generated-by (model + prompt version)
Status (draft/approved/rejected) · Approver + timestamp
```

---

## 5. Data Model (PostgreSQL via SQLAlchemy)

`organizations`, `users`, `roles` (RBAC) · `projects` · `source_documents` (file + checksum + storage key + version) · `requirements` (with source span for traceability) · `test_cases` (+ structured steps) · `test_datasets` · `traceability_links` · `compliance_mappings` (artifact ↔ standard ↔ clause ↔ rationale) · `audit_log` (append-only, hash-chained — each row hashes the previous row, for Part 11 tamper-evidence) · `alm_sync_records` · `llm_generation_runs` (model, prompt version, tokens, cost, latency, eval score).

SQLAlchemy is the ORM/translation layer, not the database — chosen so the DB engine itself (Postgres now) is a connection-string-level decision, not baked into every query.

---

## 6. Bounded Contexts (hexagonal — ports & adapters for anything external)

```
ingestion      — PDF/DOCX/ReqIF/XML/Markdown → normalized Requirement objects
knowledge      — embeddings + VectorStorePort (Milvus) + seeded regulatory corpus
generation     — the LangGraph multi-agent pipeline (Section 3)
traceability   — requirement↔test links, RTM generation, coverage analysis
compliance     — PHI/PII redaction (Presidio), clause mapping, GDPR data-subject rights
integrations   — ALMPort; Jira adapter (live), Azure DevOps + Polarion (contract-tested vs fixtures)
api            — FastAPI, versioned, OAuth2/JWT + RBAC, multi-tenant
ui             — Streamlit app: upload, job status, human review/approval screen, RTM view, audit view
worker         — Celery + Redis for long-running generation jobs
platform       — config, logging/tracing, DB, secrets, LLM cost/eval tracking
```

**Streamlit UI is the primary human interface**, including the actual human-in-the-loop approval screen (Section 3) — a QA reviewer sees pending generated test cases and approves/edits/rejects them there. It talks to the FastAPI backend only; no business logic lives in the UI layer.

---

## 7. Tech Stack (final)

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11 | |
| API | FastAPI | |
| UI | **Streamlit** | fast, Python-native, realistic fit for an internal enterprise QA tool; also hosts the human-approval screen |
| ORM | SQLAlchemy 2.0 + Alembic | DB-portable |
| Database | **PostgreSQL** | standard, reliable, trivial to run locally; Oracle possible later via connection change only |
| LLM | **Gemini** (real API key available) | `gemini-2.0-flash` default (cost/latency), `gemini-1.5-pro` as config option |
| Orchestration | LangGraph + LangChain | deterministic multi-agent topology (Section 3) |
| Vector store | **Milvus** — `milvus-lite` (embedded) for local dev, full Milvus standalone for prod on EC2 | self-hosted → data never leaves own infra (GDPR story) |
| Task queue | Celery + Redis | background processing for slow LLM jobs |
| Object storage | Local filesystem (dev) / S3 (prod), behind `StoragePort` | avoids needing MinIO locally |
| Compliance | Presidio | PHI/PII redaction before any text reaches Gemini |
| Cloud compute | **EC2** (not EKS) | matches resume, far less infra to build/operate |
| IaC | Terraform (VPC/EC2/S3/ECR/Secrets Manager/IAM — no K8s) | written to standard, not applied (no AWS account required to run locally) |
| CI/CD | GitHub Actions | lint/type-check/test/security-scan/build/push |
| Observability | structlog + OTel SDK instrumentation, no local Grafana/Jaeger stack | prod can point OTLP export at CloudWatch |

**Local dev footprint:** just Postgres + Redis + API + worker (+ Streamlit) containers. Milvus Lite is embedded (no extra container). No AWS, no Oracle, no Kubernetes required to run and demo the whole system.

---

## 8. Known Constraints (stated explicitly, not discovered mid-build)

- No live Azure DevOps or Polarion tenant available — those adapters are built to documented APIs and contract-tested against recorded fixtures. Jira **is** live (free Jira Cloud tier).
- Terraform/EC2 IaC is written to a real standard but not `terraform apply`'d — no AWS account required for local development or demo.
- This is a solo portfolio build, not a production system with real users at scale — present it that way in the interview.

---

## 9. Repo Layout

```
docs/                        # this file, PROGRESS.md, ADRs, compliance mapping docs
src/ingestion/ src/knowledge/ src/generation/ src/traceability/
src/compliance/ src/integrations/ src/api/ src/ui/ src/worker/ src/platform/
tests/unit/ tests/integration/ tests/contract/ tests/eval/
infra/docker/ infra/terraform/
.github/workflows/
alembic/
scripts/
docker-compose.yml
pyproject.toml
```

---

## 10. Verification Plan

`docker-compose up` → Postgres, Redis, API, worker, Streamlit UI running. Upload a sample healthcare requirements doc through the Streamlit UI → job runs in background → review/approve generated test cases in the UI → confirm RTM + audit log + real Jira issue creation. `pytest` (unit/integration/contract/eval) green, `ruff`/`mypy` clean.
