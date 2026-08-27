"""Integration test: real FastAPI TestClient + the real local Postgres
(the db_session fixture, dependency-overridden into the app) for the
register/login flow. Using TestClient as a context manager also triggers the
app's lifespan -- the first real exercise of platform.logging/tracing
(0% covered since Phase 1; they're config wrappers that only make sense once
something real wires them up).
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from testgen.api.app import create_app
from testgen.platform.db.session import get_db
from testgen.platform.security import decode_access_token


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.integration
def test_register_then_login_returns_valid_token(client: TestClient) -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Acme Health",
            "email": "qa@acme.health",
            "full_name": "QA Reviewer",
            "password": "correct horse battery staple",
        },
    )
    assert register_response.status_code == 201
    body = register_response.json()
    assert body["email"] == "qa@acme.health"

    login_response = client.post(
        "/api/v1/auth/token",
        data={"username": "qa@acme.health", "password": "correct horse battery staple"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    assert token

    payload = decode_access_token(token)
    assert payload["sub"] == body["id"]
    assert payload["org"] == body["organization_id"]


@pytest.mark.integration
def test_register_rejects_duplicate_email(client: TestClient) -> None:
    payload = {
        "organization_name": "Acme Health",
        "email": "dup@acme.health",
        "full_name": "QA",
        "password": "correct horse battery staple",
    }
    first = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


@pytest.mark.integration
def test_login_rejects_wrong_password(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Acme Health",
            "email": "wrongpw@acme.health",
            "full_name": "QA",
            "password": "correct horse battery staple",
        },
    )

    response = client.post(
        "/api/v1/auth/token",
        data={"username": "wrongpw@acme.health", "password": "not-the-password"},
    )

    assert response.status_code == 401


@pytest.mark.integration
def test_login_rejects_unknown_email(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/token", data={"username": "nobody@acme.health", "password": "whatever"}
    )

    assert response.status_code == 401


@pytest.mark.integration
def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
