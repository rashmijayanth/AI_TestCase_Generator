"""Persists an approved (or rejected) generation run's results to the database:
TestCase/TestDataset rows, TraceabilityLink creation + locking, and an audit
log entry. Deferred out of the graph itself in Phase 4 (Decision 28) since a
live DB session and the approving user's identity don't belong in LangGraph
state; this is the orchestration layer that closes that loop, called once the
graph has resumed past the human_approval interrupt.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from testgen.generation.models import TestCase, TestDataset
from testgen.generation.state import GenerationState
from testgen.ingestion.models import Requirement
from testgen.platform.audit import record_event
from testgen.platform.enums import (
    RequirementStatus,
    SafetyClass,
    TestCaseStatus,
    TestPriority,
    TestType,
)
from testgen.traceability.service import (
    create_traceability_link,
    lock_traceability_links_for_requirement,
)

PROMPT_VERSION = "v1"


def persist_generation_result(
    session: Session,
    *,
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    organization_id: uuid.UUID,
    final_state: GenerationState,
    model_name: str,
) -> list[TestCase]:
    """Rejected: records one audit entry, persists nothing else (drafts were
    never real rows). Approved: creates real TestCase/TestDataset rows from the
    graph's drafts, links + locks each to the requirement (one audit entry per
    link, via lock_traceability_links_for_requirement), and returns the created
    TestCase rows (e.g. for the caller to trigger ALM sync on).

    Writes the Requirement Analyst's classification back onto the Requirement
    row itself either way (approved or rejected) -- the graph only ever held
    it in state (Decision 28: no DB session in LangGraph state), and
    classification is meaningful even if the drafted test cases get rejected.
    """
    approver_id_str = final_state["human_approver_id"]
    approver_id = uuid.UUID(approver_id_str) if approver_id_str else None

    safety_class = SafetyClass(final_state["safety_class"]) if final_state["safety_class"] else None
    if safety_class is not None:
        requirement = session.get(Requirement, requirement_id)
        if requirement is not None:
            requirement.safety_class = safety_class
            requirement.status = RequirementStatus.CLASSIFIED

    if not final_state["human_approved"]:
        record_event(
            session,
            action="requirement.generation_rejected",
            entity_type="requirement",
            entity_id=requirement_id,
            payload={"critic_feedback": final_state["critic_feedback"]},
            organization_id=organization_id,
            actor_user_id=approver_id,
        )
        session.commit()
        return []

    if approver_id is None:
        raise ValueError("An approved generation result must have a human_approver_id")

    datasets_by_test_case_title: dict[str, list[dict[str, Any]]] = {}
    for dataset in final_state["draft_test_datasets"]:
        datasets_by_test_case_title.setdefault(dataset["test_case_title"], []).append(dataset)

    created_test_cases: list[TestCase] = []
    for draft in final_state["draft_test_cases"]:
        test_case = TestCase(
            project_id=project_id,
            title=draft["title"],
            test_type=TestType(draft["test_type"]),
            preconditions=draft.get("preconditions", ""),
            steps=draft.get("steps", []),
            expected_result=draft.get("expected_result", ""),
            priority=TestPriority(draft["priority"]),
            safety_class=safety_class,
            status=TestCaseStatus.APPROVED,
            generated_by_model=model_name,
            prompt_version=PROMPT_VERSION,
            approver_id=approver_id,
        )
        session.add(test_case)
        session.flush()
        created_test_cases.append(test_case)

        for dataset in datasets_by_test_case_title.get(draft["title"], []):
            session.add(
                TestDataset(
                    test_case_id=test_case.id,
                    name=dataset["name"],
                    data=dataset["data"],
                    phi_redacted=dataset["phi_redacted"],
                )
            )

        create_traceability_link(session, requirement_id=requirement_id, test_case_id=test_case.id)

    session.flush()
    lock_traceability_links_for_requirement(
        session,
        requirement_id=requirement_id,
        approver_id=approver_id,
        organization_id=organization_id,
    )
    session.commit()
    return created_test_cases
