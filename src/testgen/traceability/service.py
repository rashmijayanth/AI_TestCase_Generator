"""Requirement <-> test-case traceability: continuous linking + locking at human
approval (DESIGN.md §2), plus coverage analysis and RTM generation (DESIGN.md §10).
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from testgen.compliance.models import ComplianceMapping
from testgen.generation.models import TestCase
from testgen.ingestion.models import Requirement
from testgen.platform.audit import record_event
from testgen.platform.enums import SafetyClass, TestType
from testgen.traceability.models import TraceabilityLink


def create_traceability_link(
    session: Session, *, requirement_id: uuid.UUID, test_case_id: uuid.UUID
) -> TraceabilityLink:
    """Created as soon as a test case is drafted -- unlocked until human approval."""
    link = TraceabilityLink(
        requirement_id=requirement_id, test_case_id=test_case_id, is_locked=False
    )
    session.add(link)
    session.flush()
    return link


def lock_traceability_links_for_requirement(
    session: Session,
    *,
    requirement_id: uuid.UUID,
    approver_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> list[TraceabilityLink]:
    """The Human Approval step (DESIGN.md §2): locks every unlocked link for this
    requirement and records one audit log entry per link locked.
    """
    links = (
        session.execute(
            select(TraceabilityLink).where(
                TraceabilityLink.requirement_id == requirement_id, ~TraceabilityLink.is_locked
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for link in links:
        link.is_locked = True
        link.locked_by = approver_id
        link.locked_at = now
        record_event(
            session,
            action="traceability_link.locked",
            entity_type="traceability_link",
            entity_id=link.id,
            payload={"requirement_id": str(requirement_id), "test_case_id": str(link.test_case_id)},
            organization_id=organization_id,
            actor_user_id=approver_id,
        )
    session.flush()
    return list(links)


# Minimum coverage floor -- not a replacement for the Test Strategist agent's
# per-requirement judgment (DESIGN.md §3, generation/agents.py), which reasons
# over the requirement's actual content (numeric thresholds, timing language,
# etc.) via an LLM call. This is a deterministic, DB-queryable "did we get at
# least this much" check, usable without re-invoking the LLM.
_MINIMUM_TYPES_BY_SAFETY_CLASS: dict[SafetyClass, set[TestType]] = {
    SafetyClass.A: {TestType.FUNCTIONAL},
    SafetyClass.B: {TestType.FUNCTIONAL, TestType.SAFETY_CRITICAL},
    SafetyClass.C: {TestType.FUNCTIONAL, TestType.SAFETY_CRITICAL},
}


@dataclass(frozen=True)
class CoverageGap:
    requirement_id: uuid.UUID
    external_ref: str
    safety_class: str | None
    missing_test_types: list[str] = field(default_factory=list)


def find_coverage_gaps(session: Session, *, project_id: uuid.UUID) -> list[CoverageGap]:
    requirements = (
        session.execute(select(Requirement).where(Requirement.project_id == project_id))
        .scalars()
        .all()
    )
    gaps: list[CoverageGap] = []
    for requirement in requirements:
        linked_test_case_ids = (
            session.execute(
                select(TraceabilityLink.test_case_id).where(
                    TraceabilityLink.requirement_id == requirement.id
                )
            )
            .scalars()
            .all()
        )
        safety_class_value = requirement.safety_class.value if requirement.safety_class else None

        if not linked_test_case_ids:
            gaps.append(
                CoverageGap(
                    requirement_id=requirement.id,
                    external_ref=requirement.external_ref,
                    safety_class=safety_class_value,
                    missing_test_types=["(no test cases linked)"],
                )
            )
            continue

        covered_types = set(
            session.execute(select(TestCase.test_type).where(TestCase.id.in_(linked_test_case_ids)))
            .scalars()
            .all()
        )
        required = (
            _MINIMUM_TYPES_BY_SAFETY_CLASS.get(requirement.safety_class, set())
            if requirement.safety_class
            else set()
        )
        missing = sorted(t.value for t in required - covered_types)
        if missing:
            gaps.append(
                CoverageGap(
                    requirement_id=requirement.id,
                    external_ref=requirement.external_ref,
                    safety_class=safety_class_value,
                    missing_test_types=missing,
                )
            )
    return gaps


@dataclass(frozen=True)
class RTMRow:
    requirement_id: uuid.UUID
    external_ref: str
    requirement_text: str
    safety_class: str | None
    test_cases: list[dict[str, Any]]
    compliance_standards: list[str]


def generate_rtm(session: Session, *, project_id: uuid.UUID) -> list[RTMRow]:
    """Requirements Traceability Matrix (DESIGN.md §10): one row per requirement,
    with its linked test cases and the compliance standards mapped to it.
    """
    requirements = (
        session.execute(select(Requirement).where(Requirement.project_id == project_id))
        .scalars()
        .all()
    )
    rows: list[RTMRow] = []
    for requirement in requirements:
        links = (
            session.execute(
                select(TraceabilityLink).where(TraceabilityLink.requirement_id == requirement.id)
            )
            .scalars()
            .all()
        )
        test_case_ids = [link.test_case_id for link in links]
        test_cases = (
            session.execute(select(TestCase).where(TestCase.id.in_(test_case_ids))).scalars().all()
            if test_case_ids
            else []
        )
        mappings = (
            session.execute(
                select(ComplianceMapping).where(ComplianceMapping.requirement_id == requirement.id)
            )
            .scalars()
            .all()
        )
        rows.append(
            RTMRow(
                requirement_id=requirement.id,
                external_ref=requirement.external_ref,
                requirement_text=requirement.text,
                safety_class=requirement.safety_class.value if requirement.safety_class else None,
                test_cases=[
                    {
                        "id": str(tc.id),
                        "title": tc.title,
                        "test_type": tc.test_type.value,
                        "status": tc.status.value,
                    }
                    for tc in test_cases
                ],
                compliance_standards=sorted({m.standard.value for m in mappings}),
            )
        )
    return rows
