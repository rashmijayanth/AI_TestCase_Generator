"""Round-trips the full domain model graph (DESIGN.md §5) against the real local Postgres."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from testgen.compliance.models import ComplianceMapping
from testgen.generation.models import LLMGenerationRun, TestCase, TestDataset
from testgen.ingestion.models import Requirement, SourceDocument
from testgen.integrations.models import ALMSyncRecord
from testgen.platform.enums import (
    ALMSystem,
    DocumentFormat,
    RequirementStatus,
    SafetyClass,
    Standard,
    SyncStatus,
    TestCaseStatus,
    TestPriority,
    TestType,
)
from testgen.platform.models import Organization, Project, Role, User, UserRole
from testgen.traceability.models import TraceabilityLink


@pytest.mark.integration
def test_full_domain_graph_round_trip(db_session: Session) -> None:
    org = Organization(name="Acme Health")
    db_session.add(org)
    db_session.flush()

    project = Project(organization_id=org.id, name="Infusion Pump Firmware")
    user = User(
        organization_id=org.id,
        email="qa@acme.health",
        full_name="QA Reviewer",
        hashed_password="not-a-real-hash",
    )
    role = Role(name="qa_reviewer", description="Can approve test cases")
    db_session.add_all([project, user, role])
    db_session.flush()

    db_session.add(UserRole(user_id=user.id, role_id=role.id, organization_id=org.id))

    doc = SourceDocument(
        project_id=project.id,
        filename="infusion-pump-srs.pdf",
        file_format=DocumentFormat.PDF,
        checksum="a" * 64,
        storage_key="local/infusion-pump-srs.pdf",
        uploaded_by=user.id,
    )
    db_session.add(doc)
    db_session.flush()

    requirement = Requirement(
        source_document_id=doc.id,
        project_id=project.id,
        external_ref="REQ-001",
        text="The pump shall stop infusion within 500ms of an occlusion alarm.",
        safety_class=SafetyClass.C,
        status=RequirementStatus.CLASSIFIED,
    )
    db_session.add(requirement)
    db_session.flush()

    test_case = TestCase(
        project_id=project.id,
        title="Occlusion alarm stops infusion within 500ms",
        test_type=TestType.SAFETY_CRITICAL,
        steps=[
            {"step_no": 1, "action": "Trigger occlusion", "expected": "Infusion halts <= 500ms"}
        ],
        priority=TestPriority.CRITICAL,
        safety_class=SafetyClass.C,
        status=TestCaseStatus.DRAFT,
        generated_by_model="gemini-2.0-flash",
        prompt_version="v1",
    )
    db_session.add(test_case)
    db_session.flush()

    db_session.add(
        TraceabilityLink(requirement_id=requirement.id, test_case_id=test_case.id, is_locked=False)
    )
    db_session.add(
        TestDataset(
            test_case_id=test_case.id,
            name="occlusion-timing-values",
            data=[{"occlusion_delay_ms": v} for v in (0, 250, 499, 500, 501)],
            phi_redacted=True,
            generated_by_model="gemini-2.0-flash",
        )
    )
    db_session.add(
        ComplianceMapping(
            test_case_id=test_case.id,
            standard=Standard.IEC_62304,
            clause_ref="5.5.3",
            rationale="Verifies risk-control measure for occlusion failure mode.",
        )
    )
    db_session.add(
        LLMGenerationRun(
            agent_name="test_case_generator",
            model="gemini-2.0-flash",
            prompt_version="v1",
            input_tokens=512,
            output_tokens=256,
            cost_usd=0.001,
            latency_ms=850,
            requirement_id=requirement.id,
            test_case_id=test_case.id,
        )
    )
    db_session.add(
        ALMSyncRecord(
            test_case_id=test_case.id, alm_system=ALMSystem.JIRA, sync_status=SyncStatus.PENDING
        )
    )
    db_session.flush()

    fetched = db_session.execute(select(TestCase).where(TestCase.id == test_case.id)).scalar_one()
    assert fetched.title.startswith("Occlusion alarm")
    assert len(fetched.datasets) == 1
    assert fetched.datasets[0].data[2]["occlusion_delay_ms"] == 499


@pytest.mark.integration
def test_compliance_mapping_requires_exactly_one_artifact(db_session: Session) -> None:
    with pytest.raises(IntegrityError):
        db_session.add(
            ComplianceMapping(standard=Standard.GDPR, clause_ref="Art. 17", rationale="neither set")
        )
        db_session.flush()
    db_session.rollback()
