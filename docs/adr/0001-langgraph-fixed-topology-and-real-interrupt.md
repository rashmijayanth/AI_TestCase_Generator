# ADR-0001: Fixed-topology LangGraph orchestration, gated by a genuine `interrupt()`

**Status:** Accepted
**Date:** 2026-08-27

## Context

Seven agents (Requirement Analyst, Regulatory Researcher, Test Strategist,
Test Case Generator, Test Data Synthesizer, Compliance Critic, Traceability
Agent — DESIGN.md §3) have to turn a raw requirement into approved,
traceable test cases. Two separate design questions sit inside that:

1. **How do the agents hand off to each other?** The popular alternative is
   a free-form, autonomous multi-agent framework (AutoGen-style, or a
   supervisor agent that decides at runtime which agent to call next) —
   flexible, and a reasonable default for many agentic systems.
2. **How does a human's approval actually gate what happens next?** The
   easy version is a UI checkbox: the frontend shows "approved" and the
   backend trusts it. Functionally that's often "good enough."

Neither easy answer holds up in this system's actual context: the output
feeds an FDA/IEC-62304 audit trail. An auditor needs to be able to point at
the code and say "this is the only path a test case could have taken to
reach 'approved,' and it is reproducible." A supervisor agent choosing its
own next step at runtime, or a UI flag a backend endpoint takes on faith,
both fail that bar — neither is inspectable or provably enforced.

## Decision

- Orchestrate with a **LangGraph `StateGraph` with a fixed, deterministic
  topology**: `START → requirement_analyst → regulatory_researcher →
  test_strategist → test_case_generator → test_data_synthesizer →
  compliance_critic → (test_case_generator | human_approval) →
  traceability_agent → END` (`generation/graph.py`). The only
  non-determinism is bounded: the critic→generator retry loop (capped at
  `max_retries`) and the Regulatory Researcher's own internal retrieval
  loop. No agent decides *which other agent* runs next — the graph does.
- Gate the finalize step on a **real LangGraph `interrupt()`**
  (`human_approval_node`), not a boolean the API trusts. The graph
  literally cannot reach `traceability_agent`/`END` without a resume value
  supplied from outside — verified directly with a throwaway scratch
  script before writing any of the seven real agents (PROGRESS.md Decision
  30), and backed by a **persistent, Postgres-backed checkpointer**
  (`generation/checkpointer.py`, Decision 39) so the paused interrupt
  survives between the request that triggers generation and the later,
  separate request where a human actually approves it.

## Consequences

- Reproducible control flow: given the same inputs and the same LLM
  responses, the sequence of agent calls is identical every run. An
  auditor (or a test) can assert "the graph visits these nodes in this
  order," not just "the agents were consulted."
- The approval boundary is structurally real, not just conventionally
  respected: `api/routers/requirements.py`'s `approve`/`reject` endpoints
  are the *only* code path that can supply the interrupt's resume value,
  and `require_roles(ADMIN_ROLE_NAME)` gates both (Decision 41).
  `persist_generation_result` — the thing that actually locks traceability
  links and writes the audit entry — only ever runs after that resume.
- Cost: less flexible than a supervisor-agent design if a future
  requirement type needs a genuinely different pipeline shape (e.g.
  skipping the Compliance Critic for some class of trivial requirement).
  That would mean a new named path through the graph, not a policy change
  in one place — an explicit tradeoff, not an oversight.
- The bounded retry loop (critic → generator, capped) is the one place
  determinism is deliberately relaxed, and it's capped precisely so the
  graph is still guaranteed to terminate and reach the approval gate.
