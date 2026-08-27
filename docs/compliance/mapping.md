# Compliance Mapping

Which regulatory clause maps to which part of this system, and why. This is
the **static, human-readable** layer — "what does this codebase do to
address IEC 62304 §5.5.3, and where." It's a companion to, not a
replacement for, the **dynamic, per-artifact** `compliance_mappings`
database table (DESIGN.md §5): every time the Compliance Critic agent
grounds a specific drafted test case against a specific retrieved clause,
*that* link is recorded per-requirement/per-test-case at generation time,
queryable via the RTM (`GET /projects/{id}/rtm`, `compliance_standards`
column). This document is the fixed backdrop those dynamic links are drawn
against.

**Read this alongside `src/testgen/knowledge/corpus.py`'s own header
comment before treating anything below as authoritative regulatory
guidance**: the seeded clause text is *original, illustrative paraphrasing
written for this portfolio demo* — not verbatim standard text (ISO/IEC
standards are copyrighted and sold by those bodies; FDA/GDPR text is
public-domain but still paraphrased here rather than quoted from a
verified primary source), and `clause_ref` values are plausible-looking
section numbers, not guaranteed to match every edition of each standard. A
real deployment would license the official standard text and have it
reviewed by someone qualified to do regulatory sign-off. This document
demonstrates the *mechanism* — grounded generation, traceability, and an
auditable approval trail — not a compliance-grade clause library, and it
is not itself a regulatory audit or legal opinion.

---

## FDA (21 CFR Part 820 / Part 11)

| Clause | Paraphrased requirement | Addressed by |
|---|---|---|
| 820.30(g) | Design validation must show specs meet user needs under defined operating conditions | Test Case Generator drafts functional/positive test cases per requirement (DESIGN.md §4); Compliance Critic independently re-checks against re-retrieved clause text before a draft reaches human review |
| 820.30(i) | Design changes must be identified, verified/validated, reviewed, and approved before implementation | The human-approval `interrupt()` (ADR-0001) — no test case, and no traceability link, becomes official without a named approver on record |
| 11.10 | Electronic record systems need validation, secure audit trails, and integrity controls | Hash-chained `audit_log` (ADR-0003); `TraceabilityLink.locked_by`/`locked_at` record who approved what, when |

## IEC 62304 (medical device software life cycle)

| Clause | Paraphrased requirement | Addressed by |
|---|---|---|
| 4.3 | Software items need a safety classification (A/B/C) based on failure severity | Requirement Analyst agent classifies `SafetyClass` per requirement (`generation/agents.py`); written back to the `Requirement` row itself, not just copied onto test cases (Decision 44) |
| 5.1.1 | A development plan appropriate to the item's safety class | Test Strategist agent plans test *types* based on requirement + safety class (DESIGN.md §3); `find_coverage_gaps`'s minimum-floor check (functional for Class A; +safety_critical for B/C, Decision 33) is the deterministic backstop |
| 5.5.3 | Verification under normal *and* anomalous/boundary conditions, appropriate to safety class | The test taxonomy itself (DESIGN.md §4: functional, negative, boundary, safety-critical/failure-mode, performance, security, privacy, data-driven) — safety-critical/failure-mode cases specifically verify behavior "when the safety mechanism itself fails" |

## ISO 9001 (quality management systems)

| Clause | Paraphrased requirement | Addressed by |
|---|---|---|
| 8.3 | Plan, control, and review design/development, with verification and validation per stage | The fixed LangGraph pipeline itself (ADR-0001) — every requirement passes through the same reviewable stages, not an ad hoc process |
| 9.1 | Monitor, measure, analyze, and evaluate QMS performance | `llm_generation_runs` (model, prompt version, tokens, cost, latency, eval score — DESIGN.md §5); `tests/eval/` as a first-class pytest category for LLM-output-quality evals |
| 10.2 | React to nonconformities, take corrective action, analyze root causes | The Compliance Critic's reject → feedback → regenerate loop (bounded retries) *is* this, applied per-artifact rather than organization-wide |

## ISO 13485 (medical device QMS)

| Clause | Paraphrased requirement | Addressed by |
|---|---|---|
| 7.3 | Design/development planning defines stages, reviews, verification, validation per device risk | Same as IEC 62304 §4.3/5.1.1 above — safety-class-driven planning is shared machinery, since IEC 62304 and ISO 13485 overlap heavily by design in real medical-device QMS practice |
| 7.5.6 | Processes that can't be verified by subsequent measurement must be validated, with records | `llm_generation_runs` records the model/prompt-version/eval-score that produced each artifact — the generation process itself is the record |
| 8.2.1 | A documented feedback process, including post-market surveillance | Out of scope for this system as built — it covers pre-release test generation, not fielded-device monitoring. Named here deliberately as a gap, not silently omitted |

## ISO 27001 (information security management)

| Clause | Paraphrased requirement | Addressed by |
|---|---|---|
| A.9.1 | Access restricted per a documented access-control policy | RBAC via `require_roles(ADMIN_ROLE_NAME)` (Decision 41) gates `approve`/`reject` — the two most consequential actions in the system; JWT auth (`platform/security.py`) gates everything else; multi-tenancy is enforced at the query layer (every route scopes by the caller's `organization_id`) |
| A.12.1 | Documented operating procedures; controlled system/facility changes | `docs/DESIGN.md` + `docs/PROGRESS.md`'s phase-by-phase decision log *is* this for the system's own build process; Alembic migrations are the controlled-change mechanism for the schema itself |
| A.18.1 | Identify and keep current all applicable legal/regulatory/contractual requirements | This document, plus the corpus's own honesty notice above about what it is and isn't |

Presidio-based PHI/PII redaction (`compliance/redaction.py`) is this
system's other concrete ISO 27001-adjacent control, even though it isn't
tied to one specific seeded A.\* clause above: every string value in a
synthesized test dataset is run through `AnalyzerEngine`/`AnonymizerEngine`
*before* it's persisted (`data_synthesizer_node`, gated by
`phi_redacted=True` only being set once redaction genuinely ran — Decision
34), and the Test Data Synthesizer's own prompt separately instructs the
model to generate obviously-synthetic values in the first place. Belt and
suspenders, not either alone.

## GDPR

| Clause | Paraphrased requirement | Addressed by |
|---|---|---|
| Art. 5 | Lawful, fair, transparent processing; purpose limitation; storage limitation | Multi-tenant org scoping (every row traces to an `organization_id`); no field collects more than the stated purpose needs |
| Art. 15 *(not in the seed corpus, but genuinely implemented)* | Right of access | `compliance/gdpr.py`'s `export_user_data()` — every audit event, approved test case, and uploaded document linked to one user |
| Art. 17 | Right to erasure ("right to be forgotten") | `compliance/gdpr.py`'s `erase_user_personal_data()` — scrubs `User.email`/`full_name`/`hashed_password`, reconciled with Part-11 audit immutability by never touching `audit_log` itself (ADR-0003's Consequences section; checked by a real test, not just argued — Decision 32) |
| Art. 32 | Technical/organizational measures appropriate to risk, incl. pseudonymization/encryption | Presidio redaction (pseudonymizes/removes PII-like values before an LLM ever sees them); passwords hashed via `platform/security.py`; TLS/at-rest encryption is an infra-layer concern (`infra/terraform/s3.tf`'s `aws_s3_bucket_server_side_encryption_configuration`, EBS `encrypted = true` on the EC2 instance) |

Data-subject rights above cover *this system's own user accounts* — not
the healthcare end-patients the generated test datasets nominally
reference, which are synthetic by construction (`compliance/gdpr.py`'s own
header comment).

---

## What this document is not

- Not a substitute for review by someone qualified to make an actual
  regulatory compliance determination.
- Not proof that the *generated test cases themselves* are compliant test
  cases for a real device — that determination depends on the real
  requirement, the real device, and the real, licensed standard text, none
  of which this portfolio build has.
- Not exhaustive: it maps the 18 seeded clauses (`knowledge/corpus.py`)
  plus the GDPR rights genuinely implemented beyond them. A production
  compliance program would work from the complete, current, licensed text
  of each standard, not a demo-sized seed corpus.
