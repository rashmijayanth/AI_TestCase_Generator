# ADR-0002: Hexagonal architecture — ports & adapters at every external boundary

**Status:** Accepted
**Date:** 2026-08-27

## Context

This system talks to a genuinely long list of external things it doesn't
control: an LLM (Gemini), a vector database (Milvus), object storage
(local disk in dev, S3 in prod), and three different ALM tools (Jira live,
Azure DevOps and Polarion against documented APIs only — DESIGN.md §8, no
tenant available for the latter two). Every one of those integrations
needs to be swappable and, critically, *testable without the real
dependency* — this project has no live `GEMINI_API_KEY` in its own dev
environment (Decision 22) and no live ADO/Polarion tenant at all (Decision
36), so "write tests against the real thing" was never an option for large
parts of the system.

## Decision

Each bounded context that touches something external defines a narrow
**Port** — a `Protocol` (structural typing, no explicit inheritance
required) describing only the operations that context actually needs —
and a real **Adapter** implementing it against the actual service. Business
logic depends on the Port, never the concrete client library:

| Port | Real adapter | Test double |
|---|---|---|
| `EmbeddingPort` | `GeminiEmbedder` | `DeterministicFakeEmbedder` (hash-based) |
| `VectorStorePort` | `MilvusVectorStore` | same class, real `milvus-lite` file per test |
| `StoragePort` | `LocalFilesystemStorage` / `S3Storage` | `LocalFilesystemStorage` against `tmp_path` |
| `ALMPort` | `JiraAdapter`, `AzureDevOpsAdapter`, `PolarionAdapter` | contract tests via `httpx.MockTransport` |
| `JiraClientPort` | the real `jira.JIRA` client | scripted fake |
| `BaseChatModel` (LangChain's own port) | `ChatGoogleGenerativeAI` | `ScriptedChatModelFactory` |

Two refinements worth naming explicitly:

- **`AgentDeps` has two constructors** (Decision 40): `build_default_deps()`
  wires real adapters for the Celery worker's actual generation run;
  `build_readonly_deps()` wires stand-ins (`_UnreachableChatModel` — a real
  `BaseChatModel` subclass whose methods raise, not a duck-typed mock) for
  every API code path that only ever reads a checkpoint or resumes past
  the human-approval interrupt, neither of which touches an LLM. This is
  what lets the FastAPI service's whole lifecycle run in this environment
  without a real Gemini key.
- **`sync_test_case` catches any adapter exception and records a `FAILED`
  `ALMSyncRecord` rather than propagating** (Decision 37) — a design
  consequence of adapters being swappable is that they're also expected to
  fail independently of the core domain; a Jira outage shouldn't crash test
  case approval.

## Consequences

- The domain layer (`generation`, `traceability`, `compliance`) has zero
  import-time dependency on `google-genai`, `pymilvus`, `jira`, or
  `httpx`'s specifics — those live only inside the adapters. Confirmed
  concretely in Phase 9: sizing each container's `pyproject.toml` extras
  meant reading which modules each file imports, and the boundary held —
  `testgen.api` never needed `compliance`'s presidio/spaCy stack, because
  nothing in that layer imports `compliance.redaction` above the one lazy,
  function-local import inside `data_synthesizer_node` (Decision 34).
- Contract tests (`tests/contract/`, `httpx.MockTransport` against recorded
  fixtures) are a permanent, first-class category for ADO/Polarion — not a
  placeholder for "real tests later." There will never be a live tenant to
  test against in this environment (Decision 36), and the port/adapter
  split is exactly what makes that an acceptable, honest permanent state
  rather than an untested gap.
- Cost: an extra layer of indirection (Port → Adapter → real client) for
  every external dependency, even ones unlikely to ever change (there is
  currently exactly one LLM provider and one vector store). Accepted
  because the *testability* win (real business-logic tests with zero
  network access) outweighs the small structural overhead, and because
  DESIGN.md §6 names this hexagonal boundary as a first-class design
  constraint, not an incidental pattern.
