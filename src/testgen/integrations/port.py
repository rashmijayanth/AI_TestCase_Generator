"""ALMPort: the interface all three adapters (Jira, Azure DevOps, Polarion) implement."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ALMIssueRef:
    external_id: str
    external_url: str


class ALMPort(Protocol):
    def create_test_case_issue(
        self, *, title: str, description: str, priority: str, labels: list[str]
    ) -> ALMIssueRef: ...
