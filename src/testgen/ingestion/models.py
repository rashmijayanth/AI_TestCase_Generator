"""SourceDocument and Requirement — ingestion's owned entities."""

import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from testgen.platform.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from testgen.platform.enums import DocumentFormat, RequirementStatus, SafetyClass


class SourceDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_documents"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    filename: Mapped[str] = mapped_column(String(500))
    file_format: Mapped[DocumentFormat] = mapped_column(
        SAEnum(DocumentFormat, native_enum=False, length=20)
    )
    checksum: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(1000))
    version: Mapped[int] = mapped_column(Integer, default=1)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    requirements: Mapped[list["Requirement"]] = relationship(back_populates="source_document")


class Requirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "requirements"

    source_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_documents.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    external_ref: Mapped[str] = mapped_column(String(100), default="")
    text: Mapped[str] = mapped_column(Text)
    source_span_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_span_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    safety_class: Mapped[SafetyClass | None] = mapped_column(
        SAEnum(SafetyClass, native_enum=False, length=1), nullable=True
    )
    status: Mapped[RequirementStatus] = mapped_column(
        SAEnum(RequirementStatus, native_enum=False, length=20), default=RequirementStatus.EXTRACTED
    )

    source_document: Mapped[SourceDocument] = relationship(back_populates="requirements")
