"""Single ORM base and retained M01 application metadata."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, String, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SystemMetadata(Base):
    __tablename__ = "system_metadata"
    __table_args__ = (
        CheckConstraint("length(application_name) > 0", name="ck_system_metadata_name_nonempty"),
        CheckConstraint("schema_version >= 1", name="ck_system_metadata_schema_version"),
        CheckConstraint("updated_at >= created_at", name="ck_system_metadata_timestamp_order"),
        Index("ix_system_metadata_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    application_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    schema_version: Mapped[int] = mapped_column(nullable=False, default=1, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


# Import registrations after Base exists; all milestones share this metadata.
from earthmind_api import geospatial_models as _geospatial_models  # noqa: E402, F401
