"""Streamlit `st.session_state` glue: holds the one authenticated `ApiClient`
for the browser session plus the email the user logged in with (login only
returns a bearer token -- there's no `/me` endpoint -- so the email typed
into the login form is the only user-identifying string the UI ever has).
Kept separate from api_client.py so that module stays importable and
unit-testable with zero Streamlit dependency.
"""

from typing import cast

import streamlit as st

from testgen.platform.config import get_settings
from testgen.ui.api_client import ApiClient

_CLIENT_KEY = "testgen_api_client"
_EMAIL_KEY = "testgen_user_email"


def is_authenticated() -> bool:
    return _CLIENT_KEY in st.session_state


def get_client() -> ApiClient:
    client = st.session_state.get(_CLIENT_KEY)
    if client is None:
        raise RuntimeError("get_client() called before authentication")
    return cast(ApiClient, client)


def current_user_email() -> str:
    return str(st.session_state.get(_EMAIL_KEY, ""))


def set_authenticated(client: ApiClient, email: str) -> None:
    st.session_state[_CLIENT_KEY] = client
    st.session_state[_EMAIL_KEY] = email


def log_out() -> None:
    st.session_state.pop(_CLIENT_KEY, None)
    st.session_state.pop(_EMAIL_KEY, None)


def new_client() -> ApiClient:
    return ApiClient(base_url=get_settings().api_base_url)
