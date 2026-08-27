"""Live Jira adapter (DESIGN.md §7/§8) -- a real Jira Cloud tenant is expected,
though no credentials are configured in this environment (same situation as
GEMINI_API_KEY in Phases 3/4: built for real, not live-tested here -- smoke-test
once real JIRA_* values are added to .env).

jira.JIRA's constructor contacts the server by default (get_server_info=True) to
validate the connection -- confirmed by introspecting the installed jira 3.10.5's
actual __init__ signature. That means the underlying client can't be constructed
at all without live credentials/network, so JiraAdapter takes an
already-constructed client (JiraClientPort -- just the one method this adapter
uses) rather than constructing jira.JIRA itself: dependency injection at the
adapter level, not by faking jira.JIRA's own constructor.
"""

from typing import TYPE_CHECKING, Protocol

from testgen.integrations.port import ALMIssueRef
from testgen.platform.config import Settings, get_settings

if TYPE_CHECKING:
    from jira import JIRA


class _JiraIssueLike(Protocol):
    key: str

    def permalink(self) -> str: ...


class JiraClientPort(Protocol):
    """The one method of jira.JIRA's interface this adapter actually uses."""

    def create_issue(self, fields: dict[str, object]) -> _JiraIssueLike: ...


class JiraAdapter:
    def __init__(
        self, client: JiraClientPort, *, project_key: str, issue_type: str = "Task"
    ) -> None:
        self._client = client
        self._project_key = project_key
        self._issue_type = issue_type

    def create_test_case_issue(
        self, *, title: str, description: str, priority: str, labels: list[str]
    ) -> ALMIssueRef:
        issue = self._client.create_issue(
            fields={
                "project": {"key": self._project_key},
                "summary": title,
                "description": description,
                "issuetype": {"name": self._issue_type},
                "labels": labels,
            }
        )
        return ALMIssueRef(external_id=issue.key, external_url=issue.permalink())


def build_jira_client(settings: Settings | None = None) -> "JIRA":
    from jira import JIRA

    settings = settings or get_settings()
    return JIRA(
        server=settings.jira_base_url,
        basic_auth=(settings.jira_email, settings.jira_api_token),
    )


def get_jira_adapter(settings: Settings | None = None) -> JiraAdapter:
    settings = settings or get_settings()
    return JiraAdapter(
        client=build_jira_client(settings),
        project_key=settings.jira_project_key,
        issue_type=settings.jira_issue_type,
    )
