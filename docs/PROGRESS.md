# PROGRESS.md — Build Status

> If resuming this project in a new session: read `docs/DESIGN.md` first (locked source of truth for *what* to build), then this file (tracks *how far we've gotten* and *what to do next*). Don't re-derive anything below by re-reading the whole codebase — it's kept current on purpose.

**Next Action:** None — all 11 phases are done; this was the last one. The system is built, containerized, documented, and verified as thoroughly as this environment honestly allows (see Phase 11 Verification below for exactly what "as thoroughly as this environment allows" means, including a real, live-caught bug that would have shipped broken without it). If a future session picks this back up, the only *genuinely* remaining work is closing the two standing "untested-live" gaps this file has carried since Phase 3/6 — both need something this environment doesn't have, not more code: (1) a real `GEMINI_API_KEY`, to confirm `GeminiEmbedder`/`ChatGoogleGenerativeAI` work against the live API and to finally write real tests into the still-empty `tests/eval/` (Decision 63); (2) real Jira Cloud credentials, to confirm `JiraAdapter`'s live sync path beyond its current "constructed correctly, never actually called" status (Decision 35). Everything else that could be verified without live third-party credentials has been.

---

## Phase Status

| # | Phase | Status | Notes |
|---|-------|--------|-------|
| 0 | Scaffolding | Done (2026-08-27) | Repo skeleton, tooling, CI, docker-compose (Postgres+Redis) |
| 1 | Domain / platform | Done (2026-08-27) | Config, logging, tracing, full SQLAlchemy schema (13 tables), Alembic, hash-chained audit log |
| 2 | Ingestion | Done (2026-08-27) | 5 format parsers, deterministic requirement splitter, StoragePort, ingest_document() |
| 3 | Knowledge / RAG | Done (2026-08-27) | Milvus (confirmed working on Windows), seeded corpus, Gemini embeddings (untested live) |
| 4 | Generation (multi-agent) | Done (2026-08-27) | LangGraph StateGraph, 7 agents, retry loop, retrieval loop, human interrupt — all untested-live only on the real Gemini call itself |
| 5 | Traceability / compliance | Done (2026-08-27) | Link locking + audit, coverage gaps, RTM, Presidio (real, verified), GDPR rights |
| 6 | Integrations | Done (2026-08-27) | ALMPort, live Jira adapter (untested-live), ADO+Polarion (contract-tested), sync service |
| 7 | API / worker | Done (2026-08-27) | FastAPI (auth/RBAC/projects/documents/requirements/traceability/audit), Celery worker, persistent checkpointer, orchestration layer. The phase the previous attempt failed on (see History) — this time: 114 tests, 96% cov, 0 red runs left unresolved |
| 8 | UI | Done (2026-08-27) | Streamlit (4 pages incl. human-approval screen), live-verified end-to-end in a real browser against a real API+Postgres — 25 new tests, 139 total, 91% cov |
| 9 | Infra | Done (2026-08-27) | Terraform (validated, not applied); Dockerfiles for api/worker/ui — all 3 built and run for real via `docker compose up` |
| 10 | Docs | Done (2026-08-27) | 4 ADRs (`docs/adr/`), compliance mapping doc (`docs/compliance/mapping.md`) covering all 18 seeded clauses + GDPR rights |
| 11 | Verification | Done (2026-08-27) | Full `docker-compose up` walkthrough per DESIGN.md §10, live in a real browser against real containers — found and fixed 2 real bugs invisible to every prior phase (Decisions 61, 62), incl. one that meant real background generation had never actually worked |

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
5. **Risk resolved (Phase 3): `milvus-lite` on Windows.** DESIGN.md §7 was written assuming `milvus-lite` might be Linux/macOS-only. Tested directly on this machine: `pip install milvus-lite` (v3.2.1) pulled a real `win_amd64` wheel, and a full create-collection/insert/search/drop smoke test via `pymilvus.MilvusClient` worked end-to-end. No fallback needed — DESIGN.md §7's "local dev footprint... Milvus Lite is embedded (no extra container)" holds as originally written, on this machine at least.
6. **Domain model (Phase 1): all 13 tables from DESIGN.md §5 built now**, not spread across later phases, because they're the shared substrate every other phase writes to. Ownership split by bounded context onto one shared `Base`: `platform` owns `organizations`/`users`/`roles`/`user_roles`/`projects`/`audit_log` (cross-cutting entities); `ingestion` owns `source_documents`/`requirements`; `generation` owns `test_cases`/`test_datasets`/`llm_generation_runs`; `traceability` owns `traceability_links`; `compliance` owns `compliance_mappings`; `integrations` owns `alm_sync_records`. Shared enums live in `platform/enums.py` (as `enum.StrEnum`, Python 3.11+) to avoid circular imports between contexts that both reference e.g. `SafetyClass`.
7. **`JSON`, not Postgres `JSONB`**, for all JSON columns (`test_cases.steps`, `test_datasets.data`, `audit_log.payload`). DESIGN.md §5 explicitly wants SQLAlchemy to keep the DB engine "a connection-string-level decision" — `JSONB` is a Postgres-only optimization (indexing/containment queries) that would quietly compromise that portability. Trade-off is deliberate and one-directional: moving to a DB with real JSONB-equivalent support later just needs the column type changed, not a data model rethink.
8. **Enums stored as `native_enum=False`** (varchar + CHECK constraint) rather than native Postgres `ENUM` types. Native Postgres enums need `ALTER TYPE ... ADD VALUE` (can't run inside a transaction in older Postgres, awkward with Alembic autogenerate) every time the test-type/status vocabulary changes — likely, since this taxonomy (DESIGN.md §4) may grow. Varchar+CHECK is a plain `ALTER TABLE` migration instead.
9. **Audit hash chain is application-level** (`platform/audit.py`), not a DB trigger: `record_event()` reads the last row with `SELECT ... FOR UPDATE` (serializes concurrent appends), computes `sha256(prev_hash|action|entity_type|entity_id|canonical_json(payload))`, and inserts. `verify_chain()` walks the table and recomputes every hash. Chose application-level over a Postgres trigger/stored-procedure for testability (see `tests/integration/test_audit_hash_chain.py`, which tampers with a row directly via SQL and confirms `verify_chain` catches it) and because the hashing logic stays in the same language/codebase as everything else — a legitimate FDA-Part-11-style tamper-evidence property, verified for real rather than assumed.
10. **`llm_generation_runs.cost_usd` is `Float`, not `Numeric`/`Decimal`.** Cost tracking here is for observability/dashboards, not billing reconciliation — approximate is fine, and it avoids threading `Decimal` typing through the codebase.
11. **Sync SQLAlchemy, not async.** Celery workers are naturally sync; keeping the API's DB layer sync too avoids mixing async/sync session patterns across the worker/API boundary. Fine at this project's scale (portfolio build, not high-concurrency production).
12. **Local username/password auth implied by `users.hashed_password`.** DESIGN.md §7 says "OAuth2/JWT + RBAC" without naming an external IdP, so Phase 7 (API) will implement FastAPI's standard OAuth2-password-flow + self-issued JWTs rather than integrating a third-party identity provider — simplest thing that satisfies the stated requirement.
13. **pytest `python_classes = ["*Tests"]`** (suffix, not prefix). This domain's own vocabulary is full of `Test*`-prefixed names (`TestCase`, `TestType`, `TestPriority`, `TestCaseStatus`, and per DESIGN.md §3, agent names like "Test Strategist") that collide with pytest's default `Test*` class-collection pattern. Fixed once, globally, rather than adding `__test__ = False` to every such class as the codebase grows.
14. **`alembic/versions/` excluded from ruff's lint scope** (`extend-exclude` in `pyproject.toml`). Alembic's autogenerate template doesn't emit ruff-modern-style code (`Union[]` instead of `X | Y`, its own import order) and there's no value in hand-fixing that boilerplate on every future migration. `alembic/env.py` itself is hand-written wiring code and stays fully linted/typed.
15. **Ingestion/generation phase boundary**: ingestion (Phase 2) only ever writes `Requirement` rows with `status=EXTRACTED` and `safety_class=None`. DESIGN.md §3 gives the Requirement Analyst agent (Phase 4, LLM-based) the job of "extract[ing] discrete requirements from parsed source text, disambiguat[ing], classif[ying]... safety class" — so ingestion's `requirement_splitter.py` is deliberately mechanical (paragraph + modal-verb regex, no LLM call), producing *candidates* good enough to seed that agent, not final ground truth. `RequirementStatus.CLASSIFIED`/`NEEDS_REVIEW` are set later, by Phase 4.
16. **`StoragePort` lives in `platform`, not `ingestion`.** DESIGN.md §7 calls it out as its own tech-stack layer ("Object storage... behind StoragePort"), not ingestion-specific — later phases (e.g. exporting an RTM, storing synthetic datasets) are plausible future callers too. `LocalFilesystemStorage` implemented now (structural `Protocol`, no explicit inheritance needed); `S3Storage` deliberately raises `NotImplementedError` with a pointer to the Infra phase rather than a fake/partial implementation, since there's no real AWS account to test against (DESIGN.md §8).
17. **ReqIF parser handles the common case, not the full OMG spec.** Extracts `SPEC-OBJECT` → `THE-VALUE` text; no attribute-definition/datatype resolution, no spec-hierarchy tree. ReqIF is one of five supported formats and not the one the interview demo centers on (PDF/DOCX/Jira are) — a real, working, honestly-scoped adapter beats either skipping it or pretending it's spec-complete.
18. **`get_settings()`'s `lru_cache` needs explicit clearing in tests.** Added an autouse `tests/conftest.py` fixture (`get_settings.cache_clear()` before every test) once Phase 2 introduced the first test that depends on `get_settings()`-derived behavior (`get_storage()`). Without it, whichever test happened to call `get_settings()` first in a session would leak its cached instance into every later test — a real, if latent, cross-test correctness bug worth closing now rather than after it causes a flaky failure.
19. **`llm` extra split into `llm` (langgraph/langchain, Phase 4) and `embeddings` (google-genai, Phase 3).** Phase 3 needs Gemini's embedding API but not the multi-agent orchestration libraries yet; splitting the extra keeps "install only what this phase's code imports" (Decision 2) accurate at finer grain.
20. **Milvus's default collection schema requires an int64 primary key, not a string** (confirmed empirically — a string id raises `DataNotMatchException`). Rather than fight the schema, `stable_clause_id()` derives a deterministic positive int64 from `sha256("{standard}:{clause_ref}")`, while `standard`/`clause_ref`/`text` stay as ordinary string fields on the record — keeps upserts idempotent (same clause always maps to the same id) without needing a custom Milvus schema.
21. **Seeded regulatory corpus (18 clauses, 3 per standard) is original, illustrative paraphrasing — not verbatim standard text.** ISO/IEC standards are copyrighted and sold by those bodies; reproducing their actual clause text at length here would be both a copyright problem and not something I have a verified, licensed source for. FDA 21 CFR and the GDPR are public-domain legal text, but entries are still paraphrased rather than quoted for the same "no verified exact source in hand" reason. `clause_ref` values are illustrative, plausible-looking section numbers. A real product would license the official standard text; this corpus exists to demonstrate the RAG mechanism, not to be a compliance-grade clause library.
22. **`GeminiEmbedder` is real code, not live-tested.** No `GEMINI_API_KEY` is available in this environment. Rather than mock it out with a fake that silently "passes," its request/response handling was verified by introspecting the actually-installed `google-genai` 2.20.0 SDK (`genai.Client.__init__`, `Models.embed_content` signature, and the `EmbedContentResponse`/`ContentEmbedding` field names all confirmed directly), and the response-mapping logic (`_extract_vectors`) is unit-tested against a fake object matching that confirmed shape. The one thing that remains genuinely unverified is whether a live call to the real API succeeds end-to-end — **smoke-test this the first time a real `GEMINI_API_KEY` is added to `.env`**. All automated tests run against `DeterministicFakeEmbedder` instead (hash-based, not semantically meaningful — good for proving storage/retrieval plumbing works, not for judging retrieval *quality*).
23. **The iterative "retrieve until sufficient" loop is NOT built in Phase 3.** DESIGN.md §3 assigns that judgment to the Regulatory Researcher agent (ReAct-style) and the Compliance Critic's independent re-check — both Phase 4 concerns. `testgen.knowledge` only exposes the stateless building block (`search_clauses`: embed one query, search once); Phase 4's agents call it repeatedly from their own loop. Building the loop here without an agent to drive it would mean guessing at Phase 4's interface.
24. **Structured LLM output via Gemini's native `response_schema`, not LangChain's `.with_structured_output()`.** `ChatGoogleGenerativeAI` genuinely overrides `bind_tools` (confirmed by introspection), so `.with_structured_output()` *would* work against the real model — but LangChain's standard test doubles (`FakeMessagesListChatModel`, `GenericFakeChatModel`, etc.) don't implement `bind_tools`, so `.with_structured_output()` raises `NotImplementedError` against them (confirmed directly, not assumed). Rather than write a custom fake `BaseChatModel` with tool-call emulation, every agent instead configures `response_mime_type="application/json"` + `response_schema=SomeModel.model_json_schema()` directly (both are real, confirmed fields on `ChatGoogleGenerativeAI`) and parses `.content` with Pydantic — equally real/idiomatic LangChain usage, and trivially testable with a plain `.invoke()` fake.
25. **Enum-like agent output fields are plain `str` in the Pydantic schemas** (`generation/schemas.py`), not the real enums (`testgen.platform.enums`). Whether Gemini's `response_schema` (a constrained JSON-schema dialect) round-trips Pydantic's Enum/Literal schema generation correctly is unverified — no live API access. Keeping these fields as `str` and coercing to the real enum on our side (`SafetyClass(parsed.safety_class.strip().upper())` etc.) means a schema-translation mismatch shows up as a clear, catchable `ValueError` on our side rather than silently-wrong constrained decoding on Gemini's.
26. **`AgentDeps` + `functools.partial` for dependency injection**, not module-level factory calls inside each node. Every node has the signature `(state, *, deps)`; `build_generation_graph` binds `deps` via `partial(node_fn, deps=deps)` when registering nodes. This makes every node directly callable in a unit test (`some_node(state, deps=fake_deps)`) with zero graph/checkpointer machinery — most of Phase 4's tests exercise nodes this way, only the full-graph tests (`tests/integration/test_generation_graph.py`) go through `build_generation_graph` + a real compiled graph.
27. **Test Data Synthesizer sets `phi_redacted=False` unconditionally.** DESIGN.md §3 lists "PHI-redaction (Presidio)" as this agent's tool, but Presidio integration belongs to the `compliance` bounded context (§6), which doesn't exist until Phase 5. Rather than pull a slice of Phase 5 forward, the synthesizer prompt instructs the model to generate obviously-synthetic values (placeholder names, fictitious dates) and the dataset is honestly marked unredacted. **Phase 5 must close this loop** — see this file's Next Action.
28. **Traceability Agent (graph node) does a pure in-memory coverage-gap check only** — planned test types vs. drafted test types, no DB access. DESIGN.md §3 lists "DB read" as this agent's tool and describes it as building/validating links, but a live DB `Session` doesn't belong in LangGraph state (not cleanly serializable, and the checkpointer would try to persist it). Actually persisting `TraceabilityLink` rows + the audit log entry — the real DB write, gated on the human approval decision and the approving user's identity — is the orchestration layer's job once Phase 7 (API/worker) provides a real caller with a real session. Chose this over guessing at LangGraph's `context_schema` dependency-injection mechanics (available in this version, per `StateGraph.__init__`'s signature, but not introspected/verified here) without a live way to confirm it end-to-end.
29. **`InMemorySaver` checkpointer for Phase 4.** Enough to prove the `interrupt()`/resume mechanics work (verified directly — see Verification below) and for this phase's own tests. **Phase 7 must swap in a persistent, Postgres-backed checkpointer** (`langgraph-checkpoint-postgres` or similar) — a real deployment needs a paused human-approval interrupt to survive between the request that triggers generation and the later, separate request where a human actually approves it, which `InMemorySaver` cannot do across process restarts.
30. **LangGraph mechanics (interrupt/resume, conditional-edge retry routing) were verified with a throwaway scratch script before writing any of the real 7 agents.** Paid off directly: the full 7-agent graph worked correctly on the first attempt with zero graph-wiring bugs — the only bug hit this phase (see below) was a naming collision, not a logic error.
31. **Presidio uses `en_core_web_sm`, not the default `en_core_web_lg`.** Verified directly (manual analyze+anonymize smoke test) before writing any code. `en_core_web_sm` is ~13MB vs. ~560MB and installs/loads far faster, at a real accuracy cost — the same smoke test that confirmed PERSON/DATE_TIME/PHONE_NUMBER detection also caught it mislabeling "DOB" as ORGANIZATION. Fine for a portfolio demo; a production deployment handling real PHI at scale should evaluate `en_core_web_lg` or a domain-tuned NER model.
32. **GDPR "right to erasure" is reconciled with the audit log's Part 11 immutability by scrubbing identity fields on the `User` row only, never touching `audit_log`.** These two requirements (erase personal data vs. never alter an audited history) are in genuine tension, and DESIGN.md wants both. The resolution: `audit_log.actor_user_id` is just a UUID foreign key, not personal data by itself — the actual identifying data (email, full_name) lives on `User`, which erasure scrubs to a tombstone value. `verify_chain()` is asserted to still pass immediately after erasure in the test (`test_erase_user_personal_data_scrubs_identity_without_touching_audit_chain`), so this isn't just an argument, it's checked.
33. **`find_coverage_gaps`'s "required test types per safety class" is an explicit, minimal floor** (`_MINIMUM_TYPES_BY_SAFETY_CLASS`: Class A needs functional; B/C also need safety_critical) — not an attempt to replicate the Test Strategist agent's full per-requirement judgment (Phase 4), which reasons over the requirement's actual content (numeric thresholds, timing language) via an LLM call that this deterministic, DB-queryable check can't and shouldn't try to duplicate. It answers a narrower, still-useful question: "did we get at least this much coverage," queryable without re-invoking any LLM.
34. **Closed the Phase 4 TODO**: `generation.agents.data_synthesizer_node` now actually calls `testgen.compliance.redaction.redact_dataset_rows` and sets `phi_redacted=True` truthfully, via a **lazy import** (inside the function, not at module top) — so `testgen.generation.agents` stays importable without the `compliance` extra (presidio + spaCy model) installed, for any caller that never exercises data-driven test cases. The test that exercises this path moved from `tests/unit/test_agents.py` to `tests/integration/test_generation_agents.py` (it now genuinely calls real Presidio, matching Decision 31's "Presidio/Milvus = integration" convention) — the file/marker move is the point, not just updating the assertion from `False` to `True`.
35. **`jira.JIRA`'s constructor contacts the server by default** (`get_server_info=True`, confirmed by introspecting the installed `jira` 3.10.5) — meaning even *constructing* the real client requires live credentials/network, unlike `ChatGoogleGenerativeAI`/`GeminiEmbedder` (Phases 3/4), which construct lazily. So `JiraAdapter` takes an already-built client (`JiraClientPort` — just the one method this adapter calls) rather than being handed a `jira.JIRA` instance to fake; `build_jira_client`/`get_jira_adapter` are the real, network-touching factory functions, kept separate and untested here (same "not live-tested" footing as Gemini).
36. **Azure DevOps and Polarion are hand-built `httpx` REST clients against documented API contracts, not third-party SDKs.** Contract-tested with `httpx.MockTransport` against realistic recorded response fixtures (`tests/contract/`, using the `contract` pytest marker and directory both seeded — unused — back in Phase 0's scaffolding). This is the one pairing in the whole system where "not live-tested" is the **permanent**, intended state (DESIGN.md §8: no tenant will ever be available here), not a temporary gap waiting on a credential like Gemini/Jira.
37. **`sync_test_case` catches any adapter exception and records a FAILED `ALMSyncRecord` rather than letting it propagate.** A failed external sync is data worth keeping (DESIGN.md §5 models `alm_sync_records` with an `error_message` field specifically for this) — the caller can inspect and retry later, rather than the whole operation crashing because Jira/ADO/Polarion was briefly unreachable.
38. **Fixed a real CI gap discovered while adding the `contract` test category**: since Phase 0, CI's pytest step excluded `integration`, `contract`, *and* `eval` — meaning every integration test built across Phases 1–6 (the majority of this project's actual test coverage) had never once run in CI, only locally. Root cause: CI had no Postgres/Redis available at all, and only installed the `dev` extra. Fixed by adding Postgres+Redis as GitHub Actions service containers, installing `[dev,all]` instead of `[dev]`, downloading the spaCy model, running `alembic upgrade head` before tests, and narrowing the exclusion to just `-m "not eval"` — `eval` (LLM-output-quality tests against a real Gemini key) is the only category that genuinely can't run without a secret this repo doesn't have configured. `contract` tests need no service at all (`httpx.MockTransport`), so they were never the problem; they just rode along with the same blanket exclusion.
39. **Persistent, Postgres-backed LangGraph checkpointer (`generation/checkpointer.py`), verified twice**: once with a manual throwaway script (two independent `PostgresSaver` instances against the same container, simulating two separate processes) before writing any wrapper code, and again as a permanent, real automated test (`tests/integration/test_checkpointer.py`) that does the same thing for good. `langgraph-checkpoint-postgres` uses psycopg directly and expects a plain `postgresql://` DSN, not SQLAlchemy's `postgresql+psycopg://` dialect prefix — confirmed directly, handled by `to_psycopg_dsn()`.
40. **`build_readonly_deps()`: a second `AgentDeps` variant, alongside `build_default_deps()`, for anything that builds a compiled graph without executing a node.** Reading a persisted checkpoint (`get_state()`) never runs a node; *resuming past the human_approval interrupt* also never runs a node needing an LLM or embedder (only `human_approval` and `traceability_agent`, both pure) — so `generation-status`, `pending-approval`, *and* `approve`/`reject` all use read-only deps, not `build_default_deps()`. This means none of the API's core lifecycle needs a real `GEMINI_API_KEY` in this environment; only the Celery worker's actual generation run does. Every method on the read-only stand-ins (`_UnreachableChatModel` — a genuine `BaseChatModel` subclass, not a duck-typed stand-in, so `AgentDeps`'s `Callable[..., BaseChatModel]` typing stays honest — plus matching embedder/vector-store stand-ins) raises loudly if that "never actually called" assumption is ever wrong.
41. **RBAC is actually applied, not just built.** `require_roles()` existed after Phase 7's first pass but gated nothing — caught by checking coverage, not by a failing test. `approve`/`reject` (the most consequential actions: DESIGN.md §2 says this is what makes the audit trail meaningful) now require the `ADMIN_ROLE_NAME` role (a new shared constant in `api/deps.py`, replacing a private duplicate in `auth.py`). `register()` is the only role-granting path that exists (auto-grants "admin" to an org's first user), so this is RBAC's mechanism demonstrated on the action that matters most, not a full multi-role admin system — a real limitation, stated plainly rather than glossed over.
42. **Two different test-isolation strategies, used deliberately, not inconsistently.** Most integration tests use the rolled-back `db_session` fixture (Phase 1). But `run_generation_for_requirement`/the worker task reads its Requirement via `session_scope()` — a genuinely separate connection, simulating a real separate worker process — which cannot see uncommitted rows from a different, still-open transaction under Postgres's READ COMMITTED isolation. Tests exercising that boundary (`test_worker_tasks.py`, `test_requirements_api.py`, `test_traceability_audit_api.py`) instead let writes really commit and accept un-rolled-back rows in the local dev Postgres, using unique random org/email values per test to avoid collisions. Documented inline in each affected file, not just here.
43. **`organization_id` threading fix for audit-log multi-tenancy scoping.** `lock_traceability_links_for_requirement` (Phase 5) and `persist_generation_result`'s rejection path never set `AuditLog.organization_id` — meaning the new org-scoped `/audit-log` endpoint would have silently returned nothing for everyone. Caught while building that endpoint, before it ever shipped with the gap; both functions (and all their call sites, including Phase 5's own tests) now take an explicit `organization_id` parameter.
44. **`Requirement.safety_class`/`status` are written back to the Requirement row itself in `persist_generation_result`, not just copied onto the new `TestCase` rows.** The Requirement Analyst agent's classification only ever lived in graph state (Decision 28: no DB session in LangGraph state) — nothing wrote it back to the actual `Requirement` row, so `generate_rtm` (which reads `requirement.safety_class` from the DB) always showed `None`. **Found by a genuinely failing test** (`test_rtm_and_coverage_gaps_after_approval` asserting `row["safety_class"] == "C"`), not by inspection — exactly the kind of gap end-to-end testing across phase boundaries is supposed to catch. Written back on both approval *and* rejection, since classification is meaningful independent of whether the drafted test cases were accepted.
45. **UI structure (Phase 8): `api_client.py` (pure HTTP client, zero Streamlit imports) + `session.py` (`st.session_state` glue) + `components.py` (the one thing every page shares: `call_api`'s error/401 handling) + `app.py` (login/register gate + `st.navigation` shell) + `pages/*.py`.** Pages map to DESIGN.md §6's named views, with one deliberate merge: "job status" and "the human review/approval screen" both live on one `pages/requirements.py`, since status is exactly what gates whether the review UI renders — splitting them would have meant duplicating the project/requirement-picking scaffolding for no real separation of concerns. `pages/projects.py` (upload), `pages/rtm.py`, `pages/audit.py` are each their own file, one per §6 view.
46. **No new backend endpoint added to list "requirements for a project."** Phase 7's API surface never built one. `GET /projects/{id}/rtm` already returns one row per requirement (id, external_ref, text, safety_class, existing test cases) regardless of generation status — reused as-is for the Requirements & Approval page's listing. Phase 8 is scoped to the UI; inventing a new endpoint to make the UI marginally cleaner would have been scope creep across the API/UI boundary DESIGN.md §6 draws deliberately.
47. **Status is fetched on demand (a "Check status" button), not auto-polled.** Streamlit reruns the whole script on any widget interaction; there's no lightweight background-polling primitive in the approved stack (DESIGN.md §7) that fits this cleanly, and auto-polling every requirement on every rerun would mean an API call per requirement per unrelated click anywhere on the page. A manual refresh is honest about the tradeoff rather than faking real-time updates.
48. **`httpx`, not `requests`, for `api_client.py` — added explicitly to the `ui` extra (Decision 2: only what a phase imports gets installed), even though `all` already pulled it in via `integrations`.** Already a project dependency (Phase 6, `dev`), and its `MockTransport`/injectable-`transport` testability matches the ADO/Polarion contract-test pattern (Decision 36) exactly — `ApiClient` takes an optional `transport` so unit tests inject `httpx.MockTransport(handler)` and production uses a real one, with zero conditional logic in the client itself.
49. **Two real bugs found by writing `streamlit.testing.v1.AppTest`-based tests, not by inspection — both now regression-tested:**
    - **Message-after-`rerun()` loss.** `st.success()`/`st.info()` called immediately before `st.rerun()` never reach the browser: `st.rerun()` aborts the current run immediately, discarding whatever was queued for display in that same run. Every affected handler (create-project, approve, reject, the 401/expired-token logout path in `components.py`) now stashes `(kind, text)` in `session_state` and renders+clears it after the rerun. `tests/unit/test_ui_pages.py`'s approve/reject/create-project tests and `test_ui_app.py`'s expired-token test all assert the message is actually present post-rerun, so a regression fails loudly again.
    - **`AppTest.from_function` re-execs the harness's *source text*** (via `inspect.getsourcelines`, confirmed by reading its implementation), not a live closure — a nested `harness()` capturing an outer `render` callable raises `NameError: name 'render' is not defined` when re-exec'd. Fixed by making the harness self-contained (its own imports, page picked by name via `kwargs`), the sanctioned way `args`/`kwargs` are documented to work.
    - Separately (not a bug, a real gotcha worth recording): **importing `testgen.ui.app` directly executes its top-level `main()` once in Streamlit's "bare mode"** (no script-run context) as a side effect of the `import` statement itself, and this corrupts a *later*, real `AppTest.from_file` run of the same file (`st.form` raises "Forms cannot be nested in other forms" on that second run). `tests/unit/test_ui_app.py` never imports `testgen.ui.app` for this reason — `AppTest.from_file` execs the script fresh without going through Python's import system, which is what keeps it safe.
50. **Pre-existing mypy failure fixed in `knowledge/embeddings.py`, unrelated to Phase 8's own code.** `GeminiEmbedder.embed`'s `contents=texts` (`list[str]`) call started failing strict mypy — not a code regression (the file is unmodified since Phase 3) but a `mypy` version drift: `pyproject.toml` pins only `mypy>=1.13` (an open floor, Decision 2's "install only what's needed" logic extended to versions too), and a fresh `pip install` here resolved `mypy` 2.3.1, evidently stricter about generic-list invariance than whatever ran during Phase 3/7. Runtime signature re-confirmed via introspection (`inspect.signature`) to still genuinely accept `list[str]` as one member of `contents`'s real union type — a mypy-only false positive from treating `list[str]` and `list[str | Image | ...]` as unrelated invariant generics. Fixed with one narrow, commented `# type: ignore[arg-type]`, the same "targeted ignore over blanket suppression" precedent as Decision 5. Left the repo genuinely green rather than reporting Phase 8 done against a red baseline.
51. **`ApiClient` defaults to `httpx.HTTPTransport(retries=1)`, found necessary by live browser testing, not by any automated test.** Manually driving the real app (real `uvicorn`, real Postgres, real browser) through the golden path hit `httpx.RemoteProtocolError: Server disconnected without sending a response` on both a document upload and an approve click — confirmed via `uvicorn`'s own access log that the server never received either request at all. Root cause: httpx's client-side `keepalive_expiry` (5s default) races `uvicorn`'s own keep-alive timeout (also 5s default) — a request sent just as a pooled connection goes stale server-side gets reset before the server logs anything. `retries=1` is httpx's own documented mechanism for exactly this class of failure (it only retries the connection-establishment/send phase, safe here since the server demonstrably never processed the failed attempt). Stated honestly: this is local-`uvicorn`-under-interactive-load flakiness, consistent with DESIGN.md §1/§8's "not a production system" framing, not something a Phase 8 code change can fully eliminate — the mitigation reduces but doesn't guarantee-away every occurrence under heavy connection churn (still observed once more, on a different endpoint, after the fix; a fresh browser tab + retry succeeded immediately every time it recurred).
52. **`api_base_url` added to `Settings`** (default `http://localhost:8000`) — the UI is DESIGN.md §6's separate process that only ever talks to the API over HTTP, never imports `testgen.api` directly, so it needs the API's base URL as config, not an in-process app object. `scripts/run_ui.ps1` added alongside it (mirrors `setup_dev.ps1`'s existing convenience-script pattern).
53. **Per-service Dockerfile extras were read off the actual import graph, not guessed.** `generation/agents.py` imports `get_embedder`/`get_vector_store` at module scope (so `embeddings`/`vectorstore` are needed just to *import* `testgen.generation.agents`, even though the API's read-only deps — Decision 40 — never call them for real); `api/routers/requirements.py` imports `testgen.worker.tasks`, which imports `testgen.worker.celery_app` (so the API needs `queue` just to enqueue, never to consume). `compliance` (presidio+spaCy, the heaviest extra) is the one thing genuinely unique to the worker — the API never imports it even transitively, since `data_synthesizer_node`'s `redact_dataset_rows` import is lazy (Decision 34). Confirmed by grepping every relevant file's `^import`/`^from` lines before writing any Dockerfile, the same "verify before writing" discipline as Decisions 22/30/35/39.
54. **`README.md` added to every Dockerfile's builder-stage `COPY`, and `.dockerignore` gained a `!README.md` negation after `*.md`.** hatchling (the build backend, Decision 3) requires the file `pyproject.toml`'s `readme = "README.md"` points at to actually exist when building the wheel — `pip install .` inside the builder stage failed on the very first real `docker build` with `OSError: Readme file does not exist`. `.dockerignore` excludes `*.md` repo-wide (correct — nothing else needs it), so the negation has to come *after* that exclusion in the file, not before (`.dockerignore` rules apply in order — confirmed by testing both orderings directly, not assumed).
55. **`docker-compose.prod.yml` (a separate override file), not a hand-rolled heredoc, swaps `build:` for `image:` in production.** First draft generated the override YAML inline inside `user_data.sh.tftpl` via a bash heredoc — worked, but was needlessly fragile and unlike anything a real ops engineer would recognize. Also confirmed directly (`docker compose config`) that a plain `image: ...` in an override file does *not* remove the base file's `build:` block (both coexist, and compose would build-then-tag rather than pull) — the compose-spec `!reset null` tag is what actually clears it, verified the same way. `infra/docker/docker-compose.prod.yml` is the real, standalone artifact now; `user_data.sh.tftpl` just references it.
56. **Real bug, found only by actually running `docker compose up`, not by writing or reading the Dockerfiles**: `pymilvus` itself reads a real OS environment variable literally named `MILVUS_URI` for its own internal connection default (confirmed by reading `pymilvus.orm.connections`' source after the crash, not before) — colliding with the env var `pydantic-settings` auto-derives from `Settings.milvus_uri`. Both the `api` and `worker` containers crashed at import time (`pymilvus.exceptions.ConnectionConfigException: Illegal uri: [/app/data/milvus_lite.db], expected form 'http[s]://...'`) the moment `MILVUS_URI` became a *real* process environment variable — which `docker-compose.yml`'s `env_file: .env` does, but this app's own `.env`-file loading (via `pydantic-settings`, all of local dev so far) never did. Fixed with `Field(validation_alias="MILVUS_DB_URI")` on `Settings.milvus_uri` — renames the *environment variable* pydantic-settings looks for, not the Python attribute, so every existing `settings.milvus_uri` call site (and every test referencing it) stayed unchanged. `.env.example` and `docker-compose.yml` updated to match; a regression test (`test_milvus_db_uri_env_var_is_read_and_the_colliding_name_is_ignored`) asserts the collision stays inert. This is the kind of bug that is *structurally invisible* to local, non-containerized development and to any test that only loads `.env` files rather than setting real `os.environ` values — exactly why Phase 9's "actually run it" verification step existed.
57. **All 3 containers verified for real via `docker compose up`** (build cache reused from earlier manual `docker build` runs of each Dockerfile) — `api` reached `healthy` (alembic migrations ran, `/health` returned 200), `worker` connected to Redis and logged `celery@... ready`, `ui` served HTTP 200 and passed its own healthcheck. The `ui` service's host port (8501) collided with an unrelated, pre-existing container on this dev machine from a different project — not a defect in `docker-compose.yml` (which correctly claims the standard port) — verified instead via `docker run` against the same compose-built image, joined to the compose network, on an alternate host port.
58. **`docs/adr/` (4 records, Nygard-style Context/Decision/Consequences) holds only the decisions that clear a real bar: significant, not obvious in hindsight, worth a future reader understanding the *reasoning* for.** Everything else stays in this file's own numbered decision log rather than being promoted to an ADR — most of the 57 decisions above are legitimate build-time records, but "why LangGraph fixed-topology + a real `interrupt()`," "why hexagonal ports/adapters," "why an application-level hash chain," and "why `MILVUS_DB_URI`, not `MILVUS_URI`" are the four a new contributor would most need the *argument* for, not just the outcome. Deliberately not one ADR per phase or per file touched — that would just be this decision log with extra ceremony.
59. **`docs/compliance/mapping.md` is a static companion to the *dynamic* `compliance_mappings` table (DESIGN.md §5), not a replacement for it.** The DB table records which clause a specific generated test case actually cited, per run, via the Compliance Critic's real retrieval; this document instead answers "what does this codebase do, structurally, to address clause X" — a fixed backdrop, not per-artifact evidence. Every mapping claim in it was checked against the real code before being written down (e.g. grepped every router for `CurrentUser`/org-scoping rather than asserting "RBAC covers everything" from memory) rather than assumed from having built the features. Carries forward Decision 21's honesty framing explicitly and up front, not just by reference — the corpus's paraphrase-not-verbatim disclaimer is the first thing in the document, not a footnote.
60. **`scripts/seed_corpus.py`** closes the Phase 9 gap: real `get_embedder()`/`get_vector_store()`, calls `seed_regulatory_corpus()` for real, fails loudly (not silently) via `get_embedder()`'s existing `ValueError` if `GEMINI_API_KEY` isn't configured — confirmed live, this environment's standing constraint. Wired into `worker.Dockerfile` (copied in, since that container already has the `embeddings`/`vectorstore` extras and the real env vars) and `user_data.sh.tftpl` (a post-`up` retry loop, idempotent per Decision 20 so it's safe to leave in a boot script). Not run automatically on every worker start — a one-time operational step, invoked explicitly.
61. **Real bug, found only by uploading a real document through the real containerized API, not by writing or reading the Dockerfiles**: both `api` and `worker` run as a non-root user (`app`, uid 1000) but `docker-compose.yml`'s named `appdata` volume mounts at `/app/data` owned by root by default — `ingest_document()`'s first real write crashed with `PermissionError: [Errno 13] '/app/data/storage'`. Fixed with the standard Docker pattern: `RUN mkdir -p /app/data && chown app:app /app/data` *before* `USER app` in both Dockerfiles, so a fresh named volume gets seeded with the right ownership from the image on its first mount (Docker's own documented behavior for empty named volumes). The already-existing, already-broken volume had to be deleted and recreated for the fix to take effect — rebuilding the image alone doesn't retroactively fix ownership on a volume Docker already created.
62. **The single most consequential bug this project has shipped, and the clearest argument for Phase 11 existing at all: `generate_test_cases_task` was never actually registered with the real Celery worker process.** `celery -A testgen.worker.celery_app worker` only imports `celery_app.py` — the module that *constructs* the `Celery` app — not `testgen.worker.tasks`, the module whose `@celery_app.task(...)` decorator is what actually registers the task. Nothing in the whole codebase or test suite had ever started a real `celery worker` process to consume a real task before Phase 11 (`test_requirements_api.py`/`test_worker_tasks.py` both call `run_generation_for_requirement` directly, by explicit design — see their own docstrings): `trigger_generation`'s `.delay()` call only needs the task *name* to enqueue successfully, so every integration test through Phase 9 looked completely green while this was broken. A real worker, started for real, failed immediately with `Received unregistered task of type 'testgen.generate_test_cases'. The message has been ignored and discarded.` Fixed with Celery's own documented mechanism for exactly this: `Celery("testgen", ..., include=["testgen.worker.tasks"])` — deliberately not a direct top-level `import testgen.worker.tasks` in `celery_app.py`, which would be a real circular import (`tasks.py` itself imports `celery_app` from `celery_app.py`); `include` is lazy, consulted by Celery's own worker bootstrap after the app object already exists, which is exactly why it's the correct fix and not just the convenient one. Reverified after the fix: the real worker now lists `testgen.generate_test_cases` under `[tasks]` at startup, receives a real enqueued task, and fails at the *correct, documented* point instead (`GEMINI_API_KEY is required`) — a clean, expected failure, not a silent no-op.
63. **`tests/eval/` has never had an actual test file written into it, across all 10 prior phases** — confirmed by listing the directory during Phase 11 (only `__init__.py`). Consistent with never having a real `GEMINI_API_KEY` to run LLM-output-quality evals against in this environment (Decision 22 and this file's every "untested-live" note), but worth stating explicitly rather than leaving implied: DESIGN.md §10 names "eval" as one of four pytest categories the verification plan expects, and the honest state is "the category is scaffolded and CI-excluded (Decision 38), not merely thin — it's empty."

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

---

## Phase 2 Verification (2026-08-27)

All green:

- `pip install -e ".[dev,db,ingestion]"` — pypdf 6.16.2, python-docx 1.2.0, lxml 6.1.2, markdown-it-py 4.2.0
- `ruff format .` / `ruff check .` — clean
- `mypy src tests` (strict) — 0 issues, 45 files (after installing `lxml-stubs` — see bug #2 below)
- `pytest --cov=testgen` — **31 passed**, 90% coverage. Same deliberately-deferred 0%/partial modules as Phase 1 (`logging.py`, `tracing.py`, parts of `db/session.py`) — still not wired to anything real yet.

**Real bugs hit + fixes this phase:**

1. **`parse_markdown` returned raw markdown syntax, not plain text** — first draft read `token.content` off each top-level `inline` token, but markdown-it-py documents that field as the *original source text* of the inline span, asterisks and all; the de-markup'd text actually lives on that token's `.children` (`text`/`code_inline` sub-tokens, with `strong_open`/`strong_close`/etc. marking formatting boundaries around them). Caught by `test_parse_markdown_strips_markup` actually failing (`'**' in text`), not by inspection. Fixed by walking `token.children` and joining only `text`/`code_inline` content.
2. **`mypy` failed on missing `lxml` stubs** (`import-untyped`). Rather than blanket-suppress like the LLM/queue libraries in Phase 0's mypy overrides (which genuinely have no good stubs), installed `lxml-stubs` (a real, maintained stub package) instead — and it immediately caught a second, real issue: `Element.itertext()` is typed to yield `str | bytes`, not just `str`, so joining its output directly failed strict mypy. Fixed by decoding `bytes` items before joining, in `parse_xml` — a genuine correctness fix (mixed-content XML can yield bytes at the C level), not just a type-checker appeasement.

**Committed:** yes — see git log.

---

## Phase 3 Verification (2026-08-27)

All green:

- `pip install milvus-lite` — real `win_amd64` wheel (3.2.1), pulls in `faiss-cpu`, `grpcio`, `numpy`, `pyarrow`. `pip install pymilvus` (3.0.1) alongside it.
- **Manual smoke test** (outside pytest, before writing any Phase 3 code): `MilvusClient(uri="./data/....db")` → `create_collection` → `insert` → `search` → `drop_collection`, all real, all worked. This is what resolved Decision 5's risk flag.
- **Manual schema check**: confirmed the default collection schema needs an int64 `id` (a string id fails with `DataNotMatchException`) — this is what motivated `stable_clause_id()` (Decision 20).
- **Manual SDK introspection**: confirmed `google-genai` 2.20.0's real `Client.__init__`, `Models.embed_content` signature, and `EmbedContentResponse`/`ContentEmbedding` field names before writing `GeminiEmbedder`, rather than relying on possibly-stale memory of the API shape.
- `ruff format .` / `ruff check .` — clean, first try
- `mypy src tests` (strict) — 0 issues, 52 files, first try (pymilvus already covered by Phase 0's `ignore_missing_imports` override)
- `pytest --cov=testgen` — **42 passed**, 90% coverage. New gaps are exactly the parts that need a real `GEMINI_API_KEY` (`GeminiEmbedder.__init__`/`.embed()`, `get_embedder()`) — deliberately deferred, see Decision 22.

**No bugs hit this phase** — the empirical checks above (schema type, SDK shape) were done *before* writing the corresponding code specifically to avoid the two most likely failure modes, and it worked: first-try clean ruff/mypy, all tests passing without a red run in between.

**Committed:** yes — see git log.

---

## Phase 4 Verification (2026-08-27)

All green:

- `pip install -e ".[dev,db,ingestion,vectorstore,embeddings,llm]"` — langgraph 1.2.11, langchain 1.3.17, langchain-google-genai 4.3.6, clean install
- **Manual scratch test** (before writing any of the 7 real agents): a throwaway 2-node graph with a retry loop, conditional routing, and a real `interrupt()`/`Command(resume=...)` round trip via `InMemorySaver` — confirmed the exact mechanics (`__interrupt__` key in the result, `get_state(config).next`, resume value coming back out of `interrupt()`) before committing to the full design (Decision 30)
- **Manual SDK introspection** (before writing `llm.py`): confirmed `ChatGoogleGenerativeAI`'s real field names (`model`, `google_api_key`, `temperature`, `response_mime_type`, `response_schema`), that `response_schema` expects a plain `dict[str, Any]` (i.e. `SomeModel.model_json_schema()` works directly), and that it genuinely overrides `bind_tools` — then confirmed directly that LangChain's standard fake chat models do *not* implement `bind_tools`, which is what motivated Decision 24
- `ruff format .` / `ruff check .` — clean after fixing import order (auto-fixable) and two over-long lines in test fixture JSON strings
- `mypy src tests` (strict) — 0 issues, 61 files, after fixing one real gap: `config = {"configurable": {...}}` needed an explicit `RunnableConfig` type annotation (a plain dict literal doesn't structurally satisfy it under strict mypy even though it matches at runtime)
- `pytest --cov=testgen` — **58 passed**, 92% coverage. Uncovered lines are exactly the parts needing a real `GEMINI_API_KEY` (`get_chat_model`'s actual `ChatGoogleGenerativeAI(...)` construction, `content_str`'s error branch, `build_default_deps`) — consistent with Phase 3's approach, nothing new deferred here.

**Real bug hit + fix:** the natural Python names for three agent functions — mirroring DESIGN.md §3's own agent names "Test Strategist," "Test Case Generator," "Test Data Synthesizer" — were `test_strategist_node`, `test_case_generator_node`, `test_data_synthesizer_node`. The moment these were imported into a test file, pytest's default function-collection pattern (`test_*`) tried to collect and run *them* as tests, failing with "fixture 'state' not found" (pytest tried to inject `state`/`deps` as fixtures). This is the same root cause as Phase 1's class-collision (Decision 13), but the fix had to be different: Phase 1 could freely repoint `python_classes` because zero real test classes existed yet; here, hundreds of genuine `test_*` functions already exist, so repointing `python_functions` would break real test collection wholesale. The actual fix was renaming the three colliding *agent* functions themselves (`strategist_node`, `case_generator_node`, `data_synthesizer_node` — dropping the leading `test_`), while leaving their graph-registered string node names (`"test_strategist"`, `"test_case_generator"`, `"test_data_synthesizer"`) untouched, since those are LangGraph's own identifiers, not Python names, and stay faithful to DESIGN.md's agent naming either way.

**Committed:** yes — see git log.

---

## Phase 5 Verification (2026-08-27)

All green:

- `pip install -e ".[dev,db,ingestion,vectorstore,embeddings,llm,compliance]"` — presidio-analyzer 2.2.364, presidio-anonymizer 2.2.364, spacy 3.8.16; `python -m spacy download en_core_web_sm` (13MB, not the ~560MB `en_core_web_lg` default — see Decision 31)
- **Manual smoke test** (before writing any redaction code): real `AnalyzerEngine` + `AnonymizerEngine` against a sample string with a name/phone/date — confirmed detection and redaction actually work end-to-end before committing to this NLP config
- `ruff format .` / `ruff check .` — clean
- `mypy src tests` (strict) — 0 issues, 68 files, after two targeted `# type: ignore` comments (see bug below) — no blanket module ignore needed for presidio, unlike the LLM/queue libraries in Phase 0's overrides
- `pytest --cov=testgen` — **73 passed**, 93% coverage, 0 warnings, including the closed-loop PHI redaction test (Decision 34) and a real GDPR-erasure-vs-audit-chain-integrity test that asserts `verify_chain()` still passes after erasure, not just that erasure ran without an exception

**Real bug hit + fix:** `mypy --strict` failed on two lines in `redaction.py`, and neither was fixable by adding `presidio_analyzer`/`presidio_anonymizer` to the existing `ignore_missing_imports` override (already present since Phase 0) — that override only suppresses "module not found" errors, but these packages actually ship a `py.typed` marker, so mypy analyzes what it finds. It found two real issues: (1) `AnonymizerEngine.__init__` itself has no type annotations (`no-untyped-call` under strict mode), and (2) more interestingly, `presidio_analyzer.RecognizerResult` (returned by `AnalyzerEngine.analyze()`) and `presidio_anonymizer`'s own same-named class (expected by `AnonymizerEngine.anonymize()`) are nominally different classes from two separately-typed packages — structurally identical and confirmed duck-type compatible at runtime (the manual smoke test above), but mypy correctly flags them as incompatible types. Fixed with two narrow, commented `# type: ignore` lines rather than a blanket suppression, since the rest of `redaction.py` (and everything else touching presidio) type-checks cleanly.

**Committed:** yes — see git log.

---

## Phase 6 Verification (2026-08-27)

All green:

- `pip install -e ".[dev,db,ingestion,vectorstore,embeddings,llm,compliance,integrations]"` — jira 3.10.5, httpx already present since Phase 0
- **Manual SDK introspection** (before writing `jira_adapter.py`): confirmed `jira.JIRA.__init__`'s real signature and, critically, that it contacts the server by default — this is what drove Decision 35's design (adapter takes an already-built client, doesn't construct `jira.JIRA` itself)
- `ruff format .` / `ruff check .` — clean
- `mypy src tests` (strict) — 0 issues, 77 files, clean on the first attempt (no presidio-style typing surprises this time)
- `pytest --cov=testgen` — **80 passed**, 93% coverage, 0 warnings — first real use of the `contract` marker/directory (seeded, unused, since Phase 0)
- **CI workflow validated** (`yaml.safe_load` — no GitHub Actions runner available locally, so this confirms the file parses correctly, not that the job graph behaves as intended end to end)

**Real bug hit + fix:** one contract-test assertion was simply wrong — it guessed `httpx` would percent-encode the literal `$` in the Azure DevOps work-item-type URL segment (`/_apis/wit/workitems/$Task`) to `%24`. Running the test showed it doesn't; the URL stays exactly `.../workitems/$Task?api-version=7.1`, which is *also* a more faithful match to Azure DevOps's actual documented contract (their docs show the literal `$` too). Fixed the assertion, not the adapter — the adapter was right the first time.

**Committed:** yes — see git log.

---

## Phase 7 Verification (2026-08-27)

**This is the phase the previous, discarded implementation attempt got stuck in a bad loop on** (see History). Approached deliberately this time: built in small verified sub-steps (security → deps → auth skeleton → projects/documents → checkpointer → orchestration → worker → requirements lifecycle → traceability/audit), running ruff/mypy/pytest after nearly every file instead of batching, and every time a test failed, stopped to find the actual root cause rather than patching around it. Paid off — every failure below was diagnosed and fixed on the first real attempt, no thrashing.

All green, final state:

- `pip install -e ".[dev,db,ingestion,vectorstore,embeddings,llm,compliance,integrations,api,queue]"` plus new deps added this phase: `python-multipart`, `pyjwt`, `bcrypt` (all in the `api` extra), `langgraph-checkpoint-postgres` (in `llm`)
- **Manual verification before writing wrapper code** (twice, same discipline as Phases 3/6): (1) `jira.JIRA`-style introspection wasn't needed again, but (2) a throwaway script proved `PostgresSaver` genuinely persists a paused interrupt across two independent instances/connections — real Postgres, real graph, real `Command(resume=...)` — before `generation/checkpointer.py` was written, then locked in permanently as `tests/integration/test_checkpointer.py`
- `ruff format .` / `ruff check .` — clean
- `mypy src tests` (strict) — **0 issues, 101 files** — including one genuine typing puzzle: `AgentDeps.chat_model_factory: Callable[..., BaseChatModel]` rejected a duck-typed "unreachable" stand-in for `build_readonly_deps()` (Decision 40); fixed by making it a real `BaseChatModel` subclass whose methods raise, not by loosening the type
- `pytest --cov=testgen` — **114 passed, 96% coverage, 0 warnings**. Coverage jumped on modules nothing had exercised before: `platform/db/session.py` 54%→100%, `platform/logging.py` 0%→94%, `platform/tracing.py` 0%→80% — all three finally wired to something real via FastAPI's lifespan and dependency injection, exactly what Phase 1 and Phase 4 had been waiting for.

**Real bugs and gaps hit + fixed this phase** (roughly in the order found):

1. **Test bug**: `Organization.name` is globally unique (Phase 1 schema); an early test helper hardcoded the same org name for every registered user, so a test registering two organizations hit the unique constraint. Fixed by deriving a distinct org name per email, not a schema or app change.
2. **Test bug, twice, same root cause**: after deliberately choosing to let `test_requirements_api.py`/`test_traceability_audit_api.py` writes really commit (Decision 42), two assertions still assumed a clean table (`select(TestCase)).scalars().all() == []` / `== 1`) — wrong once other tests' committed rows were legitimately still present. Fixed by scoping every such assertion to the specific requirement/project the test itself created, never "the whole table."
3. **Real application bug, found by a genuinely failing test, not inspection**: `Requirement.safety_class`/`status` were never written back to the `Requirement` row — see Decision 44. This is the one I'd flag first if asked "what did end-to-end testing catch that unit tests alone wouldn't have."
4. **Test-expectation bug, not an app bug**: a coverage-gaps test expected zero gaps after approving one `safety_critical` test case, but Phase 5's deterministic floor correctly requires *both* `functional` and `safety_critical` for Class C — the test's scripted LLM responses only produced one type. Fixed by scripting a second, `functional` test case, which is also just a more realistic fixture.
5. **Real gap, found by checking coverage rather than by a failing test**: `require_roles()` was built but applied to no route — see Decision 41. Nothing was wrong at the type or test level; the RBAC mechanism simply had zero call sites, which coverage made visible and a failing test never would have (there was nothing failing to gate).
6. **Real gap, found while building the audit endpoint before it shipped**: `AuditLog.organization_id` was never set by `lock_traceability_links_for_requirement` or `persist_generation_result` — see Decision 43.

**Committed:** yes — see git log.

---

## Phase 8 Verification (2026-08-27)

All green:

- `pip install -e ".[dev,db,ingestion,vectorstore,embeddings,llm,compliance,integrations,api,queue,ui]"` — streamlit 1.62.0, clean install; confirmed real `st.Page`/`st.navigation`/`streamlit.testing.v1.AppTest` signatures via introspection before writing any page code (same discipline as Phases 3/4/6/7)
- `ruff format .` / `ruff check .` — clean
- `mypy src tests` (strict) — **0 issues, 113 source files** (after the pre-existing `embeddings.py` fix, Decision 50)
- `pytest --cov=testgen` — **139 passed, 91% coverage, 0 warnings** (up from 114/96% at Phase 7 — the drop is arithmetic, not a quality regression: `app.py` is structurally invisible to `pytest-cov` because `AppTest.from_file`/`from_function` exec script *source text* rather than importing it, confirmed by every *other* UI module — `pages/*.py`, `session.py`, `components.py` — showing real, non-zero coverage since they're imported normally from inside that exec'd context)
- **Real, live end-to-end verification in an actual browser** (system-prompt requirement for UI changes): `docker compose up -d postgres redis` (already running) → `alembic upgrade head` (already current) → real `uvicorn testgen.api.app:app` + real `streamlit run src/testgen/ui/app.py`, driven through the Claude Browser tool. Confirmed live: register → auto-login → sidebar nav (all 4 pages) → create project (message-after-rerun fix visibly correct) → upload a real 3-requirement Markdown doc via the API (browser-driven file-picker automation is blocked by the sandbox's `InvalidStateError` on programmatic `<input type=file>` values — a tooling limitation, not an app one; the exact multipart request the real `st.file_uploader` would send is what `test_upload_document_sends_multipart_file` already proves) → Requirements & Approval lists all 3 real extracted requirements → seeded one to `awaiting_approval` the same way `test_requirements_api.py` does (`run_generation_for_requirement` + `ScriptedChatModelFactory`, against the *same* local dev Postgres the live API reads from) → Check status → full pending-review UI renders real drafted test cases + critic feedback → **Approve** → success message + persisted test cases, live, in the browser → Traceability Matrix and Audit Log both show the real resulting rows.
- **Test-data cleanup**: the live registration above used the organization name `"Acme Health"`, which several existing integration tests hardcode literally (`test_auth_api.py` et al.) — this collided (`UniqueViolation` on `organizations.name`) and failed 20 unrelated tests on the next full-suite run. Root-caused immediately (not a code regression — confirmed by `git stash`-testing the clean tree, and by the org's `created_at` timestamp matching the manual session), fixed by renaming that one row (`UPDATE ... SET name = 'Acme Health (manual Phase 8 QA session, 2026-08-27)'`) rather than deleting it (no cascade-delete configured on this schema by design — Decision 32 — and a rename is the minimal, safe fix). Full suite re-verified green after. A reader of the dev DB later will see that one oddly-named row and now knows why.

**Real bugs found + fixed this phase** (roughly in the order found):

1. **Real bug, found by writing an `AppTest`-based test, not by inspection**: `st.success()`/`st.info()` called immediately before `st.rerun()` are silently discarded — see Decision 49. Hit in three places (create-project, approve, reject) plus the 401/expired-token path; all four fixed with the same session-state-stash pattern and now regression-tested.
2. **Real bug, found only by live browser testing — no automated test could have caught it without a real second process on a real socket**: `httpx.RemoteProtocolError`/`ReadError` from a stale pooled keep-alive connection racing `uvicorn`'s own keep-alive timeout — see Decision 51. Mitigated with `httpx.HTTPTransport(retries=1)`.
3. **Pre-existing, unrelated gap found while verifying this phase's own baseline was green**: `knowledge/embeddings.py` started failing strict mypy due to `mypy` version drift since Phase 3/7, not a Phase 8 code change — see Decision 50. Fixed rather than left red, so Phase 8 ends on a genuinely clean `ruff`/`mypy`/`pytest`, not a baseline someone else has to first go dig out.
4. **Tooling limitation, not an app bug, worth recording so a future session doesn't re-discover it the hard way**: the Claude Browser tool's sandbox refuses to programmatically set `<input type="file">`'s value (`InvalidStateError`, a standard browser security restriction) — live-driving `st.file_uploader` end-to-end isn't possible through this tool. Worked around by POSTing the multipart upload directly via `httpx` against the same running API (functionally identical to what the browser would send), then verifying the *result* renders correctly in the real browser.

**Committed:** yes — see git log.

---

## Phase 9 Verification (2026-08-27)

All green:

- Installed Terraform 1.15.8 (`winget install HashiCorp.Terraform`) and Docker 28.3.2 (already present, confirmed Phase 0/1) — both used for real, not just written-and-assumed verification this phase.
- `ruff format .` / `ruff check .` — clean
- `mypy src tests` (strict) — **0 issues, 113 source files**
- `pytest -m "not eval"` — **140 passed, 0 warnings besides the pre-existing starlette/httpx notice** (139 from Phase 8 + 1 new regression test for Decision 56's `MILVUS_DB_URI` fix)
- **Terraform, validated for real**: `terraform fmt -check -recursive` clean; `terraform init -backend=false` succeeded (real provider download: `hashicorp/aws` 5.100.0, `hashicorp/random` 3.9.0, `.terraform.lock.hcl` committed); `terraform validate` — **"Success! The configuration is valid."** No `terraform plan`/`apply` (needs real AWS credentials, DESIGN.md §8) — `validate` is the correct and honest level of verification for infra that's never applied.
- **All 3 Dockerfiles, built and run for real, not just written**: `docker build` succeeded for `api`/`worker`/`ui` (1.05GB/1.39GB/782MB respectively — the worker is largest from presidio+spaCy+langchain+milvus+faiss together, the one genuine "needs everything" service). Then `docker compose up -d --build` brought up the real stack (existing local-dev `postgres`/`redis` containers recognized as already part of the same compose project, left untouched) — caught a real bug (Decision 56, `MILVUS_URI`/`MILVUS_DB_URI` collision) on the first attempt, fixed it, rebuilt, and confirmed clean the second time: `api` container reached Docker's `healthy` state (`alembic upgrade head` ran against the real Postgres, `GET /health` returned `{"status":"ok"}`), `worker` connected to Redis and logged `celery@<hostname> ready`, `ui` served HTTP 200 and passed its own `/_stcore/health` check (verified on an alternate host port via `docker run` against the compose-built image, joined to the compose network, since host port 8501 collided with an unrelated pre-existing container on this dev machine — not a defect in `docker-compose.yml`).
- **`docker-compose.prod.yml`'s merge behavior verified directly, not assumed**: `docker compose -f docker-compose.yml -f infra/docker/docker-compose.prod.yml config` confirmed each service's `build:` block is actually removed (not left coexisting with `image:`) and `image:` resolves to the expected `${ECR_REGISTRY}/testgen-ai/<service>:latest` — this is what proved the `!reset null` tag was necessary (a plain `image:` override alone left `build:` in place, confirmed by running `config` both ways).
- **Cleanup**: `api`/`worker`/`ui` containers stopped after verification (not left running as background load) — `postgres`/`redis` left running, matching the persistent local-dev convention already documented in this file's Environment section. The three ad-hoc `testgen-*:test` image tags from manual `docker build` runs (superseded by compose's own `ai_testcase_generator-*` tags) were removed.

**Real bugs found + fixed this phase** (roughly in the order found):

1. **Real, environment-specific bug, found only by actually building the images, not by writing them**: hatchling's `readme = "README.md"` build requirement failed inside the Docker build context because `.dockerignore` excludes `*.md` repo-wide — see Decision 54.
2. **Real bug, found only by actually running `docker compose up`, invisible to every prior phase's non-containerized local development**: the `MILVUS_URI`/`pymilvus` environment-variable collision — see Decision 56. The single most consequential finding of this phase: it broke both the `api` and `worker` containers outright, and no amount of code review would have surfaced it, since the collision only exists once `MILVUS_URI` becomes a real OS environment variable.
3. **Design correction, found by testing the actual compose merge behavior rather than trusting the first draft**: `docker-compose.prod.yml`'s `image:` override doesn't remove the base file's `build:` block on its own — see Decision 55.

**Known gap, deliberately not closed this phase** (belongs to Phase 11, not Phase 9's infra-only scope — see this file's Next Action): nothing seeds the regulatory corpus (`knowledge/corpus.py`) outside of tests, so a fresh `docker-compose up` stack's Milvus collection is empty until someone runs a seed step by hand.

**Committed:** yes — see git log.

---

## Phase 10 Verification (2026-08-27)

All green (docs-only phase — no source changes, so this is lighter than
Phases 8/9, but the same checks were still run, not skipped):

- `ruff check .` / `mypy src tests` (strict) — clean, unaffected (no `.py` files touched)
- `pytest -m "not eval"` — **140 passed**, unchanged from Phase 9 (unaffected)
- **Every factual claim in `docs/compliance/mapping.md` was checked against the real code before being written, not asserted from memory of having built the features** — e.g. the "RBAC gates `approve`/`reject`, JWT gates everything else, every route scopes by `organization_id`" claim was verified by grepping `CurrentUser`/`Reviewer` usage across every router file and confirming `auth.py`'s two endpoints (`register`/`token`) are the only ones without it, and that `audit.py` filters directly on `organization_id` while `documents.py`/`projects.py`/`requirements.py`/`traceability.py` do the equivalent via `get_owned_project`'s ownership check — both are real, just different mechanisms for the same guarantee, and the doc's claim doesn't overstate which.
- `knowledge/corpus.py` (Decision 21's own seed data) was read in full before writing the compliance doc's per-clause table, rather than working from a summary — the 18 clauses' exact standard/`clause_ref`/paraphrased text all came from that read, not reconstructed from memory.

**No bugs found this phase** — expected for a docs-only phase with no source changes; the verification effort went into *accuracy of the documentation's claims* rather than into catching code defects.

**Committed:** yes — see git log.

---

## Phase 11 Verification (2026-08-27) — final phase

The full DESIGN.md §10 walkthrough, against the actual `docker-compose`
stack (not local dev processes — Phase 8's UI verification used local
`uvicorn`/`streamlit`; this is the first time the *built images* were
driven end to end). This is the phase that justified having a Phase 11 at
all: two real, structural bugs were found that no prior phase's testing —
including Phase 8's own live-browser verification — could have caught,
because both only manifest when a real container, running as it actually
will in production, does something for the first time.

**Walkthrough, in order:**

1. `docker compose up -d` — Postgres/Redis (already running, 8+ hours,
   untouched) + `api`/`worker`/`ui` all built and started. `api` reached
   Docker's `healthy` state; `ui`'s host port (8501) again collided with
   the same unrelated pre-existing container on this dev machine as Phase
   9 — same non-issue, worked around the same way (`docker run` against
   the compose-built image, joined to the compose network, alternate host
   port).
2. `scripts/seed_corpus.py` run for real inside the `worker` container —
   failed exactly as documented (`GEMINI_API_KEY is required`), confirming
   its wiring reaches the correct point and fails loudly rather than
   masking the missing key.
3. Register → auto-login → create project → **upload a real document via
   direct HTTP against the containerized API** (browser file-picker
   automation is sandboxed the same way Phase 8 found — worked around the
   same way, `httpx` direct POST) — **crashed with a real bug, see below**.
4. Fixed, rebuilt, retried — upload succeeded, 2 requirements extracted.
5. **Triggered a real generation via the UI** (`Generate test cases`) —
   enqueued to the real `worker` via real Redis — **the real worker
   discarded it as an unregistered task, a second real bug, see below**.
6. Fixed, rebuilt, retried — the real worker received the real task and
   failed at the *correct, documented* point (`GEMINI_API_KEY is
   required`) instead of silently discarding it.
7. Seeded a pending-approval state the same way Phase 8 did (scripted fake
   LLM responses + fake embedder, run from the host against the same
   containerized Postgres) — reused, not reinvented.
8. **Full approval screen, live, in the browser, against the real
   containerized API+UI**: drafted test cases + critic feedback rendered
   correctly → **Approve** → success message + 2 persisted test cases,
   exactly as Phase 8 verified against local processes, now also verified
   against the actual deployable images.
9. Traceability Matrix and Audit Log pages both rendered real data from
   the containerized stack (2 `stDataFrame` widgets on RTM — the matrix
   itself plus a real coverage gap for the still-ungenerated second
   requirement; 1 populated `stDataFrame` on Audit Log).
10. Jira sync legitimately returned empty — `settings.jira_base_url` is
    unset in this `.env` (no live Jira credentials in this environment,
    same standing constraint as Decision 35/DESIGN.md §8), so
    `_resume_and_persist` correctly never even attempts a sync call. Not
    separately re-derived live: the UI's Approve button runs the exact
    same `_resume_and_persist` code path the existing, passing
    `test_full_lifecycle_generate_status_pending_approve` already asserts
    `alm_sync == []` for under these same config conditions.
11. **`platform.audit.verify_chain()` run directly against the real,
    live-generated audit log (484 rows accumulated across this whole
    project's history, including every action from this walkthrough) —
    returned `True`.** The strongest verification the hash chain (ADR-0003)
    has had yet: real production-shaped usage, not an isolated test
    fixture tampering with one row and checking the detector fires.
12. `ruff check .` / `mypy src tests scripts/seed_corpus.py` (strict) —
    clean. `pytest -m "not eval"` — **140 passed**, unchanged (both real
    bugs were containerization/deployment issues, not caught by — and not
    expected to be caught by — the existing non-containerized test suite;
    Decision 62's fix does get exercised indirectly through
    `test_worker_tasks.py` importing `testgen.worker.tasks`, but no test
    asserts on Celery's own task registry, which is exactly the gap that
    let this ship unnoticed for four phases).
13. Cleanup: `api`/`worker`/`ui` (compose-managed) and the standalone
    verification `ui` container stopped; `postgres`/`redis` left running
    (persistent local-dev convention, Environment section above). New test
    data used a distinctive org name (`Phase11 Verification Org`) chosen
    specifically to avoid Phase 8's `"Acme Health"` collision — confirmed
    via grep against `tests/` before use, no cleanup needed after.

**Browser-tooling note, not an app finding:** several UI interactions this
phase needed a retry or a fresh tab before succeeding — one login attempt
where `click`+`type` silently didn't reach the actual `<input>` element
(confirmed via direct DOM inspection: the field's real `.value` stayed
empty despite the tool reporting the keystrokes sent), recovered by
switching to `form_input` and then, when that also needed a fresh tab to
take effect, by simply opening a new tab. Verified directly each time that
this was a browser-automation/tab-state issue and not the application: the
exact same credentials worked instantly over direct HTTP, and the exact
same click+type sequence worked correctly moments earlier and moments
later in the same session. Recorded here so a future session doesn't waste
time suspecting an app regression that isn't there.

**Real bugs found + fixed this phase** (both are the reason Phase 11
existed as a distinct phase rather than being folded into Phase 9):

1. **`PermissionError` on the first real write to the `appdata` volume** —
   see Decision 61. `api`/`worker` run as a non-root user, but a fresh
   named Docker volume mounts owned by root by default; neither container
   had ever actually written to that path before (Phase 9's verification
   didn't upload a document or run a real generation). Fixed with
   `chown`-before-`USER app` in both Dockerfiles, exploiting Docker's own
   documented "seed an empty named volume from the image" behavior.
2. **`generate_test_cases_task` was never registered with the real Celery
   worker process** — see Decision 62. The single most consequential
   finding across all 11 phases: every test through Phase 9 exercised
   *enqueuing* (needs only a task name string) or called the underlying
   function *directly* (bypassing Celery's registry entirely), so nothing
   had ever proven a real `celery worker` process could actually consume a
   real `generate_test_cases_task`. It couldn't have — fixed with Celery's
   own `include=` mechanism on the `Celery()` constructor.

**Committed:** yes — see git log.
