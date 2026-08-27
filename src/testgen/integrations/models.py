"""ALMSyncRecord — sync status of a test case against an external ALM tool."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from testgen.platform.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from testgen.platform.enums import ALMSystem, SyncStatus


class ALMSyncRecord(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "alm_sync_records"

    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_cases.id"))
    alm_system: Mapped[ALMSystem] = mapped_column(SAEnum(ALMSystem, native_enum=False, length=20))
    external_id: Mapped[str] = mapped_column(String(100), default="")
    external_url: Mapped[str] = mapped_column(String(1000), default="")
    sync_status: Mapped[SyncStatus] = mapped_column(
        SAEnum(SyncStatus, native_enum=False, length=20), default=SyncStatus.PENDING
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
