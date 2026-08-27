"""Traceability Matrix page: RTM + coverage gaps (DESIGN.md §10 verification
plan -- "confirm RTM"), per project.
"""

from typing import Any

import streamlit as st

from testgen.ui.components import call_api
from testgen.ui.session import get_client


def _render_rtm(rows: list[dict[str, Any]]) -> None:
    st.subheader("Requirements Traceability Matrix")
    if not rows:
        st.info("No requirements in this project yet.")
        return
    st.dataframe(
        [
            {
                "Requirement": row["external_ref"] or row["requirement_id"][:8],
                "Text": row["requirement_text"],
                "Safety class": row["safety_class"] or "—",
                "Test cases": len(row["test_cases"]),
                "Standards": ", ".join(row["compliance_standards"]) or "—",
            }
            for row in rows
        ],
        hide_index=True,
        width="stretch",
    )


def _render_coverage_gaps(gaps: list[dict[str, Any]]) -> None:
    st.subheader("Coverage gaps")
    if not gaps:
        st.success("No coverage gaps against the minimum floor for this project.")
        return
    st.dataframe(
        [
            {
                "Requirement": gap["external_ref"] or gap["requirement_id"][:8],
                "Safety class": gap["safety_class"] or "—",
                "Missing test types": ", ".join(gap["missing_test_types"]),
            }
            for gap in gaps
        ],
        hide_index=True,
        width="stretch",
    )


def render() -> None:
    st.title("Traceability Matrix")

    client = get_client()
    projects = call_api(client.list_projects, error_prefix="Could not load projects")
    if projects is None:
        return
    if not projects:
        st.info("Create a project first, on the Projects & Upload page.")
        return

    labels = {p["id"]: p["name"] for p in projects}
    project_id = st.selectbox("Project", options=list(labels), format_func=lambda pid: labels[pid])

    rows = call_api(lambda: client.rtm(project_id), error_prefix="Could not load RTM")
    if rows is None:
        return
    _render_rtm(rows)

    st.divider()

    gaps = call_api(
        lambda: client.coverage_gaps(project_id), error_prefix="Could not load coverage gaps"
    )
    if gaps is None:
        return
    _render_coverage_gaps(gaps)
