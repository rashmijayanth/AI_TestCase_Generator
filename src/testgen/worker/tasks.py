"""Celery tasks.

generate_test_cases_task is the thin, JSON-serializable-args Celery entrypoint
(Celery task arguments must serialize through the broker, so it can't take an
AgentDeps directly). run_generation_for_requirement does the actual work and
takes an injectable AgentDeps, so it's directly testable without a live Gemini
key or a real Celery broker/worker process.
"""

import uuid
from typing import Any

from langchain_core.runnables import RunnableConfig

from testgen.generation.agents import AgentDeps, build_default_deps
from testgen.generation.checkpointer import postgres_checkpointer
from testgen.generation.graph import build_generation_graph
from testgen.generation.state import new_generation_state
from testgen.ingestion.models import Requirement
from testgen.platform.db.session import session_scope
from testgen.worker.celery_app import celery_app


def run_generation_for_requirement(
    requirement_id: str, *, deps: AgentDeps, max_retries: int = 3
) -> dict[str, Any]:
    """The slow, many-LLM-calls part (DESIGN.md §7: "background processing for
    slow LLM jobs"), run up to (and including) the human_approval interrupt.
    """
    with session_scope() as session:
        requirement = session.get(Requirement, uuid.UUID(requirement_id))
        if requirement is None:
            raise ValueError(f"No such requirement: {requirement_id}")
        requirement_text = requirement.text

    config: RunnableConfig = {"configurable": {"thread_id": requirement_id}}
    with postgres_checkpointer() as checkpointer:
        graph = build_generation_graph(deps, checkpointer=checkpointer)
        initial_state = new_generation_state(
            requirement_id, requirement_text, max_retries=max_retries
        )
        result = graph.invoke(initial_state, config)

    return {
        "requirement_id": requirement_id,
        "awaiting_approval": "__interrupt__" in result,
        "safety_class": result.get("safety_class"),
    }


# celery's task decorator isn't fully typed even though the package is found
# (same class of gap as presidio, Phase 5).
@celery_app.task(name="testgen.generate_test_cases")  # type: ignore[untyped-decorator]
def generate_test_cases_task(requirement_id: str, max_retries: int = 3) -> dict[str, Any]:
    return run_generation_for_requirement(
        requirement_id, deps=build_default_deps(), max_retries=max_retries
    )
