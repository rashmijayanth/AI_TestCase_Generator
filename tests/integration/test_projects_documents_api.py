"""Integration test: project creation/listing and document upload -> ingestion,
via the real FastAPI TestClient + real Postgres.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from testgen.api.app import create_app
from testgen.platform.db.session import get_db


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client


def _register_and_login(client: TestClient, email: str = "qa@acme.health") -> dict[str, str]:
    # organizations.name is globally unique (Phase 1 schema) -- derive a
    # distinct org name per email so tests registering multiple orgs don't
    # collide on that constraint.
    client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": f"Acme Health ({email})",
            "email": email,
            "full_name": "QA Reviewer",
            "password": "correct horse battery staple",
        },
    )
    token = client.post(
        "/api/v1/auth/token", data={"username": email, "password": "correct horse battery staple"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
def test_create_and_list_projects_scoped_to_organization(client: TestClient) -> None:
    headers = _register_and_login(client, "org1@acme.health")
    other_headers = _register_and_login(client, "org2@acme.health")

    create_response = client.post(
        "/api/v1/projects",
        json={"name": "Infusion Pump Firmware", "description": "Class C device"},
        headers=headers,
    )
    assert create_response.status_code == 201

    mine = client.get("/api/v1/projects", headers=headers).json()
    theirs = client.get("/api/v1/projects", headers=other_headers).json()

    assert len(mine) == 1
    assert mine[0]["name"] == "Infusion Pump Firmware"
    assert theirs == []


@pytest.mark.integration
def test_projects_endpoint_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/projects")

    assert response.status_code == 401


@pytest.mark.integration
def test_upload_document_ingests_requirements(client: TestClient) -> None:
    headers = _register_and_login(client)
    project_id = client.post(
        "/api/v1/projects", json={"name": "Infusion Pump Firmware"}, headers=headers
    ).json()["id"]

    content = (
        b"# Infusion Pump SRS\n\n"
        b"REQ-001: The system shall stop infusion within 500ms of an occlusion alarm.\n\n"
        b"REQ-002: The system shall log every alarm event with a timestamp.\n"
    )
    response = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("srs.md", content, "text/markdown")},
        headers=headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["requirements_extracted"] == 2
    assert body["version"] == 1


@pytest.mark.integration
def test_upload_document_rejects_unsupported_extension(client: TestClient) -> None:
    headers = _register_and_login(client)
    project_id = client.post(
        "/api/v1/projects", json={"name": "Infusion Pump Firmware"}, headers=headers
    ).json()["id"]

    response = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("srs.txt", b"whatever", "text/plain")},
        headers=headers,
    )

    assert response.status_code == 400


@pytest.mark.integration
def test_upload_document_to_unowned_project_returns_404(client: TestClient) -> None:
    owner_headers = _register_and_login(client, "owner@acme.health")
    intruder_headers = _register_and_login(client, "intruder@acme.health")
    project_id = client.post(
        "/api/v1/projects", json={"name": "Infusion Pump Firmware"}, headers=owner_headers
    ).json()["id"]

    response = client.post(
        f"/api/v1/projects/{project_id}/documents",
        files={"file": ("srs.md", b"REQ-1: The system shall alarm.", "text/markdown")},
        headers=intruder_headers,
    )

    assert response.status_code == 404
