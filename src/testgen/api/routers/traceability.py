"""RTM and coverage-gap views (DESIGN.md §10 verification plan)."""

import uuid
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from testgen.api.deps import CurrentUser, DbSession
from testgen.api.routers.documents import get_owned_project
from testgen.api.routers.requirements import get_generation_status_for
from testgen.generation.agents import build_readonly_deps
from testgen.generation.checkpointer import postgres_checkpointer
from testgen.generation.graph import build_generation_graph
from testgen.ingestion.models import Requirement
from testgen.traceability.service import find_coverage_gaps, generate_rtm
from testgen.worker.tasks import generate_test_cases_task

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["traceability"])


@router.get("/rtm")
def rtm(project_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    get_owned_project(db, user, project_id)
    rows = generate_rtm(db, project_id=project_id)
    return [
        {
            "requirement_id": str(row.requirement_id),
            "external_ref": row.external_ref,
            "requirement_text": row.requirement_text,
            "safety_class": row.safety_class,
            "test_cases": row.test_cases,
            "compliance_standards": row.compliance_standards,
        }
        for row in rows
    ]


@router.get("/coverage-gaps")
def coverage_gaps(project_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    get_owned_project(db, user, project_id)
    gaps = find_coverage_gaps(db, project_id=project_id)
    return [
        {
            "requirement_id": str(gap.requirement_id),
            "external_ref": gap.external_ref,
            "safety_class": gap.safety_class,
            "missing_test_types": gap.missing_test_types,
        }
        for gap in gaps
    ]


@router.post("/generate-all-pending")
def generate_all_pending(project_id: uuid.UUID, user: CurrentUser, db: DbSession) -> dict[str, Any]:
    """Enqueues generation for every requirement in the project that hasn't been
    started yet -- skips anything already in_progress/awaiting_approval/completed
    so this is safe to click repeatedly (e.g. after adding new requirements to
    an existing project) without re-triggering or duplicating work already done.

    Still one Celery task per requirement under the hood (worker/tasks.py's
    generate_test_cases_task is unchanged) -- this only removes the need to
    click "Generate" once per requirement from the UI. Each still pauses at its
    own human_approval interrupt; this does not bulk-approve anything.
    """
    get_owned_project(db, user, project_id)
    requirements = (
        db.execute(select(Requirement).where(Requirement.project_id == project_id))
        .scalars()
        .all()
    )

    queued: list[str] = []
    skipped: list[dict[str, str]] = []
    with postgres_checkpointer() as checkpointer:
        graph = build_generation_graph(build_readonly_deps(), checkpointer=checkpointer)
        for requirement in requirements:
            current_status = get_generation_status_for(graph, requirement.id)
            if current_status == "not_started":
                generate_test_cases_task.delay(str(requirement.id))
                queued.append(str(requirement.id))
            else:
                skipped.append({"requirement_id": str(requirement.id), "status": current_status})

    return {"queued": queued, "skipped": skipped}


@router.get("/pending-approvals")
def pending_approvals(project_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    """Every requirement in the project currently paused at the human_approval
    interrupt -- backs the Review Queue page so a reviewer sees all of them in
    one place instead of navigating to each requirement individually to check
    its status first. Each item here still gets approved/rejected one at a
    time (client.pending_approval + approve/reject per requirement_id) -- this
    only lists which ones are waiting, it doesn't bulk-approve them.
    """
    get_owned_project(db, user, project_id)
    requirements = (
        db.execute(select(Requirement).where(Requirement.project_id == project_id))
        .scalars()
        .all()
    )

    waiting: list[dict[str, Any]] = []
    with postgres_checkpointer() as checkpointer:
        graph = build_generation_graph(build_readonly_deps(), checkpointer=checkpointer)
        for requirement in requirements:
            if get_generation_status_for(graph, requirement.id) == "awaiting_approval":
                waiting.append(
                    {
                        "requirement_id": str(requirement.id),
                        "external_ref": requirement.external_ref,
                        "requirement_text": requirement.text,
                    }
                )
    return waiting
