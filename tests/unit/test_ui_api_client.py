"""Unit tests for the UI's HTTP client (testgen.ui.api_client). Mocked
transport, same `httpx.MockTransport` pattern as the ADO/Polarion contract
tests (Decision 36) -- proves request shape (method/path/body/auth header)
and response handling without a real FastAPI process.
"""

import json
from collections.abc import Callable

import httpx
import pytest

from testgen.ui.api_client import ApiClient, ApiError

Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler, token: str | None = None) -> ApiClient:
    return ApiClient(
        base_url="http://testserver",
        token=token,
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.unit
def test_register_posts_expected_body_and_parses_response() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["json"] = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                "id": "u1",
                "email": "qa@acme.health",
                "full_name": "QA",
                "organization_id": "o1",
            },
        )

    client = _client(handler)
    result = client.register(
        organization_name="Acme", email="qa@acme.health", full_name="QA", password="secret123"
    )

    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v1/auth/register"
    assert captured["json"] == {
        "organization_name": "Acme",
        "email": "qa@acme.health",
        "full_name": "QA",
        "password": "secret123",
    }
    assert result["email"] == "qa@acme.health"


@pytest.mark.unit
def test_login_sends_form_data_and_stores_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/auth/token"
        assert request.headers["content-type"] == "application/x-www-form-urlencoded"
        return httpx.Response(200, json={"access_token": "tok-123", "token_type": "bearer"})

    client = _client(handler)
    token = client.login("qa@acme.health", "secret123")

    assert token == "tok-123"
    assert client.token == "tok-123"


@pytest.mark.unit
def test_authenticated_requests_carry_bearer_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer tok-123"
        return httpx.Response(200, json=[])

    client = _client(handler, token="tok-123")
    client.list_projects()


@pytest.mark.unit
def test_unauthenticated_requests_omit_auth_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        return httpx.Response(200, json=[])

    client = _client(handler)
    client.list_projects()


@pytest.mark.unit
def test_error_response_with_string_detail_raises_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "Email already registered"})

    client = _client(handler)
    with pytest.raises(ApiError) as exc_info:
        client.register(
            organization_name="Acme", email="dup@acme.health", full_name="QA", password="x"
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Email already registered"


@pytest.mark.unit
def test_error_response_with_validation_list_detail_joins_messages() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "detail": [
                    {"loc": ["body", "email"], "msg": "field required"},
                    {"loc": ["body", "password"], "msg": "too short"},
                ]
            },
        )

    client = _client(handler)
    with pytest.raises(ApiError) as exc_info:
        client.list_projects()

    assert exc_info.value.status_code == 422
    assert "field required" in exc_info.value.detail
    assert "too short" in exc_info.value.detail


@pytest.mark.unit
def test_error_response_with_non_json_body_falls_back_to_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal server error")

    client = _client(handler)
    with pytest.raises(ApiError) as exc_info:
        client.list_projects()

    assert exc_info.value.status_code == 500
    assert "internal server error" in exc_info.value.detail


@pytest.mark.unit
def test_create_project_posts_name_and_description() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {"name": "Infusion Pump", "description": "desc"}
        return httpx.Response(
            201, json={"id": "p1", "name": "Infusion Pump", "description": "desc"}
        )

    client = _client(handler)
    result = client.create_project("Infusion Pump", "desc")

    assert result["id"] == "p1"


@pytest.mark.unit
def test_upload_document_sends_multipart_file() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/projects/proj-1/documents"
        assert request.headers["content-type"].startswith("multipart/form-data")
        assert b"REQ-001" in request.content
        return httpx.Response(
            201,
            json={
                "document_id": "doc-1",
                "filename": "srs.md",
                "version": 1,
                "requirements_extracted": 1,
                "requirement_ids": ["req-1"],
            },
        )

    client = _client(handler)
    result = client.upload_document(
        "proj-1", filename="srs.md", content=b"REQ-001: shall do X.", content_type="text/markdown"
    )

    assert result["requirement_ids"] == ["req-1"]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("method_name", "expected_path", "expected_method"),
    [
        ("trigger_generation", "/api/v1/requirements/req-1/generate", "POST"),
        ("generation_status", "/api/v1/requirements/req-1/generation-status", "GET"),
        ("pending_approval", "/api/v1/requirements/req-1/pending-approval", "GET"),
        ("approve", "/api/v1/requirements/req-1/approve", "POST"),
        ("reject", "/api/v1/requirements/req-1/reject", "POST"),
    ],
)
def test_requirement_lifecycle_methods_hit_expected_endpoint(
    method_name: str, expected_path: str, expected_method: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == expected_path
        assert request.method == expected_method
        return httpx.Response(200, json={"status": "ok"})

    client = _client(handler)
    getattr(client, method_name)("req-1")


@pytest.mark.unit
def test_rtm_and_coverage_gaps_hit_project_scoped_paths() -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        return httpx.Response(200, json=[])

    client = _client(handler)
    client.rtm("proj-1")
    client.coverage_gaps("proj-1")

    assert seen_paths == [
        "/api/v1/projects/proj-1/rtm",
        "/api/v1/projects/proj-1/coverage-gaps",
    ]


@pytest.mark.unit
def test_audit_log_passes_limit_as_query_param() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/audit-log"
        assert request.url.params["limit"] == "50"
        return httpx.Response(200, json=[])

    client = _client(handler)
    client.audit_log(limit=50)
