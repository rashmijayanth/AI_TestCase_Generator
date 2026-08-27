"""RTM and coverage-gap views (DESIGN.md §10 verification plan)."""

import uuid
from typing import Any

from fastapi import APIRouter

from testgen.api.deps import CurrentUser, DbSession
from testgen.api.routers.documents import get_owned_project
from testgen.traceability.service import find_coverage_gaps, generate_rtm

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
