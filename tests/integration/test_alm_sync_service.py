"""Integration test: sync_test_case against the real local Postgres container,
using a fake ALMPort (the adapters themselves are tested independently --
unit for Jira, contract for Azure DevOps/Polarion). This is about
ALMSyncRecord persistence and failure handling, not any one adapter.
"""

import pytest
from sqlalchemy.orm import Session

from testgen.generation.models import TestCase
from testgen.integrations.port import ALMIssueRef
from testgen.integrations.service import sync_test_case
from testgen.platform.enums import ALMSystem, SyncStatus, TestPriority, TestType
from testgen.platform.models import Organization, Project


class _FakeSucceedingAdapter:
    def create_test_case_issue(
        self, *, title: str, description: str, priority: str, labels: list[str]
    ) -> ALMIssueRef:
        return ALMIssueRef(
            external_id="TESTGEN-1", external_url="https://acme.atlassian.net/browse/TESTGEN-1"
        )


class _FakeFailingAdapter:
    def create_test_case_issue(
        self, *, title: str, description: str, priority: str, labels: list[str]
    ) -> ALMIssueRef:
        raise ConnectionError("Jira Cloud unreachable")


def _make_test_case(session: Session) -> TestCase:
    org = Organization(name="Acme Health")
    session.add(org)
    session.flush()
    project = Project(organization_id=org.id, name="Infusion Pump Firmware")
    session.add(project)
    session.flush()
    test_case = TestCase(
        project_id=project.id,
        title="Occlusion alarm stops infusion",
        test_type=TestType.SAFETY_CRITICAL,
        priority=TestPriority.CRITICAL,
        expected_result="Infusion halts within 500ms",
    )
    session.add(test_case)
    session.flush()
    return test_case


@pytest.mark.integration
def test_sync_test_case_records_success(db_session: Session) -> None:
    test_case = _make_test_case(db_session)

    record = sync_test_case(
        db_session, test_case=test_case, adapter=_FakeSucceedingAdapter(), alm_system=ALMSystem.JIRA
    )

    assert record.sync_status == SyncStatus.SYNCED
    assert record.external_id == "TESTGEN-1"
    assert record.external_url.startswith("https://acme.atlassian.net")
    assert record.last_synced_at is not None
    assert record.error_message == ""


@pytest.mark.integration
def test_sync_test_case_records_failure_without_raising(db_session: Session) -> None:
    test_case = _make_test_case(db_session)

    record = sync_test_case(
        db_session, test_case=test_case, adapter=_FakeFailingAdapter(), alm_system=ALMSystem.JIRA
    )

    assert record.sync_status == SyncStatus.FAILED
    assert "unreachable" in record.error_message
    assert record.external_id == ""
