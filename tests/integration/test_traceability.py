"""Integration tests for traceability link creation/locking, coverage-gap
analysis, and RTM generation, against the real local Postgres container.
"""

import pytest
from sqlalchemy.orm import Session

from testgen.compliance.clause_mapping import create_compliance_mapping
from testgen.generation.models import TestCase
from testgen.ingestion.models import Requirement, SourceDocument
from testgen.platform.audit import verify_chain
from testgen.platform.enums import (
    DocumentFormat,
    RequirementStatus,
    SafetyClass,
    Standard,
    TestCaseStatus,
    TestPriority,
    TestType,
)
from testgen.platform.models import Organization, Project, User
from testgen.traceability.service import (
    create_traceability_link,
    find_coverage_gaps,
    generate_rtm,
    lock_traceability_links_for_requirement,
)


def _make_project_and_user(session: Session) -> tuple[Project, User]:
    org = Organization(name="Acme Health")
    session.add(org)
    session.flush()
    project = Project(organization_id=org.id, name="Infusion Pump Firmware")
    user = User(
        organization_id=org.id,
        email="qa@acme.health",
        full_name="QA Reviewer",
        hashed_password="hash",
    )
    session.add_all([project, user])
    session.flush()
    return project, user


def _make_requirement(
    session: Session, project: Project, *, safety_class: SafetyClass | None
) -> Requirement:
    doc = SourceDocument(
        project_id=project.id,
        filename="srs.md",
        file_format=DocumentFormat.MARKDOWN,
        checksum="a" * 64,
        storage_key="k",
    )
    session.add(doc)
    session.flush()
    requirement = Requirement(
        source_document_id=doc.id,
        project_id=project.id,
        external_ref="REQ-001",
        text="The pump shall stop infusion within 500ms of an occlusion alarm.",
        safety_class=safety_class,
        status=RequirementStatus.CLASSIFIED,
    )
    session.add(requirement)
    session.flush()
    return requirement


def _make_test_case(session: Session, project: Project, test_type: TestType) -> TestCase:
    test_case = TestCase(
        project_id=project.id,
        title=f"{test_type.value} test",
        test_type=test_type,
        priority=TestPriority.HIGH,
        status=TestCaseStatus.DRAFT,
    )
    session.add(test_case)
    session.flush()
    return test_case


@pytest.mark.integration
def test_link_creation_starts_unlocked_then_lock_sets_audit_trail(db_session: Session) -> None:
    project, user = _make_project_and_user(db_session)
    requirement = _make_requirement(db_session, project, safety_class=SafetyClass.C)
    test_case = _make_test_case(db_session, project, TestType.SAFETY_CRITICAL)

    link = create_traceability_link(
        db_session, requirement_id=requirement.id, test_case_id=test_case.id
    )
    assert link.is_locked is False
    assert link.locked_by is None

    locked = lock_traceability_links_for_requirement(
        db_session,
        requirement_id=requirement.id,
        approver_id=user.id,
        organization_id=project.organization_id,
    )

    assert len(locked) == 1
    assert locked[0].is_locked is True
    assert locked[0].locked_by == user.id
    assert locked[0].locked_at is not None
    assert verify_chain(db_session) is True


@pytest.mark.integration
def test_locking_is_idempotent_for_already_locked_links(db_session: Session) -> None:
    project, user = _make_project_and_user(db_session)
    requirement = _make_requirement(db_session, project, safety_class=SafetyClass.A)
    test_case = _make_test_case(db_session, project, TestType.FUNCTIONAL)
    create_traceability_link(db_session, requirement_id=requirement.id, test_case_id=test_case.id)

    first = lock_traceability_links_for_requirement(
        db_session,
        requirement_id=requirement.id,
        approver_id=user.id,
        organization_id=project.organization_id,
    )
    second = lock_traceability_links_for_requirement(
        db_session,
        requirement_id=requirement.id,
        approver_id=user.id,
        organization_id=project.organization_id,
    )

    assert len(first) == 1
    assert len(second) == 0  # nothing left unlocked to lock


@pytest.mark.integration
def test_find_coverage_gaps_flags_requirement_with_no_linked_test_cases(
    db_session: Session,
) -> None:
    project, _ = _make_project_and_user(db_session)
    requirement = _make_requirement(db_session, project, safety_class=SafetyClass.B)

    gaps = find_coverage_gaps(db_session, project_id=project.id)

    assert len(gaps) == 1
    assert gaps[0].requirement_id == requirement.id
    assert gaps[0].missing_test_types == ["(no test cases linked)"]


@pytest.mark.integration
def test_find_coverage_gaps_flags_missing_safety_critical_for_class_c(db_session: Session) -> None:
    project, _ = _make_project_and_user(db_session)
    requirement = _make_requirement(db_session, project, safety_class=SafetyClass.C)
    functional_case = _make_test_case(db_session, project, TestType.FUNCTIONAL)
    create_traceability_link(
        db_session, requirement_id=requirement.id, test_case_id=functional_case.id
    )

    gaps = find_coverage_gaps(db_session, project_id=project.id)

    assert len(gaps) == 1
    assert gaps[0].missing_test_types == ["safety_critical"]


@pytest.mark.integration
def test_find_coverage_gaps_reports_none_when_minimum_is_met(db_session: Session) -> None:
    project, _ = _make_project_and_user(db_session)
    requirement = _make_requirement(db_session, project, safety_class=SafetyClass.C)
    functional_case = _make_test_case(db_session, project, TestType.FUNCTIONAL)
    safety_case = _make_test_case(db_session, project, TestType.SAFETY_CRITICAL)
    create_traceability_link(
        db_session, requirement_id=requirement.id, test_case_id=functional_case.id
    )
    create_traceability_link(db_session, requirement_id=requirement.id, test_case_id=safety_case.id)

    gaps = find_coverage_gaps(db_session, project_id=project.id)

    assert gaps == []


@pytest.mark.integration
def test_generate_rtm_includes_test_cases_and_compliance_standards(db_session: Session) -> None:
    project, _ = _make_project_and_user(db_session)
    requirement = _make_requirement(db_session, project, safety_class=SafetyClass.C)
    test_case = _make_test_case(db_session, project, TestType.SAFETY_CRITICAL)
    create_traceability_link(db_session, requirement_id=requirement.id, test_case_id=test_case.id)
    create_compliance_mapping(
        db_session,
        standard=Standard.IEC_62304,
        clause_ref="5.5.3",
        rationale="Failure-mode verification",
        requirement_id=requirement.id,
    )

    [row] = generate_rtm(db_session, project_id=project.id)

    assert row.external_ref == "REQ-001"
    assert row.safety_class == "C"
    assert len(row.test_cases) == 1
    assert row.test_cases[0]["test_type"] == "safety_critical"
    assert row.compliance_standards == ["iec_62304"]
