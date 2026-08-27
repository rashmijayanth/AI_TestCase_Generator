"""Integration test: the full requirement generation lifecycle through the
real FastAPI TestClient + real Postgres + real persistent checkpointer.

generate/status/pending-approval/approve/reject are exercised through the API
(that's the actual thing under test). The Celery task itself is not run here --
`trigger_generation` only enqueues to Redis, and nothing in this test suite
runs a Celery worker to consume it (that's Celery's own well-tested
machinery, not something this project needs to re-verify). To populate the
checkpoint the API endpoints then read, this test calls
run_generation_for_requirement directly with scripted deps -- simulating
"the worker already did its job" -- then drives generation-status,
pending-approval, and approve/reject entirely through the API.

Deliberately does NOT override get_db with the rolled-back db_session fixture
here (unlike the other API test files): run_generation_for_requirement reads
the requirement via its own separate session_scope() connection, which --
under Postgres's READ COMMITTED isolation -- cannot see uncommitted rows from
a different, still-open transaction. The API needs to really commit for the
"separate worker process" simulation to see its data, exactly like the real
system (a real API request and a real worker process are, in fact, separate
connections). Consequence: this test's rows are not auto-rolled-back and
persist in the local dev Postgres afterward -- accepted for the same reason as
tests/integration/test_worker_tasks.py (single-developer local DB, unique
random org/email per test avoids collisions across runs). db_session is
still used below, but only for read-only verification queries -- READ
COMMITTED means a statement run on it after the API's commits still sees them.
"""

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from testgen.api.app import create_app
from testgen.generation.agents import AgentDeps
from testgen.generation.models import TestCase
from testgen.knowledge.corpus import seed_regulatory_corpus
from testgen.knowledge.embeddings import EMBEDDING_DIMENSION, DeterministicFakeEmbedder
from testgen.knowledge.vector_store import MilvusVectorStore
from testgen.platform.audit import verify_chain
from testgen.platform.db.session import session_scope
from testgen.platform.models import AuditLog, User, UserRole
from testgen.traceability.models import TraceabilityLink
from testgen.worker.tasks import run_generation_for_requirement
from tests.fakes import ScriptedChatModelFactory

_ANALYSIS_RESPONSE = '{"safety_class": "C", "rationale": "Failure could delay treatment."}'
_SUFFICIENT_RESPONSE = '{"sufficient": true, "refined_query": ""}'
_PLAN_RESPONSE = (
    '{"test_types": ["safety_critical"], "rationale": "Class C needs failure-mode coverage."}'
)
_TEST_CASE_RESPONSE = (
    '{"test_cases": [{"title": "Occlusion alarm stops infusion", "test_type": "safety_critical", '
    '"preconditions": "Pump running", "steps": [{"step_no": 1, "action": "Trigger occlusion", '
    '"expected": "Halts within 500ms"}], "expected_result": "Halts", "priority": "critical"}]}'
)
_APPROVED_RESPONSE = '{"approved": true, "feedback": "", "cited_clause_refs": ["5.5.3"]}'


@pytest.fixture
def client() -> Iterator[TestClient]:
    # No get_db override here -- see module docstring for why this test needs
    # the API's writes to be genuinely committed, not held in a rolled-back
    # transaction.
    with TestClient(create_app()) as test_client:
        yield test_client


def _register_and_login(client: TestClient) -> dict[str, str]:
    email = f"qa-{uuid.uuid4()}@acme.health"
    client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": f"Acme Health {email}",
            "email": email,
            "full_name": "QA Reviewer",
            "password": "correct horse battery staple",
        },
    )
    token = client.post(
        "/api/v1/auth/token", data={"username": email, "password": "correct horse battery staple"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_project_and_requirement(client: TestClient, headers: dict[str, str]) -> str:
    project_id = client.post(
        "/api/v1/projects", json={"name": "Infusion Pump Firmware"}, headers=headers
    ).json()["id"]
    upload = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={
            "file": (
                "srs.md",
                b"REQ-001: The system shall stop infusion within 500ms of an occlusion alarm.\n",
                "text/markdown",
            )
        },
        headers=headers,
    ).json()
    return str(upload["requirement_ids"][0])


def _run_worker_directly(requirement_id: str, tmp_path: Path) -> None:
    embedder = DeterministicFakeEmbedder(dimension=EMBEDDING_DIMENSION)
    store = MilvusVectorStore(
        uri=str(tmp_path / "requirements_api_test.db"), dimension=EMBEDDING_DIMENSION
    )
    seed_regulatory_corpus(embedder, store)
    factory = ScriptedChatModelFactory(
        {
            "RequirementAnalysisOutput": [_ANALYSIS_RESPONSE],
            "SufficiencyCheckOutput": [_SUFFICIENT_RESPONSE],
            "TestPlanOutput": [_PLAN_RESPONSE],
            "TestCaseGeneratorOutput": [_TEST_CASE_RESPONSE],
            "ComplianceCritiqueOutput": [_APPROVED_RESPONSE],
        }
    )
    deps = AgentDeps(chat_model_factory=factory, embedder=embedder, vector_store=store)
    run_generation_for_requirement(requirement_id, deps=deps)


@pytest.mark.integration
def test_trigger_generation_enqueues_without_error(client: TestClient) -> None:
    headers = _register_and_login(client)
    requirement_id = _create_project_and_requirement(client, headers)

    response = client.post(f"/api/v1/requirements/{requirement_id}/generate", headers=headers)

    assert response.status_code == 202
    assert response.json()["status"] == "queued"


@pytest.mark.integration
def test_generation_status_reports_not_started_before_any_run(client: TestClient) -> None:
    headers = _register_and_login(client)
    requirement_id = _create_project_and_requirement(client, headers)

    response = client.get(
        f"/api/v1/requirements/{requirement_id}/generation-status", headers=headers
    )

    assert response.json()["status"] == "not_started"


@pytest.mark.integration
def test_full_lifecycle_generate_status_pending_approve(
    client: TestClient, db_session: Session, tmp_path: Path
) -> None:
    headers = _register_and_login(client)
    requirement_id = _create_project_and_requirement(client, headers)

    _run_worker_directly(requirement_id, tmp_path)

    status_response = client.get(
        f"/api/v1/requirements/{requirement_id}/generation-status", headers=headers
    )
    assert status_response.json()["status"] == "awaiting_approval"

    pending_response = client.get(
        f"/api/v1/requirements/{requirement_id}/pending-approval", headers=headers
    )
    assert pending_response.status_code == 200
    pending_body = pending_response.json()
    assert pending_body["safety_class"] == "C"
    assert len(pending_body["draft_test_cases"]) == 1

    approve_response = client.post(
        f"/api/v1/requirements/{requirement_id}/approve", headers=headers
    )
    assert approve_response.status_code == 200
    approve_body = approve_response.json()
    assert approve_body["status"] == "approved"
    assert approve_body["test_cases_created"] == 1
    assert approve_body["alm_sync"] == []  # no JIRA_BASE_URL configured in this environment

    # Scoped to this requirement, not "the whole table" -- this test doesn't
    # get transaction isolation from other tests (see module docstring), so
    # other tests' committed rows are legitimately still there.
    links = (
        db_session.execute(
            select(TraceabilityLink).where(
                TraceabilityLink.requirement_id == uuid.UUID(requirement_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(links) == 1
    assert links[0].is_locked is True

    created_test_cases = (
        db_session.execute(select(TestCase).where(TestCase.id == links[0].test_case_id))
        .scalars()
        .all()
    )
    assert len(created_test_cases) == 1
    assert created_test_cases[0].status.value == "approved"

    assert verify_chain(db_session) is True

    final_status = client.get(
        f"/api/v1/requirements/{requirement_id}/generation-status", headers=headers
    )
    assert final_status.json()["status"] == "completed"


@pytest.mark.integration
def test_reject_records_audit_entry_and_creates_no_test_cases(
    client: TestClient, db_session: Session, tmp_path: Path
) -> None:
    headers = _register_and_login(client)
    requirement_id = _create_project_and_requirement(client, headers)

    _run_worker_directly(requirement_id, tmp_path)

    reject_response = client.post(f"/api/v1/requirements/{requirement_id}/reject", headers=headers)

    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"
    assert reject_response.json()["test_cases_created"] == 0

    # Scoped to this requirement, not "the whole table is empty" -- this test
    # doesn't get transaction isolation from other tests (see module
    # docstring), so other tests' committed rows are legitimately still there.
    links_for_this_requirement = (
        db_session.execute(
            select(TraceabilityLink).where(
                TraceabilityLink.requirement_id == uuid.UUID(requirement_id)
            )
        )
        .scalars()
        .all()
    )
    assert links_for_this_requirement == []
    [event] = (
        db_session.execute(select(AuditLog).where(AuditLog.entity_id == requirement_id))
        .scalars()
        .all()
    )
    assert event.action == "requirement.generation_rejected"


@pytest.mark.integration
def test_pending_approval_returns_409_when_nothing_is_pending(client: TestClient) -> None:
    headers = _register_and_login(client)
    requirement_id = _create_project_and_requirement(client, headers)

    response = client.get(
        f"/api/v1/requirements/{requirement_id}/pending-approval", headers=headers
    )

    assert response.status_code == 409


@pytest.mark.integration
def test_approve_forbidden_for_user_without_admin_role(client: TestClient, tmp_path: Path) -> None:
    # register() always grants the "admin" role (see api/deps.py's
    # ADMIN_ROLE_NAME docstring) -- there's no API path to create a user
    # without it, so this simulates one by removing the role directly, the
    # only way to exercise the 403 branch of the RBAC gate on approve/reject.
    email = f"qa-{uuid.uuid4()}@acme.health"
    client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": f"Acme Health {email}",
            "email": email,
            "full_name": "QA Reviewer",
            "password": "correct horse battery staple",
        },
    )
    token = client.post(
        "/api/v1/auth/token", data={"username": email, "password": "correct horse battery staple"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    requirement_id = _create_project_and_requirement(client, headers)
    _run_worker_directly(requirement_id, tmp_path)

    with session_scope() as session:
        user = session.execute(select(User).where(User.email == email)).scalar_one()
        session.execute(delete(UserRole).where(UserRole.user_id == user.id))

    response = client.post(f"/api/v1/requirements/{requirement_id}/approve", headers=headers)

    assert response.status_code == 403


@pytest.mark.integration
def test_requirement_endpoints_reject_unowned_requirement(client: TestClient) -> None:
    owner_headers = _register_and_login(client)
    requirement_id = _create_project_and_requirement(client, owner_headers)
    intruder_headers = _register_and_login(client)

    response = client.get(
        f"/api/v1/requirements/{requirement_id}/generation-status", headers=intruder_headers
    )

    assert response.status_code == 404
