# ADR-0003: Application-level, hash-chained audit log

**Status:** Accepted
**Date:** 2026-08-27

## Context

DESIGN.md §2 is explicit that this system's entire reason for existing is
the audit trail: "nothing reaches ALM sync without a named human approval
on record," and that traceability only becomes official "at the Human
Approval step." An append-only `audit_log` table (DESIGN.md §5) is the
obvious start, but an append-only table on its own only stops *new* rows
from silently disappearing — it does nothing to prove an *existing* row
hasn't been quietly edited after the fact (`UPDATE audit_log SET payload =
... WHERE id = 42`), which is exactly the tamper scenario 21 CFR Part 11
("secure audit trails... sufficient to ensure the authenticity, integrity"
— the FDA seed clause `11.10`) cares about.

## Decision

Each row stores `sha256(prev_hash | action | entity_type | entity_id |
canonical_json(payload))` as its own hash, chaining every row to the one
before it (`platform/audit.py`). `record_event()` reads the last row with
`SELECT ... FOR UPDATE` to serialize concurrent appends (so two
simultaneous writers can't both compute their hash against the same
"previous" row and silently fork the chain), then inserts. `verify_chain()`
walks the whole table and recomputes every hash from scratch — a tampered
row's hash won't match what a hash of its own content would predict, and
neither will every row *after* it (each one's stored `prev_hash` was
computed from the tampered version's original hash, not whatever it was
just changed to).

Built as plain application code, not a Postgres trigger or stored
procedure. Two reasons, both about actually being able to trust the
answer:

- **Testability.** `tests/integration/test_audit_hash_chain.py` tampers
  with a row directly via raw SQL and asserts `verify_chain()` catches it
  — a real adversarial test, not just "no exception was raised." That test
  is straightforward to write against Python code in the same codebase;
  it would mean a separate SQL/pl-pgsql test harness for a trigger-based
  version.
- **Same-language accountability.** The hashing logic lives next to
  everything else that writes `audit_log` rows, reviewable and testable
  the same way as the rest of the domain — not a second implementation
  language (SQL procedural code) an auditor or reviewer would need to trust
  separately.

## Consequences

- GDPR's right to erasure (Art. 17) and Part 11's "don't touch history"
  requirement are in genuine tension for any system that logs a user's
  identity into an immutable trail. Resolved by scope, not by weakening
  either guarantee: `audit_log.actor_user_id` is a UUID foreign key, not
  personal data on its own — the actual identifying fields (email,
  full_name) live on `User`, which erasure scrubs to a tombstone. The hash
  chain covers `action`/`entity_type`/`entity_id`/`payload`, none of which
  erasure touches, so `verify_chain()` is asserted to still pass
  *immediately after* an erasure in
  `test_erase_user_personal_data_scrubs_identity_without_touching_audit_chain`
  — checked, not just argued (Decision 32).
- The chain only proves *this database's* history hasn't been edited in
  place. It does not (and cannot, on its own) prove a row was never
  deleted and every subsequent hash recomputed to match — that would need
  an external, independent anchor (e.g. periodically publishing the latest
  hash somewhere outside this system's own control), which is explicitly
  out of scope for a portfolio build (DESIGN.md §1/§8).
- `SELECT ... FOR UPDATE` on the last row means every audit write briefly
  serializes against every other one. Acceptable at this project's scale
  (Decision 11 makes the same call about sync SQLAlchemy generally) — a
  high-throughput production deployment would need to revisit this if
  audit-log writes ever became a real contention point.
