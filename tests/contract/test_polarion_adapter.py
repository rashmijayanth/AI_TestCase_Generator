"""Contract test: verifies our request matches Polarion's documented JSON:API-
style REST endpoint for creating work items, and that we correctly parse a
realistic, recorded-shape response. No live tenant is available (DESIGN.md §8)
-- this proves the request/response contract, not that it works against a
real, possibly-drifted-since-documented tenant.
"""

import json

import httpx
import pytest

from testgen.integrations.polarion_adapter import PolarionAdapter

_FIXTURE_RESPONSE = {
    "data": [
        {
            "type": "workitems",
            "id": "InfusionPump/WI-42",
            "links": {"self": "https://polarion.acme.internal/polarion/rest/v1/.../WI-42"},
        }
    ]
}


@pytest.mark.contract
def test_create_test_case_issue_sends_expected_jsonapi_body_and_parses_response() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_FIXTURE_RESPONSE)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://polarion.acme.internal/polarion/rest/v1",
    )
    adapter = PolarionAdapter(client, project_id="InfusionPump")

    ref = adapter.create_test_case_issue(
        title="Occlusion alarm stops infusion",
        description="Verifies infusion halts within 500ms.",
        priority="critical",
        labels=["safety_critical"],
    )

    assert captured["method"] == "POST"
    assert "/projects/InfusionPump/workitems" in str(captured["url"])
    body = captured["body"]
    assert isinstance(body, dict)
    [item] = body["data"]
    assert item["type"] == "workitems"
    assert item["attributes"]["title"] == "Occlusion alarm stops infusion"
    assert item["attributes"]["type"] == "task"

    assert ref.external_id == "InfusionPump/WI-42"
    assert ref.external_url == "https://polarion.acme.internal/polarion/rest/v1/.../WI-42"


@pytest.mark.contract
def test_raises_for_non_2xx_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"errors": [{"title": "Forbidden"}]})

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://polarion.acme.internal/polarion/rest/v1",
    )
    adapter = PolarionAdapter(client, project_id="InfusionPump")

    with pytest.raises(httpx.HTTPStatusError):
        adapter.create_test_case_issue(title="t", description="d", priority="low", labels=[])
