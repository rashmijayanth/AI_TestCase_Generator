"""LLM Usage & Cost page: per-agent token/cost/latency totals for a project
(generation.orchestration.project_llm_usage_summary), closing the gap where
llm_generation_runs existed in the schema since Phase 1 but was never
populated or surfaced anywhere.
"""

from typing import Any

import streamlit as st

from testgen.ui.components import call_api
from testgen.ui.session import get_client


def _render_usage(rows: list[dict[str, Any]]) -> None:
    st.subheader("LLM usage by agent")
    if not rows:
        st.info(
            "No LLM usage recorded yet for this project -- run a generation "
            "job first, on the Requirements & Approval page."
        )
        return

    total_calls = sum(row["call_count"] for row in rows)
    total_input = sum(row["total_input_tokens"] for row in rows)
    total_output = sum(row["total_output_tokens"] for row in rows)
    total_cost = sum(row["total_cost_usd"] for row in rows)

    cols = st.columns(4)
    cols[0].metric("LLM calls", total_calls)
    cols[1].metric("Input tokens", f"{total_input:,}")
    cols[2].metric("Output tokens", f"{total_output:,}")
    cols[3].metric("Est. cost (USD)", f"${total_cost:,.4f}")

    table = [
        {
            "Agent": row["agent_name"],
            "Calls": row["call_count"],
            "Input tokens": row["total_input_tokens"],
            "Output tokens": row["total_output_tokens"],
            "Cost (USD)": row["total_cost_usd"],
            "Avg latency (ms)": round(row["avg_latency_ms"]),
        }
        for row in rows
    ]
    st.dataframe(table, hide_index=True, width="stretch")

    st.caption(
        "Cost is 0 until real per-model Gemini pricing is configured "
        "(generation.orchestration.persist_llm_usage) -- token counts are "
        "real, from Gemini's own usage_metadata."
    )
    st.bar_chart(
        {row["Agent"]: row["Input tokens"] + row["Output tokens"] for row in table},
    )


def render() -> None:
    st.title("LLM Usage & Cost")

    client = get_client()
    projects = call_api(client.list_projects, error_prefix="Could not load projects")
    if projects is None:
        return
    if not projects:
        st.info("Create a project first, on the Projects & Upload page.")
        return

    labels = {p["id"]: p["name"] for p in projects}
    project_id = st.selectbox("Project", options=list(labels), format_func=lambda pid: labels[pid])

    rows = call_api(lambda: client.llm_usage(project_id), error_prefix="Could not load LLM usage")
    if rows is None:
        return
    _render_usage(rows)
