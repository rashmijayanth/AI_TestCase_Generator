# Architecture Decision Records

Lightweight ADRs (Context / Decision / Consequences) for the choices in this
codebase that most warrant a standalone record — significant, not always
obvious in hindsight, and worth a future contributor understanding the
reasoning for rather than just the outcome. Most build-time decisions live
in `docs/PROGRESS.md`'s numbered decision log instead; these four rose
above that bar. New ADRs are numbered sequentially and never edited after
acceptance — a changed decision gets a new ADR that supersedes the old one.

| ADR | Decision |
|---|---|
| [0001](0001-langgraph-fixed-topology-and-real-interrupt.md) | Fixed-topology LangGraph orchestration, gated by a genuine `interrupt()` |
| [0002](0002-hexagonal-ports-and-adapters.md) | Hexagonal architecture — ports & adapters at every external boundary |
| [0003](0003-application-level-hash-chained-audit-log.md) | Application-level, hash-chained audit log |
| [0004](0004-milvus-db-uri-env-var-rename.md) | Rename the Milvus URI setting's environment variable, not the Python attribute |
