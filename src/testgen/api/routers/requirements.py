"""Requirement-level generation lifecycle: trigger (Celery), check status,
view the pending-approval payload, and approve/reject -- resuming the graph,
persisting results, and syncing to Jira on approval.
"""

import uuid
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from testgen.api.deps import ADMIN_ROLE_NAME, CurrentUser, DbSession, require_roles
from testgen.api.routers.documents import get_owned_project
from testgen.generation.agents import build_readonly_deps
from testgen.generation.checkpointer import postgres_checkpointer
from testgen.generation.graph import build_generation_graph
from testgen.generation.orchestration import persist_generation_result
from testgen.generation.state import GenerationState
from testgen.ingestion.models import Requirement
from testgen.integrations.jira_adapter import get_jira_adapter
from testgen.integrations.service import sync_test_case
from testgen.platform.config import get_settings
from testgen.platform.enums import ALMSystem
from testgen.platform.models import User
from testgen.worker.tasks import generate_test_cases_task

router = APIRouter(prefix="/api/v1/requirements", tags=["requirements"])


def get_owned_requirement(
    db: DbSession, user: CurrentUser, requirement_id: uuid.UUID
) -> Requirement:
    requirement = db.get(Requirement, requirement_id)
    if requirement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    get_owned_project(db, user, requirement.project_id)
    return requirement


@router.post("/{requirement_id}/generate", status_code=status.HTTP_202_ACCEPTED)
def trigger_generation(
    requirement_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> dict[str, str]:
    get_owned_requirement(db, user, requirement_id)
    generate_test_cases_task.delay(str(requirement_id))
    return {"requirement_id": str(requirement_id), "status": "queued"}


def _status_from_snapshot(snapshot: Any) -> str:
    if not snapshot.values:
        return "not_started"
    if snapshot.next == ("human_approval",):
        return "awaiting_approval"
    if snapshot.next == ():
        return "completed"
    return "in_progress"


def get_generation_status_for(graph: Any, requirement_id: uuid.UUID | str) -> str:
    """Shared by the single-requirement endpoint below and the project-level
    bulk-trigger endpoint (traceability.py) -- the latter builds one graph and
    reuses it across every requirement in the project rather than paying the
    build_generation_graph cost per requirement.
    """
    config: RunnableConfig = {"configurable": {"thread_id": str(requirement_id)}}
    snapshot = graph.get_state(config)
    return _status_from_snapshot(snapshot)


@router.get("/{requirement_id}/generation-status")
def generation_status(
    requirement_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> dict[str, Any]:
    get_owned_requirement(db, user, requirement_id)

    # Reading a persisted checkpoint never executes a node, so this never
    # needs a real GEMINI_API_KEY -- see build_readonly_deps's docstring.
    with postgres_checkpointer() as checkpointer:
        graph = build_generation_graph(build_readonly_deps(), checkpointer=checkpointer)
        return {"status": get_generation_status_for(graph, requirement_id)}


@router.get("/{requirement_id}/pending-approval")
def pending_approval(requirement_id: uuid.UUID, user: CurrentUser, db: DbSession) -> dict[str, Any]:
    get_owned_requirement(db, user, requirement_id)
    config: RunnableConfig = {"configurable": {"thread_id": str(requirement_id)}}

    with postgres_checkpointer() as checkpointer:
        graph = build_generation_graph(build_readonly_deps(), checkpointer=checkpointer)
        snapshot = graph.get_state(config)

    if snapshot.next != ("human_approval",):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No generation run awaiting approval for this requirement",
        )

    for task in snapshot.tasks:
        if task.interrupts:
            return dict(task.interrupts[0].value)

    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No pending interrupt found")


# Locking in a human-approval decision is the most consequential action in this
# system (DESIGN.md §2: it's what makes the audit trail meaningful) -- gated on
# a role, not just any authenticated org member. See ADMIN_ROLE_NAME's docstring
# in api/deps.py for the scope of RBAC actually built here.
Reviewer = Annotated[User, Depends(require_roles(ADMIN_ROLE_NAME))]


@router.post("/{requirement_id}/approve")
def approve_generation(requirement_id: uuid.UUID, user: Reviewer, db: DbSession) -> dict[str, Any]:
    return _resume_and_persist(requirement_id, user, db, approved=True)


@router.post("/{requirement_id}/reject")
def reject_generation(requirement_id: uuid.UUID, user: Reviewer, db: DbSession) -> dict[str, Any]:
    return _resume_and_persist(requirement_id, user, db, approved=False)


def _resume_and_persist(
    requirement_id: uuid.UUID, user: CurrentUser, db: DbSession, *, approved: bool
) -> dict[str, Any]:
    requirement = get_owned_requirement(db, user, requirement_id)
    settings = get_settings()
    config: RunnableConfig = {"configurable": {"thread_id": str(requirement_id)}}

    # Resuming only runs human_approval (pure) and traceability_agent (pure) --
    # no LLM/embedding calls happen after the interrupt, so read-only deps are
    # correct here too, not build_default_deps().
    with postgres_checkpointer() as checkpointer:
        graph = build_generation_graph(build_readonly_deps(), checkpointer=checkpointer)
        final_state = graph.invoke(
            Command(resume={"approved": approved, "approver_id": str(user.id)}), config
        )

    created = persist_generation_result(
        db,
        project_id=requirement.project_id,
        requirement_id=requirement_id,
        organization_id=user.organization_id,
        final_state=cast(GenerationState, final_state),
        model_name=settings.gemini_model,
    )

    sync_results: list[dict[str, str]] = []
    if approved and settings.jira_base_url:
        adapter = get_jira_adapter(settings)
        for test_case in created:
            record = sync_test_case(
                db, test_case=test_case, adapter=adapter, alm_system=ALMSystem.JIRA
            )
            sync_results.append(
                {"test_case_id": str(test_case.id), "sync_status": record.sync_status.value}
            )

    return {
        "requirement_id": str(requirement_id),
        "status": "approved" if approved else "rejected",
        "test_cases_created": len(created),
        "alm_sync": sync_results,
    }
