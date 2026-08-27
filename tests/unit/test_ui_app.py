"""AppTest-based check for the Streamlit entrypoint (testgen.ui.app).

Deliberately does NOT `import testgen.ui.app` anywhere in this file: app.py
calls main() at module scope (the standard Streamlit entrypoint pattern), so
a plain `import` executes it once outside any script-run context ("bare
mode") -- confirmed directly to corrupt a later real AppTest run of the same
file (`st.form` raised "Forms cannot be nested in other forms" on the second,
real execution). AppTest.from_file sidesteps this entirely: it execs the
script's source fresh, without going through Python's import system, so it
never touches a module object this file could accidentally pre-run.

The unauthenticated (login/register) render and the logout-on-expired-token
path (which needs app.py's real login gate to catch the post-rerun state)
are checked here. Authenticated, per-page behavior that doesn't depend on
app.py's shell is covered in test_ui_pages.py via AppTest.from_function
against each page's render() directly (with session_state pre-seeded),
which sidesteps app.py entirely.
"""

from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from testgen.ui.api_client import ApiClient

_APP_PATH = str(Path(__file__).resolve().parents[2] / "src" / "testgen" / "ui" / "app.py")


@pytest.mark.unit
def test_login_page_renders_with_no_exception() -> None:
    at = AppTest.from_file(_APP_PATH)
    at.run()

    assert not at.exception
    assert [t.value for t in at.title] == ["Automatic Test Case Generation AI"]
    assert [tab.label for tab in at.tabs] == ["Log in", "Register"]
    assert {inp.label for inp in at.text_input} == {
        "Email",
        "Password",
        "Organization name",
        "Full name",
    }


@pytest.mark.unit
def test_expired_token_bounces_back_to_login_with_message() -> None:
    # A pre-authenticated session whose token the server no longer accepts
    # (expired/revoked). The default page (Requirements & Approval) calls
    # list_projects() as its first API call, so a 401 there is enough to
    # exercise components.call_api's logout+rerun path -- and this run goes
    # through app.py's real main(), so the rerun's is_authenticated() check
    # actually redirects to the login form, unlike a bare page harness.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Could not validate credentials"})

    client = ApiClient(
        base_url="http://testserver", token="tok", transport=httpx.MockTransport(handler)
    )

    at = AppTest.from_file(_APP_PATH)
    at.session_state["testgen_api_client"] = client
    at.session_state["testgen_user_email"] = "qa@acme.health"
    at.run()

    assert not at.exception
    assert [t.value for t in at.title] == ["Automatic Test Case Generation AI"]
    assert any("session has expired" in i.value for i in at.info)
    assert "testgen_api_client" not in at.session_state
