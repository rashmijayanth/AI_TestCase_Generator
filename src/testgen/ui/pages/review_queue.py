"""Review Queue: every requirement across a project currently paused at the
human_approval interrupt, in one place.

This exists purely to remove navigation friction (Requirements & Approval
page requires opening each requirement's expander and clicking "Check status"
individually to discover it's waiting). It deliberately does NOT add a
bulk-approve action -- each item here is still approved or rejected one at a
time via render_pending_approval, so a genuine per-item human review still
gates every approval (DESIGN.md §2: this is what makes the audit trail
meaningful). A single "approve all" button would let someone sign off on
every pending test case without reading any of them, which defeats the point
of the interrupt existing at all.
"""

import streamlit as st

from testgen.ui.components import call_api
from testgen.ui.pages.requirements import render_pending_approval
from testgen.ui.session import get_client


def render() -> None:
    st.title("Review Queue")
    st.caption("Every requirement across your projects currently awaiting approval.")

    client = get_client()
    projects = call_api(client.list_projects, error_prefix="Could not load projects")
    if projects is None:
        return
    if not projects:
        st.info("Create a project and upload a document first, on the Projects & Upload page.")
        return

    labels = {p["id"]: p["name"] for p in projects}
    project_id = st.selectbox("Project", options=list(labels), format_func=lambda pid: labels[pid])

    waiting = call_api(
        lambda: client.pending_approvals(project_id), error_prefix="Could not load review queue"
    )
    if waiting is None:
        return
    if not waiting:
        st.success("Nothing waiting on your review in this project right now.")
        return

    st.write(f"**{len(waiting)}** requirement(s) awaiting your review.")
    for item in waiting:
        ref = item["external_ref"] or item["requirement_id"][:8]
        label = f"{ref} — {item['requirement_text'][:80]}"
        with st.expander(label, expanded=True):
            render_pending_approval(client, item["requirement_id"])
