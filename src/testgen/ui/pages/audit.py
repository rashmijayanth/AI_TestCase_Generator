"""Audit Log page (DESIGN.md §10 verification plan -- "confirm... audit
log"). Org-scoped server-side already (api/routers/audit.py); this page is
just a table over it, newest first.
"""

import streamlit as st

from testgen.ui.components import call_api
from testgen.ui.session import get_client


def render() -> None:
    st.title("Audit Log")

    client = get_client()
    limit = st.number_input("Rows to show", min_value=10, max_value=1000, value=100, step=10)
    events = call_api(
        lambda: client.audit_log(limit=int(limit)), error_prefix="Could not load audit log"
    )
    if events is None:
        return

    if not events:
        st.info("No audit events recorded yet for this organization.")
        return

    st.dataframe(
        [
            {
                "ID": event["id"],
                "When": event["created_at"],
                "Action": event["action"],
                "Entity type": event["entity_type"],
                "Entity ID": event["entity_id"],
                "Payload": event["payload"],
            }
            for event in events
        ],
        hide_index=True,
        width="stretch",
    )
