"""Integration test: writes real audit_log rows and confirms tamper-evidence for real."""

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from testgen.platform.audit import record_event, verify_chain
from testgen.platform.models import AuditLog


@pytest.mark.integration
def test_chain_is_valid_after_several_events(db_session: Session) -> None:
    record_event(
        db_session,
        action="test_case.created",
        entity_type="test_case",
        entity_id="tc-1",
        payload={"title": "A"},
    )
    record_event(
        db_session,
        action="test_case.approved",
        entity_type="test_case",
        entity_id="tc-1",
        payload={"approver": "qa1"},
    )
    record_event(
        db_session,
        action="alm_sync.completed",
        entity_type="test_case",
        entity_id="tc-1",
        payload={"jira_key": "PORT-1"},
    )

    assert verify_chain(db_session) is True


@pytest.mark.integration
def test_tampering_with_a_row_breaks_the_chain(db_session: Session) -> None:
    record_event(db_session, action="a", entity_type="t", entity_id="1", payload={"v": 1})
    row2 = record_event(db_session, action="b", entity_type="t", entity_id="1", payload={"v": 2})
    record_event(db_session, action="c", entity_type="t", entity_id="1", payload={"v": 3})

    assert verify_chain(db_session) is True

    db_session.execute(update(AuditLog).where(AuditLog.id == row2.id).values(payload={"v": 999}))
    db_session.flush()

    assert verify_chain(db_session) is False
