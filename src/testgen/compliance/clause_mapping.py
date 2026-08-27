"""ComplianceMapping CRUD -- artifact <-> standard <-> clause <-> rationale."""

import uuid

from sqlalchemy.orm import Session

from testgen.compliance.models import ComplianceMapping
from testgen.platform.enums import Standard


def create_compliance_mapping(
    session: Session,
    *,
    standard: Standard,
    clause_ref: str,
    rationale: str,
    requirement_id: uuid.UUID | None = None,
    test_case_id: uuid.UUID | None = None,
) -> ComplianceMapping:
    """A clear application-level error instead of letting the DB's CHECK constraint
    (Phase 1) raise a raw IntegrityError for the same "exactly one" invariant.
    """
    if (requirement_id is None) == (test_case_id is None):
        raise ValueError("Exactly one of requirement_id or test_case_id must be set")
    mapping = ComplianceMapping(
        requirement_id=requirement_id,
        test_case_id=test_case_id,
        standard=standard,
        clause_ref=clause_ref,
        rationale=rationale,
    )
    session.add(mapping)
    session.flush()
    return mapping
