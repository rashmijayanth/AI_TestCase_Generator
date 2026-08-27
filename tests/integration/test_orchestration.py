"""Integration test: persist_generation_result against the real local Postgres
container. Builds a plausible final GenerationState by hand rather than
running the whole graph -- the graph's own mechanics are already covered by
tests/integration/test_generation_graph.py; this is about the persistence step.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from testgen.generation.models import TestDataset
from testgen.generation.orchestration import persist_generation_result
from testgen.generation.state import GenerationState, new_generation_state
from testgen.ingestion.models import Requirement, SourceDocument
from testgen.platform.audit import verify_chain
from testgen.platform.enums import DocumentFormat, RequirementStatus
from testgen.platform.models import AuditLog, Organization, Project, User
from testgen.traceability.models import TraceabilityLink


def _make_requirement_and_user(session: Session) -> tuple[Project, Requirement, User]:
    org = Organization(name="Acme Health")
    session.add(org)
    session.flush()
    project = Project(organization_id=org.id, name="Infusion Pump Firmware")
    user = User(
        organization_id=org.id, email="qa@acme.health", full_name="QA", hashed_password="hash"
    )
    session.add_all([project, user])
    session.flush()
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
        status=RequirementStatus.CLASSIFIED,
    )
    session.add(requirement)
    session.flush()
    return project, requirement, user


def _approved_state(requirement: Requirement, approver_id: str) -> GenerationState:
    state = new_generation_state(str(requirement.id), requirement.text)
    state["safety_class"] = "C"
    state["draft_test_cases"] = [
        {
            "title": "Occlusion alarm stops infusion",
            "test_type": "safety_critical",
            "preconditions": "Pump running",
            "steps": [{"step_no": 1, "action": "Trigger occlusion", "expected": "Halts <=500ms"}],
            "expected_result": "Infusion halts and alarm sounds",
            "priority": "critical",
        },
        {
            "title": "Boundary timing sweep",
            "test_type": "data_driven",
            "preconditions": "Pump running",
            "steps": [{"step_no": 1, "action": "Vary occlusion delay", "expected": "Consistent"}],
            "expected_result": "Halts at or before threshold",
            "priority": "high",
        },
    ]
    state["draft_test_datasets"] = [
        {
            "name": "occlusion-timing-values",
            "data": [{"delay_ms": 499}, {"delay_ms": 500}],
            "phi_redacted": True,
            "test_case_title": "Boundary timing sweep",
        }
    ]
    state["critic_approved"] = True
    state["human_approved"] = True
    state["human_approver_id"] = approver_id
    return state


@pytest.mark.integration
def test_persist_generation_result_creates_test_cases_datasets_and_locked_links(
    db_session: Session,
) -> None:
    project, requirement, user = _make_requirement_and_user(db_session)
    state = _approved_state(requirement, str(user.id))

    created = persist_generation_result(
        db_session,
        project_id=project.id,
        requirement_id=requirement.id,
        organization_id=project.organization_id,
        final_state=state,
        model_name="gemini-2.0-flash",
    )

    assert len(created) == 2
    safety_critical = next(tc for tc in created if tc.test_type.value == "safety_critical")
    data_driven = next(tc for tc in created if tc.test_type.value == "data_driven")

    assert safety_critical.status.value == "approved"
    assert safety_critical.safety_class is not None
    assert safety_critical.safety_class.value == "C"
    assert safety_critical.approver_id == user.id
    assert safety_critical.generated_by_model == "gemini-2.0-flash"
    assert safety_critical.prompt_version == "v1"

    [dataset] = (
        db_session.execute(select(TestDataset).where(TestDataset.test_case_id == data_driven.id))
        .scalars()
        .all()
    )
    assert dataset.name == "occlusion-timing-values"
    assert dataset.phi_redacted is True

    links = (
        db_session.execute(
            select(TraceabilityLink).where(TraceabilityLink.requirement_id == requirement.id)
        )
        .scalars()
        .all()
    )
    assert len(links) == 2
    assert all(link.is_locked for link in links)
    assert all(link.locked_by == user.id for link in links)
    assert verify_chain(db_session) is True


@pytest.mark.integration
def test_persist_generation_result_records_rejection_without_creating_test_cases(
    db_session: Session,
) -> None:
    _project, requirement, user = _make_requirement_and_user(db_session)
    state = new_generation_state(str(requirement.id), requirement.text)
    state["draft_test_cases"] = [{"title": "t", "test_type": "functional", "priority": "low"}]
    state["critic_approved"] = False
    state["critic_feedback"] = "Missing a boundary-value test."
    state["human_approved"] = False
    state["human_approver_id"] = str(user.id)

    created = persist_generation_result(
        db_session,
        project_id=_project.id,
        requirement_id=requirement.id,
        organization_id=_project.organization_id,
        final_state=state,
        model_name="gemini-2.0-flash",
    )

    assert created == []
    [event] = (
        db_session.execute(select(AuditLog).where(AuditLog.entity_id == str(requirement.id)))
        .scalars()
        .all()
    )
    assert event.action == "requirement.generation_rejected"
    assert "boundary-value" in event.payload["critic_feedback"]


@pytest.mark.integration
def test_persist_generation_result_rejects_approval_with_no_approver(db_session: Session) -> None:
    project, requirement, _user = _make_requirement_and_user(db_session)
    state = new_generation_state(str(requirement.id), requirement.text)
    state["human_approved"] = True
    state["human_approver_id"] = None

    with pytest.raises(ValueError, match="human_approver_id"):
        persist_generation_result(
            db_session,
            project_id=project.id,
            requirement_id=requirement.id,
            organization_id=project.organization_id,
            final_state=state,
            model_name="gemini-2.0-flash",
        )
