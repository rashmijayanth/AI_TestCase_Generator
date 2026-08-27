"""GDPR data-subject rights for this system's own users.

(Not the healthcare end-patients the generated test datasets are nominally
about -- those are synthetic by construction, see generation/agents.py's
Test Data Synthesizer, and redaction.py handles any PHI-like text reaching an
LLM. This module is about the login accounts in the `users` table.)
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from testgen.generation.models import TestCase
from testgen.ingestion.models import SourceDocument
from testgen.platform.models import AuditLog, User


def export_user_data(session: Session, user_id: uuid.UUID) -> dict[str, Any]:
    """GDPR Art. 15 (right of access): everything this system holds linked to one user."""
    user = session.get(User, user_id)
    if user is None:
        raise ValueError(f"No such user: {user_id}")

    audit_events = (
        session.execute(
            select(AuditLog).where(AuditLog.actor_user_id == user_id).order_by(AuditLog.id)
        )
        .scalars()
        .all()
    )
    approved_test_cases = (
        session.execute(select(TestCase).where(TestCase.approver_id == user_id)).scalars().all()
    )
    uploaded_documents = (
        session.execute(select(SourceDocument).where(SourceDocument.uploaded_by == user_id))
        .scalars()
        .all()
    )

    return {
        "user": {"id": str(user.id), "email": user.email, "full_name": user.full_name},
        "audit_events": [
            {
                "action": event.action,
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "created_at": event.created_at.isoformat(),
            }
            for event in audit_events
        ],
        "approved_test_cases": [
            {"id": str(tc.id), "title": tc.title} for tc in approved_test_cases
        ],
        "uploaded_documents": [
            {"id": str(doc.id), "filename": doc.filename} for doc in uploaded_documents
        ],
    }


def erase_user_personal_data(session: Session, user_id: uuid.UUID) -> User:
    """GDPR Art. 17 (right to erasure), reconciled with the audit log's Part 11
    tamper-evidence: only the identifying fields on the User row are scrubbed.
    audit_log rows referencing this user via actor_user_id are left completely
    untouched -- the hash chain covers action/entity_type/entity_id/payload,
    none of which changes here, so verify_chain() continues to pass unchanged.
    """
    user = session.get(User, user_id)
    if user is None:
        raise ValueError(f"No such user: {user_id}")
    user.email = f"erased-{user.id}@erased.invalid"
    user.full_name = "[erased]"
    user.hashed_password = ""
    user.is_active = False
    session.flush()
    return user
