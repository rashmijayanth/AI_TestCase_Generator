"""Streamlit entrypoint (DESIGN.md §6: "the primary human interface... talks
to the FastAPI backend only; no business logic lives in the UI layer").

Run with `streamlit run src/testgen/ui/app.py` (or scripts/run_ui.ps1),
against a running API (`uvicorn testgen.api.app:app`) -- API_BASE_URL points
at it, defaulting to http://localhost:8000.

register()/approve()/reject() etc. all require ADMIN_ROLE_NAME server-side;
register() auto-grants "admin" to an org's first user (api/deps.py), so the
logged-in user here always passes that gate already -- no separate
role-picker needed (PROGRESS.md's Phase 8 Next Action).
"""

import streamlit as st

from testgen.ui.api_client import ApiError
from testgen.ui.components import LOGOUT_MESSAGE_KEY
from testgen.ui.pages import audit, projects, requirements, review_queue, rtm, usage
from testgen.ui.session import (
    current_user_email,
    is_authenticated,
    log_out,
    new_client,
    set_authenticated,
)


def _render_login() -> None:
    st.title("Automatic Test Case Generation AI")
    st.caption("Healthcare requirements → compliant, traceable test cases")

    logout_message = st.session_state.pop(LOGOUT_MESSAGE_KEY, None)
    if logout_message is not None:
        st.info(logout_message)

    login_tab, register_tab = st.tabs(["Log in", "Register"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            client = new_client()
            try:
                client.login(email, password)
            except ApiError as exc:
                st.error(f"Login failed: {exc.detail}")
            else:
                set_authenticated(client, email)
                st.rerun()

    with register_tab:
        st.caption("Registering creates a new organization with you as its admin.")
        with st.form("register_form"):
            org_name = st.text_input("Organization name")
            full_name = st.text_input("Full name")
            reg_email = st.text_input("Email", key="register_email")
            reg_password = st.text_input("Password", type="password", key="register_password")
            reg_submitted = st.form_submit_button("Register")
        if reg_submitted:
            client = new_client()
            try:
                client.register(
                    organization_name=org_name,
                    email=reg_email,
                    full_name=full_name,
                    password=reg_password,
                )
                client.login(reg_email, reg_password)
            except ApiError as exc:
                st.error(f"Registration failed: {exc.detail}")
            else:
                set_authenticated(client, reg_email)
                st.rerun()


def main() -> None:
    st.set_page_config(page_title="AI Test Case Generator", page_icon="🧪", layout="wide")

    if not is_authenticated():
        _render_login()
        return

    with st.sidebar:
        st.write(f"Signed in as **{current_user_email()}**")
        if st.button("Log out"):
            log_out()
            st.rerun()

    nav = st.navigation(
        [
            st.Page(projects.render, title="Projects & Upload", icon="📁", url_path="projects"),
            st.Page(
                requirements.render,
                title="Requirements & Approval",
                icon="✅",
                url_path="requirements",
                default=True,
            ),
            st.Page(
                review_queue.render, title="Review Queue", icon="📋", url_path="review-queue"
            ),
            st.Page(rtm.render, title="Traceability Matrix", icon="🔗", url_path="rtm"),
            st.Page(usage.render, title="LLM Usage & Cost", icon="💰", url_path="usage"),
            st.Page(audit.render, title="Audit Log", icon="📜", url_path="audit"),
        ]
    )
    nav.run()


main()
