"""Integration test: RTM, coverage-gaps, and audit-log endpoints through the
real FastAPI TestClient + real Postgres + real persistent checkpointer.

Same non-isolation rationale as test_requirements_api.py: run_generation_for_
requirement needs the API's writes to be genuinely committed. See that file's
module docstring for the full explanation.
"""

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from testgen.api.app import create_app
from testgen.generation.agents import AgentDeps
from testgen.knowledge.corpus import seed_regulatory_corpus
from testgen.knowledge.embeddings import EMBEDDING_DIMENSION, DeterministicFakeEmbedder
from testgen.knowledge.vector_store import MilvusVectorStore
from testgen.worker.tasks import run_generation_for_requirement
from tests.fakes import ScriptedChatModelFactory

_ANALYSIS_RESPONSE = '{"safety_class": "C", "rationale": "Failure could delay treatment."}'
_SUFFICIENT_RESPONSE = '{"sufficient": true, "refined_query": ""}'
# Class C's deterministic coverage floor (traceability/service.py) requires both
# functional and safety_critical -- script both so the "gaps resolve after
# approval" assertion below reflects a genuinely fully-covered requirement,
# not just whatever the (separate, LLM-driven) Test Strategist happened to plan.
_PLAN_RESPONSE = (
    '{"test_types": ["safety_critical", "functional"], '
    '"rationale": "Class C needs failure-mode coverage plus normal-path coverage."}'
)
_TEST_CASE_RESPONSE = (
    '{"test_cases": ['
    '{"title": "Occlusion alarm stops infusion", "test_type": "safety_critical", '
    '"preconditions": "Pump running", "steps": [{"step_no": 1, "action": "Trigger occlusion", '
    '"expected": "Halts within 500ms"}], "expected_result": "Halts", "priority": "critical"}, '
    '{"title": "Normal infusion completes", "test_type": "functional", '
    '"preconditions": "Pump idle", "steps": [{"step_no": 1, "action": "Start infusion", '
    '"expected": "Runs to completion"}], "expected_result": "Completes normally", '
    '"priority": "medium"}]}'
)
_APPROVED_RESPONSE = '{"approved": true, "feedback": "", "cited_clause_refs": ["5.5.3"]}'


@pytest.fixture
def client() -> Iterator[TestClient]:
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


def _create_project_and_requirement(client: TestClient, headers: dict[str, str]) -> tuple[str, str]:
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
    return project_id, str(upload["requirement_ids"][0])


def _run_worker_directly(requirement_id: str, tmp_path: Path) -> None:
    embedder = DeterministicFakeEmbedder(dimension=EMBEDDING_DIMENSION)
    store = MilvusVectorStore(
        uri=str(tmp_path / "traceability_api_test.db"), dimension=EMBEDDING_DIMENSION
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
def test_coverage_gaps_reports_missing_coverage_before_generation(client: TestClient) -> None:
    headers = _register_and_login(client)
    project_id, _requirement_id = _create_project_and_requirement(client, headers)

    response = client.get(f"/api/v1/projects/{project_id}/coverage-gaps", headers=headers)

    assert response.status_code == 200
    [gap] = response.json()
    assert gap["missing_test_types"] == ["(no test cases linked)"]


@pytest.mark.integration
def test_rtm_and_coverage_gaps_after_approval(client: TestClient, tmp_path: Path) -> None:
    headers = _register_and_login(client)
    project_id, requirement_id = _create_project_and_requirement(client, headers)
    _run_worker_directly(requirement_id, tmp_path)
    client.post(f"/api/v1/requirements/{requirement_id}/approve", headers=headers)

    rtm_response = client.get(f"/api/v1/projects/{project_id}/rtm", headers=headers)
    assert rtm_response.status_code == 200
    [row] = [r for r in rtm_response.json() if r["requirement_id"] == requirement_id]
    assert row["external_ref"] == "REQ-001"
    assert row["safety_class"] == "C"
    assert len(row["test_cases"]) == 2
    assert {tc["test_type"] for tc in row["test_cases"]} == {"safety_critical", "functional"}

    gaps_response = client.get(f"/api/v1/projects/{project_id}/coverage-gaps", headers=headers)
    assert gaps_response.status_code == 200
    matching_gaps = [g for g in gaps_response.json() if g["requirement_id"] == requirement_id]
    assert matching_gaps == []  # safety_critical coverage now satisfied


@pytest.mark.integration
def test_rtm_endpoint_requires_ownership(client: TestClient) -> None:
    owner_headers = _register_and_login(client)
    project_id, _requirement_id = _create_project_and_requirement(client, owner_headers)
    intruder_headers = _register_and_login(client)

    response = client.get(f"/api/v1/projects/{project_id}/rtm", headers=intruder_headers)

    assert response.status_code == 404


@pytest.mark.integration
def test_audit_log_records_approval_and_is_organization_scoped(
    client: TestClient, tmp_path: Path
) -> None:
    headers = _register_and_login(client)
    _project_id, requirement_id = _create_project_and_requirement(client, headers)
    _run_worker_directly(requirement_id, tmp_path)
    client.post(f"/api/v1/requirements/{requirement_id}/approve", headers=headers)

    mine = client.get("/api/v1/audit-log", headers=headers).json()
    assert any(
        event["action"] == "traceability_link.locked"
        and event["payload"]["requirement_id"] == requirement_id
        for event in mine
    )

    other_headers = _register_and_login(client)
    theirs = client.get("/api/v1/audit-log", headers=other_headers).json()
    assert not any(event["payload"].get("requirement_id") == requirement_id for event in theirs)
