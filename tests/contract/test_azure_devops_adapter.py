"""Contract test: verifies our request matches Azure DevOps's documented Work
Items REST API (api-version=7.1, JSON-Patch document format) and that we
correctly parse a realistic, recorded-shape response. No live tenant is
available (DESIGN.md §8) -- this proves the request/response contract, not
that it works against a real, possibly-drifted-since-documented tenant.
"""

import json

import httpx
import pytest

from testgen.integrations.azure_devops_adapter import AzureDevOpsAdapter

_FIXTURE_RESPONSE = {
    "id": 12345,
    "rev": 1,
    "fields": {"System.Title": "Occlusion alarm stops infusion", "System.State": "New"},
    "url": "https://dev.azure.com/acme/InfusionPump/_apis/wit/workItems/12345",
    "_links": {"html": {"href": "https://dev.azure.com/acme/InfusionPump/_workitems/edit/12345"}},
}


@pytest.mark.contract
def test_create_test_case_issue_sends_expected_patch_document_and_parses_response() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["content_type"] = request.headers.get("content-type")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_FIXTURE_RESPONSE)

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://dev.azure.com")
    adapter = AzureDevOpsAdapter(client, organization="acme", project="InfusionPump")

    ref = adapter.create_test_case_issue(
        title="Occlusion alarm stops infusion",
        description="Verifies infusion halts within 500ms.",
        priority="critical",
        labels=["safety_critical"],
    )

    assert captured["method"] == "POST"
    assert "acme/InfusionPump/_apis/wit/workitems/$Task" in str(captured["url"])
    assert "api-version=7.1" in str(captured["url"])
    assert captured["content_type"] == "application/json-patch+json"
    body = captured["body"]
    assert isinstance(body, list)
    assert {
        "op": "add",
        "path": "/fields/System.Title",
        "value": "Occlusion alarm stops infusion",
    } in body

    assert ref.external_id == "12345"
    assert ref.external_url == "https://dev.azure.com/acme/InfusionPump/_workitems/edit/12345"


@pytest.mark.contract
def test_raises_for_non_2xx_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized"})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://dev.azure.com")
    adapter = AzureDevOpsAdapter(client, organization="acme", project="InfusionPump")

    with pytest.raises(httpx.HTTPStatusError):
        adapter.create_test_case_issue(title="t", description="d", priority="low", labels=[])
