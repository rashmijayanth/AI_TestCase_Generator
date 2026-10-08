"""Requirements & Approval page: per-requirement generation trigger + status,
and the human-approval review screen itself (DESIGN.md §3's `interrupt()`,
made real -- PROGRESS.md's Phase 8 Next Action calls this out specifically).

There's no "list requirements for a project" endpoint (Phase 7's API surface
doesn't have one), so this page reuses GET .../rtm -- it already returns one
row per requirement with text/safety_class/any-existing-test-cases, which is
exactly what's needed here too.

Status is fetched on demand (a "Check status" button), not auto-polled: this
is a server-rendered-per-rerun app, not a long-lived page with a background
timer, and polling on every rerun would mean an API call per requirement per
click anywhere on the page.
"""

from typing import Any

import streamlit as st

from testgen.ui.api_client import ApiClient
from testgen.ui.components import call_api
from testgen.ui.session import get_client


def _status_key(requirement_id: str) -> str:
    return f"testgen_status_{requirement_id}"


def _message_key(requirement_id: str) -> str:
    return f"testgen_message_{requirement_id}"


def _stash_message(requirement_id: str, kind: str, text: str) -> None:
    # st.rerun() aborts the current run immediately, so an st.success/st.info
    # call right before it is discarded before the browser ever paints it --
    # stash it and render it after the rerun instead (a standard Streamlit
    # pattern for this, confirmed by an AppTest run that showed the message
    # never actually appearing without this).
    st.session_state[_message_key(requirement_id)] = (kind, text)


def _render_existing_test_cases(test_cases: list[dict[str, Any]]) -> None:
    st.dataframe(
        [
            {"Title": tc["title"], "Type": tc["test_type"], "Status": tc["status"]}
            for tc in test_cases
        ],
        hide_index=True,
        width="stretch",
    )


def _render_draft_test_case(test_case: dict[str, Any]) -> None:
    st.markdown(
        f"**{test_case['title']}** &nbsp;·&nbsp; `{test_case['test_type']}` "
        f"&nbsp;·&nbsp; priority: **{test_case['priority']}**"
    )
    st.caption(f"Preconditions: {test_case['preconditions']}")
    st.dataframe(
        [
            {"Step": s["step_no"], "Action": s["action"], "Expected": s["expected"]}
            for s in test_case["steps"]
        ],
        hide_index=True,
        width="stretch",
    )
    st.write(f"Expected result: {test_case['expected_result']}")


def _render_draft_dataset(dataset: dict[str, Any]) -> None:
    redacted = "yes" if dataset["phi_redacted"] else "no"
    st.markdown(
        f"**Test data: {dataset['name']}** "
        f"(for *{dataset['test_case_title']}*, PHI-redacted: {redacted})"
    )
    st.dataframe(dataset["data"], hide_index=True, width="stretch")


def render_pending_approval(client: ApiClient, requirement_id: str) -> None:
    """Renders the drafted test cases/critic feedback for one requirement's
    paused human_approval interrupt, plus its Approve/Reject buttons. Shared
    by this page (called after "Check status" shows awaiting_approval) and by
    the Review Queue page (pages/review_queue.py), which lists every requirement
    across a project already sitting at this interrupt.
    """
    pending = call_api(
        lambda: client.pending_approval(requirement_id),
        error_prefix="Could not load pending review",
    )
    if pending is None:
        return

    st.markdown("#### Pending review")
    if pending["critic_approved"]:
        st.success("Compliance critic approved this draft on its independent re-check.")
    else:
        st.warning("Compliance critic did not fully approve this draft -- review carefully.")
    if pending["critic_feedback"]:
        st.caption(f"Critic feedback: {pending['critic_feedback']}")

    st.markdown("##### Draft test cases")
    for test_case in pending["draft_test_cases"]:
        _render_draft_test_case(test_case)
        st.divider()

    if pending["draft_test_datasets"]:
        st.markdown("##### Draft test data")
        for dataset in pending["draft_test_datasets"]:
            _render_draft_dataset(dataset)
        st.divider()

    approve_col, reject_col = st.columns(2)
    with approve_col:
        if st.button("Approve", key=f"approve_{requirement_id}", type="primary"):
            result = call_api(
                lambda: client.approve(requirement_id), error_prefix="Approval failed"
            )
            if result is not None:
                st.session_state.pop(_status_key(requirement_id), None)
                message = f"Approved -- {result['test_cases_created']} test case(s) created."
                if result["alm_sync"]:
                    message += f" ALM sync: {result['alm_sync']}"
                _stash_message(requirement_id, "success", message)
                st.rerun()
    with reject_col:
        if st.button("Reject", key=f"reject_{requirement_id}"):
            result = call_api(
                lambda: client.reject(requirement_id), error_prefix="Rejection failed"
            )
            if result is not None:
                st.session_state.pop(_status_key(requirement_id), None)
                _stash_message(requirement_id, "info", "Rejected -- no test cases were created.")
                st.rerun()


def _render_requirement(client: ApiClient, row: dict[str, Any]) -> None:
    requirement_id = row["requirement_id"]
    ref = row["external_ref"] or requirement_id[:8]
    label = f"{ref} — {row['requirement_text'][:80]}"

    with st.expander(label):
        message = st.session_state.pop(_message_key(requirement_id), None)
        if message is not None:
            kind, text = message
            getattr(st, kind)(text)

        st.write(f"Safety class: **{row['safety_class'] or 'not yet classified'}**")
        if row["compliance_standards"]:
            st.caption("Compliance standards: " + ", ".join(row["compliance_standards"]))

        if row["test_cases"]:
            st.success(f"{len(row['test_cases'])} test case(s) on record for this requirement.")
            _render_existing_test_cases(row["test_cases"])

        generate_col, status_col = st.columns(2)
        with generate_col:
            if st.button("Generate test cases", key=f"generate_{requirement_id}"):
                result = call_api(
                    lambda: client.trigger_generation(requirement_id),
                    error_prefix="Could not trigger generation",
                )
                if result is not None:
                    st.info("Generation queued -- use 'Check status' once the worker has run.")
        with status_col:
            if st.button("Check status", key=f"check_status_{requirement_id}"):
                status = call_api(
                    lambda: client.generation_status(requirement_id),
                    error_prefix="Could not check status",
                )
                if status is not None:
                    st.session_state[_status_key(requirement_id)] = status["status"]

        status = st.session_state.get(_status_key(requirement_id))
        if status:
            st.write(f"Last known status: `{status}`")
        if status == "awaiting_approval":
            render_pending_approval(client, requirement_id)


def render() -> None:
    st.title("Requirements & Approval")

    client = get_client()
    projects = call_api(client.list_projects, error_prefix="Could not load projects")
    if projects is None:
        return
    if not projects:
        st.info("Create a project and upload a document first, on the Projects & Upload page.")
        return

    labels = {p["id"]: p["name"] for p in projects}
    project_id = st.selectbox("Project", options=list(labels), format_func=lambda pid: labels[pid])

    rows = call_api(lambda: client.rtm(project_id), error_prefix="Could not load requirements")
    if rows is None:
        return
    if not rows:
        st.info("No requirements yet -- upload a document for this project first.")
        return

    if st.button("Generate all ungenerated", key="generate_all_pending"):
        result = call_api(
            lambda: client.generate_all_pending(project_id),
            error_prefix="Could not trigger bulk generation",
        )
        if result is not None:
            queued_count = len(result["queued"])
            skipped_count = len(result["skipped"])
            st.info(
                f"Queued {queued_count} requirement(s) for generation "
                f"({skipped_count} already in progress or done -- skipped)."
            )

    for row in rows:
        _render_requirement(client, row)
