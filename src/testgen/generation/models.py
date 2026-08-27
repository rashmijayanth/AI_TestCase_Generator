"""TestCase, TestDataset, LLMGenerationRun — generation's owned entities."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from testgen.platform.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from testgen.platform.enums import SafetyClass, TestCaseStatus, TestPriority, TestType


class TestCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "test_cases"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(String(500))
    test_type: Mapped[TestType] = mapped_column(SAEnum(TestType, native_enum=False, length=30))
    preconditions: Mapped[str] = mapped_column(Text, default="")
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    expected_result: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[TestPriority] = mapped_column(
        SAEnum(TestPriority, native_enum=False, length=20)
    )
    safety_class: Mapped[SafetyClass | None] = mapped_column(
        SAEnum(SafetyClass, native_enum=False, length=1), nullable=True
    )
    status: Mapped[TestCaseStatus] = mapped_column(
        SAEnum(TestCaseStatus, native_enum=False, length=20), default=TestCaseStatus.DRAFT
    )
    generated_by_model: Mapped[str] = mapped_column(String(100), default="")
    prompt_version: Mapped[str] = mapped_column(String(50), default="")
    approver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    datasets: Mapped[list["TestDataset"]] = relationship(back_populates="test_case")


class TestDataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "test_datasets"

    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_cases.id"))
    name: Mapped[str] = mapped_column(String(255))
    data: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    phi_redacted: Mapped[bool] = mapped_column(default=False)
    generated_by_model: Mapped[str] = mapped_column(String(100), default="")

    test_case: Mapped[TestCase] = relationship(back_populates="datasets")


class LLMGenerationRun(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One row per agent LLM call: cost/latency/eval tracking (DESIGN.md §5)."""

    __tablename__ = "llm_generation_runs"

    agent_name: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    eval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requirements.id"), nullable=True
    )
    test_case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_cases.id"), nullable=True
    )
