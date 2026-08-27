"""Projects & Upload page: create a project, upload a requirements document
to it (ingestion runs synchronously -- DESIGN.md §6/api/routers/documents.py
-- so extracted requirements are visible immediately after upload).
"""

from typing import Any

import streamlit as st

from testgen.ui.components import call_api
from testgen.ui.session import get_client

_MESSAGE_KEY = "testgen_projects_message"


def _create_project_form() -> None:
    st.subheader("New project")
    with st.form("create_project_form", clear_on_submit=True):
        name = st.text_input("Project name")
        description = st.text_area("Description", value="")
        submitted = st.form_submit_button("Create project")

    if not submitted:
        return
    if not name:
        st.error("Project name is required.")
        return

    client = get_client()
    result = call_api(
        lambda: client.create_project(name, description), error_prefix="Could not create project"
    )
    if result is not None:
        # st.rerun() aborts this run immediately, so an st.success() call right
        # before it would never actually reach the browser -- stash it and show
        # it after the rerun instead (confirmed missing via an AppTest run).
        st.session_state[_MESSAGE_KEY] = f"Created project '{result['name']}'."
        st.rerun()


def _upload_form(projects: list[dict[str, Any]]) -> None:
    st.subheader("Upload a requirements document")
    if not projects:
        st.info("Create a project above before uploading a document.")
        return

    labels = {p["id"]: p["name"] for p in projects}
    project_id = st.selectbox(
        "Project", options=list(labels), format_func=lambda pid: labels[pid], key="upload_project"
    )
    uploaded = st.file_uploader("Requirements document (PDF, DOCX, ReqIF, XML, or Markdown)")
    submitted = st.button("Upload", disabled=uploaded is None)

    if not submitted or uploaded is None:
        return

    client = get_client()
    result = call_api(
        lambda: client.upload_document(
            project_id,
            filename=uploaded.name,
            content=uploaded.getvalue(),
            content_type=uploaded.type or "application/octet-stream",
        ),
        error_prefix="Upload failed",
    )
    if result is None:
        return

    st.success(
        f"Extracted {result['requirements_extracted']} requirement(s) from "
        f"'{result['filename']}' (v{result['version']})."
    )
    st.caption("Requirement IDs (used on the Requirements & Approval page):")
    st.code("\n".join(result["requirement_ids"]) or "(none)")


def render() -> None:
    st.title("Projects & Upload")

    message = st.session_state.pop(_MESSAGE_KEY, None)
    if message is not None:
        st.success(message)

    client = get_client()
    projects = call_api(client.list_projects, error_prefix="Could not load projects")
    if projects is None:
        return

    _create_project_form()
    st.divider()

    st.subheader("Existing projects")
    if projects:
        st.dataframe(
            [{"ID": p["id"], "Name": p["name"], "Description": p["description"]} for p in projects],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No projects yet -- create one above.")

    st.divider()
    _upload_form(projects)
