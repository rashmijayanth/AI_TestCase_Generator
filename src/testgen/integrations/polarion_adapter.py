"""Polarion ALM REST API adapter (DESIGN.md §6/§8).

Targets Polarion's modern JSON:API-style REST interface (not the legacy SOAP
API). Same situation as Azure DevOps: no live Polarion tenant is available
(DESIGN.md §8), so this is contract-tested against a recorded fixture
(tests/integration/test_polarion_adapter.py), not live-verified, and that's the
permanent, intended state for this adapter.
"""

import httpx

from testgen.integrations.port import ALMIssueRef


class PolarionAdapter:
    def __init__(
        self, client: httpx.Client, *, project_id: str, work_item_type: str = "task"
    ) -> None:
        self._client = client
        self._project_id = project_id
        self._work_item_type = work_item_type

    def create_test_case_issue(
        self, *, title: str, description: str, priority: str, labels: list[str]
    ) -> ALMIssueRef:
        body = {
            "data": [
                {
                    "type": "workitems",
                    "attributes": {
                        "title": title,
                        "type": self._work_item_type,
                        "description": {"type": "text/html", "value": description},
                    },
                }
            ]
        }
        response = self._client.post(f"/projects/{self._project_id}/workitems", json=body)
        response.raise_for_status()
        item = response.json()["data"][0]
        return ALMIssueRef(external_id=item["id"], external_url=item["links"]["self"])
