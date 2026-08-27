"""ComplianceMapping — artifact <-> standard <-> clause <-> rationale."""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from testgen.platform.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from testgen.platform.enums import Standard


class ComplianceMapping(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "compliance_mappings"
    __table_args__ = (
        CheckConstraint(
            "(requirement_id IS NOT NULL) <> (test_case_id IS NOT NULL)",
            name="ck_compliance_mapping_exactly_one_artifact",
        ),
    )

    requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requirements.id"), nullable=True
    )
    test_case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_cases.id"), nullable=True
    )
    standard: Mapped[Standard] = mapped_column(SAEnum(Standard, native_enum=False, length=20))
    clause_ref: Mapped[str] = mapped_column(String(100))
    rationale: Mapped[str] = mapped_column(Text, default="")
