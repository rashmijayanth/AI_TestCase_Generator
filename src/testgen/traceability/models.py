"""TraceabilityLink — requirement <-> test-case links, locked at human approval (DESIGN.md §2)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from testgen.platform.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class TraceabilityLink(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "traceability_links"
    __table_args__ = (
        UniqueConstraint("requirement_id", "test_case_id", name="uq_traceability_link"),
    )

    requirement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("requirements.id"))
    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_cases.id"))
    is_locked: Mapped[bool] = mapped_column(default=False)
    locked_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
