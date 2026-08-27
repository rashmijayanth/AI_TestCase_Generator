"""AppTest-based checks for individual page render() functions, run via
AppTest.from_function against each page directly -- session_state is
pre-seeded with an already-authenticated ApiClient (mocked transport), so
these never touch app.py's login/nav shell at all (see test_ui_app.py for
why that matters).

These exist because the api_client.py unit tests only prove the HTTP layer
is correct in isolation -- they can't catch a page mis-reading a response
shape (wrong dict key, etc.) or a Streamlit interaction bug. Both classes of
bug were found writing these: the approve/reject/create-project handlers
called st.success()/st.info() immediately before st.rerun(), which discards
the message before the browser ever paints it (st.rerun() aborts the run
immediately) -- fixed by stashing the message in session_state and rendering
it after the rerun. These tests assert the message actually appears, so a
regression would fail loudly again.
"""

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from testgen.ui.api_client import ApiClient

Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler) -> ApiClient:
    return ApiClient(
        base_url="http://testserver", token="tok", transport=httpx.MockTransport(handler)
    )


def _page_harness(page_name: str) -> None:
    # AppTest.from_function re-execs this function's *source text* in a fresh
    # namespace (confirmed via inspect.getsourcelines in its implementation) --
    # so it can't close over an outer `render` callable, only receive plain
    # data through kwargs. Hence picking the page by name here, with its own
    # self-contained import, rather than _run() taking a render callable.
    from testgen.ui.pages import audit, projects, requirements, rtm

    pages = {
        "projects": projects.render,
        "requirements": requirements.render,
        "rtm": rtm.render,
        "audit": audit.render,
    }
    pages[page_name]()


def _run(page_name: str, client: ApiClient) -> AppTest:
    at = AppTest.from_function(_page_harness, kwargs={"page_name": page_name})
    at.session_state["testgen_api_client"] = client
    at.session_state["testgen_user_email"] = "qa@acme.health"
    at.run()
    return at


_PENDING_PAYLOAD: dict[str, Any] = {
    "requirement_text": "Shall stop infusion within 500ms of an occlusion alarm.",
    "safety_class": "C",
    "critic_approved": True,
    "critic_feedback": "",
    "draft_test_cases": [
        {
            "title": "Occlusion alarm stops infusion",
            "test_type": "safety_critical",
            "preconditions": "Pump running",
            "steps": [
                {"step_no": 1, "action": "Trigger occlusion", "expected": "Halts within 500ms"}
            ],
            "expected_result": "Halts",
            "priority": "critical",
        }
    ],
    "draft_test_datasets": [
        {
            "name": "Flow rates",
            "data": [{"rate_ml_per_hr": 50}, {"rate_ml_per_hr": 100}],
            "phi_redacted": True,
            "test_case_title": "Occlusion alarm stops infusion",
        }
    ],
}

_RTM_ROW: dict[str, Any] = {
    "requirement_id": "r1",
    "external_ref": "REQ-001",
    "requirement_text": "Shall stop infusion within 500ms of an occlusion alarm.",
    "safety_class": "C",
    "test_cases": [],
    "compliance_standards": ["IEC_62304"],
}


# --- Projects & Upload ------------------------------------------------------


@pytest.mark.unit
def test_create_project_shows_success_message_after_rerun() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/projects" and request.method == "GET":
            return httpx.Response(200, json=[])
        if request.url.path == "/api/v1/projects" and request.method == "POST":
            return httpx.Response(
                201, json={"id": "p1", "name": "Infusion Pump", "description": ""}
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    at = _run("projects", _client(handler))
    assert not at.exception

    name_input = next(t for t in at.text_input if t.label == "Project name")
    name_input.set_value("Infusion Pump")
    submit = next(b for b in at.button if b.label == "Create project")
    submit.click().run()

    assert not at.exception
    assert [s.value for s in at.success] == ["Created project 'Infusion Pump'."]


# --- Requirements & Approval -------------------------------------------------


@pytest.mark.unit
def test_requirements_page_with_no_projects_shows_guidance() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    at = _run("requirements", _client(handler))

    assert not at.exception
    assert any("Create a project" in i.value for i in at.info)


@pytest.mark.unit
def test_check_status_then_approve_shows_drafts_and_success_message() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        path = request.url.path
        if path == "/api/v1/projects":
            return httpx.Response(
                200, json=[{"id": "p1", "name": "Infusion Pump", "description": ""}]
            )
        if path == "/api/v1/projects/p1/rtm":
            return httpx.Response(200, json=[_RTM_ROW])
        if path == "/api/v1/requirements/r1/generation-status":
            return httpx.Response(200, json={"status": "awaiting_approval"})
        if path == "/api/v1/requirements/r1/pending-approval":
            return httpx.Response(200, json=_PENDING_PAYLOAD)
        if path == "/api/v1/requirements/r1/approve":
            return httpx.Response(
                200,
                json={
                    "requirement_id": "r1",
                    "status": "approved",
                    "test_cases_created": 1,
                    "alm_sync": [],
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {path}")

    at = _run("requirements", _client(handler))
    assert not at.exception

    check_status = next(b for b in at.button if b.label == "Check status")
    check_status.click().run()
    assert not at.exception

    markdown_text = " ".join(m.value for m in at.markdown)
    assert "Pending review" in markdown_text
    assert "Occlusion alarm stops infusion" in markdown_text
    assert "Flow rates" in markdown_text

    approve = next(b for b in at.button if b.label == "Approve")
    approve.click().run()

    assert not at.exception
    assert [s.value for s in at.success] == ["Approved -- 1 test case(s) created."]
    assert calls[-3:] == [
        "POST /api/v1/requirements/r1/approve",
        "GET /api/v1/projects",
        "GET /api/v1/projects/p1/rtm",
    ]


@pytest.mark.unit
def test_check_status_then_reject_shows_info_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/projects":
            return httpx.Response(
                200, json=[{"id": "p1", "name": "Infusion Pump", "description": ""}]
            )
        if path == "/api/v1/projects/p1/rtm":
            return httpx.Response(200, json=[_RTM_ROW])
        if path == "/api/v1/requirements/r1/generation-status":
            return httpx.Response(200, json={"status": "awaiting_approval"})
        if path == "/api/v1/requirements/r1/pending-approval":
            return httpx.Response(200, json=_PENDING_PAYLOAD)
        if path == "/api/v1/requirements/r1/reject":
            return httpx.Response(
                200,
                json={
                    "requirement_id": "r1",
                    "status": "rejected",
                    "test_cases_created": 0,
                    "alm_sync": [],
                },
            )
        raise AssertionError(f"unexpected request: {request.method} {path}")

    at = _run("requirements", _client(handler))
    next(b for b in at.button if b.label == "Check status").click().run()

    reject = next(b for b in at.button if b.label == "Reject")
    reject.click().run()

    assert not at.exception
    assert [i.value for i in at.info] == ["Rejected -- no test cases were created."]


# --- Traceability Matrix -----------------------------------------------------


@pytest.mark.unit
def test_rtm_page_renders_rows_and_no_gaps() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/projects":
            return httpx.Response(
                200, json=[{"id": "p1", "name": "Infusion Pump", "description": ""}]
            )
        if path == "/api/v1/projects/p1/rtm":
            return httpx.Response(200, json=[_RTM_ROW])
        if path == "/api/v1/projects/p1/coverage-gaps":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected request: {request.method} {path}")

    at = _run("rtm", _client(handler))

    assert not at.exception
    assert any("No coverage gaps" in s.value for s in at.success)


@pytest.mark.unit
def test_rtm_page_renders_coverage_gaps() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/projects":
            return httpx.Response(
                200, json=[{"id": "p1", "name": "Infusion Pump", "description": ""}]
            )
        if path == "/api/v1/projects/p1/rtm":
            return httpx.Response(200, json=[_RTM_ROW])
        if path == "/api/v1/projects/p1/coverage-gaps":
            return httpx.Response(
                200,
                json=[
                    {
                        "requirement_id": "r1",
                        "external_ref": "REQ-001",
                        "safety_class": "C",
                        "missing_test_types": ["safety_critical"],
                    }
                ],
            )
        raise AssertionError(f"unexpected request: {request.method} {path}")

    at = _run("rtm", _client(handler))

    assert not at.exception
    assert not any("No coverage gaps" in s.value for s in at.success)


# --- Audit Log ----------------------------------------------------------------


@pytest.mark.unit
def test_audit_log_page_renders_events() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/audit-log"
        return httpx.Response(
            200,
            json=[
                {
                    "id": 1,
                    "action": "requirement.generation_approved",
                    "entity_type": "requirement",
                    "entity_id": "r1",
                    "payload": {},
                    "created_at": "2026-08-27T10:00:00+00:00",
                }
            ],
        )

    at = _run("audit", _client(handler))

    assert not at.exception
    assert not list(at.info)  # the "no events" branch should not have rendered
