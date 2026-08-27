import pytest

from testgen.integrations.jira_adapter import JiraAdapter


class _FakeIssue:
    key = "TESTGEN-42"

    def permalink(self) -> str:
        return "https://acme.atlassian.net/browse/TESTGEN-42"


class _FakeJiraClient:
    def __init__(self) -> None:
        self.captured_fields: dict[str, object] | None = None

    def create_issue(self, fields: dict[str, object]) -> _FakeIssue:
        self.captured_fields = fields
        return _FakeIssue()


@pytest.mark.unit
def test_jira_adapter_creates_issue_with_expected_fields() -> None:
    client = _FakeJiraClient()
    adapter = JiraAdapter(client=client, project_key="TESTGEN", issue_type="Task")

    ref = adapter.create_test_case_issue(
        title="Occlusion alarm stops infusion",
        description="Verifies infusion halts within 500ms.",
        priority="critical",
        labels=["safety_critical"],
    )

    assert ref.external_id == "TESTGEN-42"
    assert ref.external_url == "https://acme.atlassian.net/browse/TESTGEN-42"
    assert client.captured_fields is not None
    assert client.captured_fields["project"] == {"key": "TESTGEN"}
    assert client.captured_fields["summary"] == "Occlusion alarm stops infusion"
    assert client.captured_fields["issuetype"] == {"name": "Task"}
    assert client.captured_fields["labels"] == ["safety_critical"]
