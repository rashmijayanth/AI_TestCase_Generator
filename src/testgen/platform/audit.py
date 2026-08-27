"""Append-only, hash-chained audit log (each row hashes the previous row).

Gives tamper-evidence for FDA Part 11 style audit trails: if any historical row's
payload is altered directly in the database, `verify_chain` detects it because the
recomputed hash for every row after the tampered one stops matching.
"""

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from testgen.platform.models import AuditLog

GENESIS_HASH = "0" * 64


def compute_row_hash(
    prev_hash: str,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any],
) -> str:
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    material = "|".join([prev_hash, action, entity_type, entity_id, canonical_payload])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def record_event(
    session: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | uuid.UUID,
    payload: dict[str, Any],
    organization_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> AuditLog:
    """Appends one row, chained to the current last row's hash. Caller commits."""
    last = session.execute(
        select(AuditLog).order_by(AuditLog.id.desc()).limit(1).with_for_update()
    ).scalar_one_or_none()
    prev_hash = last.row_hash if last is not None else GENESIS_HASH

    entity_id_str = str(entity_id)
    row_hash = compute_row_hash(prev_hash, action, entity_type, entity_id_str, payload)

    row = AuditLog(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id_str,
        payload=payload,
        prev_hash=None if last is None else prev_hash,
        row_hash=row_hash,
    )
    session.add(row)
    session.flush()
    return row


def verify_chain(session: Session) -> bool:
    """Walks the whole table in insertion order and confirms every row's hash recomputes."""
    rows = session.execute(select(AuditLog).order_by(AuditLog.id.asc())).scalars().all()
    expected_prev = GENESIS_HASH
    for row in rows:
        recomputed = compute_row_hash(
            expected_prev, row.action, row.entity_type, row.entity_id, row.payload
        )
        if recomputed != row.row_hash:
            return False
        expected_prev = row.row_hash
    return True
