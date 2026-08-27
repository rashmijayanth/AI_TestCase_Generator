"""Thin HTTP client for the FastAPI backend (DESIGN.md §6: the UI "talks to
the FastAPI backend only; no business logic lives in the UI layer"). No
Streamlit imports here on purpose -- this module is plain, framework-free
request/response plumbing, unit-testable with `httpx.MockTransport` the same
way the ADO/Polarion contract tests already do (Decision 36).
"""

from __future__ import annotations

from typing import Any

import httpx

_DEFAULT_TIMEOUT = 30.0


class ApiError(Exception):
    """Raised for any non-2xx response, with the server's own detail message
    surfaced (FastAPI's `{"detail": ...}` body, string or validation-error list).
    """

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


def _extract_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text or f"HTTP {response.status_code}"

    if not isinstance(body, dict):
        return str(body)
    detail = body.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        messages = [str(item.get("msg", item)) for item in detail if isinstance(item, dict)]
        if messages:
            return "; ".join(messages)
    return str(body)


class ApiClient:
    """One instance per logged-in browser session (held in
    `st.session_state` by `testgen.ui.session`), so the bearer token travels
    with it automatically once `login()` succeeds.
    """

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.token = token
        # httpx's client-side keepalive_expiry (5s default) races uvicorn's own
        # keep-alive timeout (also 5s by default) -- confirmed live: a request
        # made just after a multi-second gap reused an already-server-closed
        # connection and failed with RemoteProtocolError before the server ever
        # logged it. retries=1 is httpx's documented mechanism for exactly this
        # -- it only retries the connection-establishment/send phase, which is
        # safe here since the server demonstrably never saw the failed attempt.
        # Callers that pass their own transport (tests, MockTransport) are
        # unaffected.
        self._client = httpx.Client(
            base_url=base_url,
            timeout=_DEFAULT_TIMEOUT,
            transport=transport or httpx.HTTPTransport(retries=1),
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._client.request(method, path, headers=self._headers(), **kwargs)
        if response.status_code >= 400:
            raise ApiError(response.status_code, _extract_detail(response))
        return response.json() if response.content else None

    # --- auth ----------------------------------------------------------

    def register(
        self, *, organization_name: str, email: str, full_name: str, password: str
    ) -> dict[str, Any]:
        result: dict[str, Any] = self._request(
            "POST",
            "/api/v1/auth/register",
            json={
                "organization_name": organization_name,
                "email": email,
                "full_name": full_name,
                "password": password,
            },
        )
        return result

    def login(self, email: str, password: str) -> str:
        """On success, also stores the token on this client so subsequent
        calls are authenticated -- returns it too, for callers that want it.
        """
        result: dict[str, Any] = self._request(
            "POST",
            "/api/v1/auth/token",
            data={"username": email, "password": password},
        )
        token = str(result["access_token"])
        self.token = token
        return token

    # --- projects --------------------------------------------------------

    def list_projects(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self._request("GET", "/api/v1/projects")
        return result

    def create_project(self, name: str, description: str = "") -> dict[str, Any]:
        result: dict[str, Any] = self._request(
            "POST", "/api/v1/projects", json={"name": name, "description": description}
        )
        return result

    # --- documents ---------------------------------------------------------

    def upload_document(
        self, project_id: str, *, filename: str, content: bytes, content_type: str
    ) -> dict[str, Any]:
        result: dict[str, Any] = self._request(
            "POST",
            f"/api/v1/projects/{project_id}/documents",
            files={"file": (filename, content, content_type)},
        )
        return result

    # --- requirement generation lifecycle ------------------------------

    def trigger_generation(self, requirement_id: str) -> dict[str, Any]:
        result: dict[str, Any] = self._request(
            "POST", f"/api/v1/requirements/{requirement_id}/generate"
        )
        return result

    def generation_status(self, requirement_id: str) -> dict[str, Any]:
        result: dict[str, Any] = self._request(
            "GET", f"/api/v1/requirements/{requirement_id}/generation-status"
        )
        return result

    def pending_approval(self, requirement_id: str) -> dict[str, Any]:
        result: dict[str, Any] = self._request(
            "GET", f"/api/v1/requirements/{requirement_id}/pending-approval"
        )
        return result

    def approve(self, requirement_id: str) -> dict[str, Any]:
        result: dict[str, Any] = self._request(
            "POST", f"/api/v1/requirements/{requirement_id}/approve"
        )
        return result

    def reject(self, requirement_id: str) -> dict[str, Any]:
        result: dict[str, Any] = self._request(
            "POST", f"/api/v1/requirements/{requirement_id}/reject"
        )
        return result

    # --- traceability / audit -------------------------------------------

    def rtm(self, project_id: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self._request("GET", f"/api/v1/projects/{project_id}/rtm")
        return result

    def coverage_gaps(self, project_id: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self._request(
            "GET", f"/api/v1/projects/{project_id}/coverage-gaps"
        )
        return result

    def audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self._request(
            "GET", "/api/v1/audit-log", params={"limit": limit}
        )
        return result
