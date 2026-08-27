"""Integration tests for ComplianceMapping CRUD and GDPR data-subject rights,
against the real local Postgres container.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from testgen.compliance.clause_mapping import create_compliance_mapping
from testgen.compliance.gdpr import erase_user_personal_data, export_user_data
from testgen.generation.models import TestCase
from testgen.ingestion.models import Requirement, SourceDocument
from testgen.platform.audit import record_event, verify_chain
from testgen.platform.enums import (
    DocumentFormat,
    RequirementStatus,
    Standard,
    TestCaseStatus,
    TestPriority,
    TestType,
)
from testgen.platform.models import AuditLog, Organization, Project, User


def _make_project(session: Session) -> Project:
    org = Organization(name="Acme Health")
    session.add(org)
    session.flush()
    project = Project(organization_id=org.id, name="Infusion Pump Firmware")
    session.add(project)
    session.flush()
    return project


@pytest.mark.integration
def test_create_compliance_mapping_requires_exactly_one_artifact(db_session: Session) -> None:
    with pytest.raises(ValueError, match="Exactly one"):
        create_compliance_mapping(
            db_session, standard=Standard.GDPR, clause_ref="Art.17", rationale="neither set"
        )

    project = _make_project(db_session)
    doc = SourceDocument(
        project_id=project.id,
        filename="srs.md",
        file_format=DocumentFormat.MARKDOWN,
        checksum="a" * 64,
        storage_key="k",
    )
    db_session.add(doc)
    db_session.flush()
    requirement = Requirement(
        source_document_id=doc.id,
        project_id=project.id,
        text="The pump shall alarm on occlusion.",
        status=RequirementStatus.EXTRACTED,
    )
    db_session.add(requirement)
    db_session.flush()

    with pytest.raises(ValueError, match="Exactly one"):
        create_compliance_mapping(
            db_session,
            standard=Standard.GDPR,
            clause_ref="Art.17",
            rationale="both set",
            requirement_id=requirement.id,
            test_case_id=requirement.id,
        )

    mapping = create_compliance_mapping(
        db_session,
        standard=Standard.IEC_62304,
        clause_ref="5.5.3",
        rationale="Verifies failure-mode handling",
        requirement_id=requirement.id,
    )

    assert mapping.id is not None
    assert mapping.standard == Standard.IEC_62304


@pytest.mark.integration
def test_export_user_data_gathers_everything_linked_to_the_user(db_session: Session) -> None:
    project = _make_project(db_session)
    user = User(
        organization_id=project.organization_id,
        email="qa@acme.health",
        full_name="QA Reviewer",
        hashed_password="not-a-real-hash",
    )
    db_session.add(user)
    db_session.flush()

    doc = SourceDocument(
        project_id=project.id,
        filename="srs.md",
        file_format=DocumentFormat.MARKDOWN,
        checksum="a" * 64,
        storage_key="k",
        uploaded_by=user.id,
    )
    db_session.add(doc)
    db_session.flush()

    test_case = TestCase(
        project_id=project.id,
        title="Occlusion alarm",
        test_type=TestType.SAFETY_CRITICAL,
        priority=TestPriority.CRITICAL,
        status=TestCaseStatus.APPROVED,
        approver_id=user.id,
    )
    db_session.add(test_case)
    db_session.add(
        AuditLog(
            actor_user_id=user.id,
            action="test_case.approved",
            entity_type="test_case",
            entity_id="tc-1",
            payload={},
            prev_hash=None,
            row_hash="0" * 64,
        )
    )
    db_session.flush()

    export = export_user_data(db_session, user.id)

    assert export["user"]["email"] == "qa@acme.health"
    assert len(export["audit_events"]) == 1
    assert export["audit_events"][0]["action"] == "test_case.approved"
    assert len(export["approved_test_cases"]) == 1
    assert len(export["uploaded_documents"]) == 1


@pytest.mark.integration
def test_export_user_data_raises_for_unknown_user(db_session: Session) -> None:
    with pytest.raises(ValueError, match="No such user"):
        export_user_data(db_session, uuid.uuid4())


@pytest.mark.integration
def test_erase_user_personal_data_raises_for_unknown_user(db_session: Session) -> None:
    with pytest.raises(ValueError, match="No such user"):
        erase_user_personal_data(db_session, uuid.uuid4())


@pytest.mark.integration
def test_erase_user_personal_data_scrubs_identity_without_touching_audit_chain(
    db_session: Session,
) -> None:
    project = _make_project(db_session)
    user = User(
        organization_id=project.organization_id,
        email="real.name@acme.health",
        full_name="Real Name",
        hashed_password="hash",
    )
    db_session.add(user)
    db_session.flush()

    record_event(
        db_session,
        action="user.login",
        entity_type="user",
        entity_id=user.id,
        payload={"ip": "127.0.0.1"},
        actor_user_id=user.id,
    )

    assert verify_chain(db_session) is True

    erased = erase_user_personal_data(db_session, user.id)

    assert erased.email != "real.name@acme.health"
    assert erased.full_name == "[erased]"
    assert erased.is_active is False
    # The audit chain never touched the User row's fields -- it stays valid.
    assert verify_chain(db_session) is True
