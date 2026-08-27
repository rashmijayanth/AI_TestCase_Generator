"""Audit log view, organization-scoped (DESIGN.md §10 verification plan)."""

from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from testgen.api.deps import CurrentUser, DbSession
from testgen.platform.models import AuditLog

router = APIRouter(prefix="/api/v1/audit-log", tags=["audit"])


@router.get("")
def list_audit_log(user: CurrentUser, db: DbSession, limit: int = 100) -> list[dict[str, Any]]:
    events = (
        db.execute(
            select(AuditLog)
            .where(AuditLog.organization_id == user.organization_id)
            .order_by(AuditLog.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": event.id,
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "payload": event.payload,
            "created_at": event.created_at.isoformat(),
        }
        for event in events
    ]
