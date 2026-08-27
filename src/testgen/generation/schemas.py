"""Structured LLM output contracts for each agent (DESIGN.md §3).

Enum-like fields are plain `str` here, not the real enum types (testgen.platform.enums)
-- Gemini's response_schema is a constrained JSON schema, and its compatibility with
Pydantic's generated schema for Enum/Literal fields is unverified (no live API access
in this environment; see docs/PROGRESS.md). Callers coerce these strings into the real
enums themselves and get a clear, catchable error if the model returns something
unexpected, rather than that ambiguity being buried inside JSON-schema translation.
"""

from typing import Any

from pydantic import BaseModel, Field


class RequirementAnalysisOutput(BaseModel):
    safety_class: str
    rationale: str


class SufficiencyCheckOutput(BaseModel):
    sufficient: bool
    refined_query: str = ""


class TestPlanOutput(BaseModel):
    test_types: list[str]
    rationale: str


class TestCaseStepOutput(BaseModel):
    step_no: int
    action: str
    expected: str


class TestCaseDraftOutput(BaseModel):
    title: str
    test_type: str
    preconditions: str
    steps: list[TestCaseStepOutput]
    expected_result: str
    priority: str


class TestCaseGeneratorOutput(BaseModel):
    test_cases: list[TestCaseDraftOutput]


class TestDatasetDraftOutput(BaseModel):
    name: str
    rows: list[dict[str, Any]]


class ComplianceCritiqueOutput(BaseModel):
    approved: bool
    feedback: str
    cited_clause_refs: list[str] = Field(default_factory=list)
