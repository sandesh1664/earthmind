"""Additive M04 audit/comparison records on the existing ORM base."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from earthmind_api.models import Base


class SimulationEvent(Base):
    __tablename__ = "simulation_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('queued','starting','progress','cancel_requested',"
            "'cancelled','succeeded','failed','retry')",
            name="ck_simulation_event_type",
        ),
        Index("ix_simulation_events_run_created", "run_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=sa_text("gen_random_uuid()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    progress_seconds: Mapped[float | None] = mapped_column(Float)


class SimulationComparison(Base):
    __tablename__ = "simulation_comparisons"
    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=sa_text("gen_random_uuid()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    baseline_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    modified_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
