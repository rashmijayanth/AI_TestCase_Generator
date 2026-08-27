"""Shared rendering helper used by every page. Kept to the one thing that's
genuinely common (turning an ApiError into an st.error, and bouncing back to
the login screen on an expired/invalid token) -- page-specific rendering
(test case cards, tables) stays in the page that needs it.
"""

from collections.abc import Callable
from typing import TypeVar

import streamlit as st

from testgen.ui.api_client import ApiError
from testgen.ui.session import log_out

T = TypeVar("T")

# st.rerun() aborts the current run immediately, so an st.error() call right
# before it would never actually reach the browser -- stash it in session
# state and have the (now logged-out) login page show it after the rerun.
# app.py's login render pops this key.
LOGOUT_MESSAGE_KEY = "testgen_logout_message"


def call_api(action: Callable[[], T], *, error_prefix: str) -> T | None:
    """Runs an API call, returning its result -- or None if it failed, after
    rendering an st.error (callers should `if result is None: return`).
    A 401 means the token expired or was revoked server-side; that forces a
    logout + rerun back to the login screen rather than showing a generic
    error the user can't act on.
    """
    try:
        return action()
    except ApiError as exc:
        if exc.status_code == 401:
            log_out()
            st.session_state[LOGOUT_MESSAGE_KEY] = "Your session has expired. Please log in again."
            st.rerun()
        st.error(f"{error_prefix}: {exc.detail}")
        return None
