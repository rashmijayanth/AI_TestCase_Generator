"""Ties an ALMPort adapter to the ALMSyncRecord model: records every sync
attempt, success or failure -- a failed sync is data (DESIGN.md §5's
alm_sync_records), never an unhandled exception bubbling out of this call.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from testgen.generation.models import TestCase
from testgen.integrations.models import ALMSyncRecord
from testgen.integrations.port import ALMPort
from testgen.platform.enums import ALMSystem, SyncStatus


def sync_test_case(
    session: Session, *, test_case: TestCase, adapter: ALMPort, alm_system: ALMSystem
) -> ALMSyncRecord:
    record = ALMSyncRecord(
        test_case_id=test_case.id, alm_system=alm_system, sync_status=SyncStatus.PENDING
    )
    session.add(record)
    session.flush()

    try:
        issue_ref = adapter.create_test_case_issue(
            title=test_case.title,
            description=test_case.expected_result,
            priority=test_case.priority.value,
            labels=[test_case.test_type.value],
        )
    except Exception as exc:
        # Any adapter failure (network, auth, malformed response) becomes a
        # recorded FAILED sync, not a crash -- the caller can retry later.
        record.sync_status = SyncStatus.FAILED
        record.error_message = str(exc)
        session.flush()
        return record

    record.external_id = issue_ref.external_id
    record.external_url = issue_ref.external_url
    record.sync_status = SyncStatus.SYNCED
    record.last_synced_at = datetime.now(UTC)
    session.flush()
    return record
