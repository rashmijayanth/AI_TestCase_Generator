"""LangGraph state schema for the test-generation pipeline. One graph run == one Requirement.

Every field uses default replace-on-update semantics (no Annotated reducers needed):
each node either owns a field outright (nothing else writes it) or computes the full
new value itself (e.g. retry_count), so there's never a need to merge two nodes'
partial writes to the same key.
"""

from typing import Any, TypedDict


class GenerationState(TypedDict):
    requirement_id: str
    requirement_text: str

    safety_class: str | None
    analysis_rationale: str

    retrieved_clauses: list[dict[str, Any]]

    planned_test_types: list[str]
    strategist_rationale: str

    draft_test_cases: list[dict[str, Any]]
    draft_test_datasets: list[dict[str, Any]]

    critic_approved: bool
    critic_feedback: str

    coverage_gaps: list[str]

    retry_count: int
    max_retries: int

    human_approved: bool | None
    human_approver_id: str | None


def new_generation_state(
    requirement_id: str, requirement_text: str, max_retries: int = 3
) -> GenerationState:
    return GenerationState(
        requirement_id=requirement_id,
        requirement_text=requirement_text,
        safety_class=None,
        analysis_rationale="",
        retrieved_clauses=[],
        planned_test_types=[],
        strategist_rationale="",
        draft_test_cases=[],
        draft_test_datasets=[],
        critic_approved=False,
        critic_feedback="",
        coverage_gaps=[],
        retry_count=0,
        max_retries=max_retries,
        human_approved=None,
        human_approver_id=None,
    )
