"""Azure DevOps Work Items REST API adapter (DESIGN.md §6/§8).

No live Azure DevOps tenant is available (DESIGN.md §8) -- this is one of the
two adapters (with Polarion) where "not live-tested" is the PERMANENT, intended
state, not a temporary gap waiting on a credential like Gemini/Jira. Built to
the documented Work Items REST API (api-version=7.1, the JSON-Patch document
format it requires) and contract-tested against a recorded, realistic response
(tests/integration/test_azure_devops_adapter.py): that proves the request shape
matches the documented contract and the response parses correctly, not that it
works against a real, possibly-drifted-since-documented tenant.
"""

import httpx

from testgen.integrations.port import ALMIssueRef


class AzureDevOpsAdapter:
    def __init__(
        self,
        client: httpx.Client,
        *,
        organization: str,
        project: str,
        work_item_type: str = "Task",
    ) -> None:
        self._client = client
        self._organization = organization
        self._project = project
        self._work_item_type = work_item_type

    def create_test_case_issue(
        self, *, title: str, description: str, priority: str, labels: list[str]
    ) -> ALMIssueRef:
        patch_document = [
            {"op": "add", "path": "/fields/System.Title", "value": title},
            {"op": "add", "path": "/fields/System.Description", "value": description},
            {"op": "add", "path": "/fields/System.Tags", "value": "; ".join(labels)},
        ]
        response = self._client.post(
            f"/{self._organization}/{self._project}/_apis/wit/workitems/${self._work_item_type}",
            params={"api-version": "7.1"},
            json=patch_document,
            headers={"Content-Type": "application/json-patch+json"},
        )
        response.raise_for_status()
        data = response.json()
        return ALMIssueRef(external_id=str(data["id"]), external_url=data["_links"]["html"]["href"])
