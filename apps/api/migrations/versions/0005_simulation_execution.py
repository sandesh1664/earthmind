"""Durable, bounded M04 execution on existing scenarios/runs; no geographic rewrite."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_simulation_execution"
down_revision = "0004_run_state_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scenarios", sa.Column("configuration_checksum", sa.String(64)))
    for column in (
        sa.Column("idempotency_key", sa.String(128)),
        sa.Column("request_sha256", sa.String(64)),
        sa.Column(
            "input_config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "progress", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("worker_id", sa.String(100)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column(
            "cancel_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("retry_of", sa.Uuid()),
        sa.Column("output_manifest_uri", sa.Text()),
    ):
        op.add_column("simulation_runs", column)
    op.create_unique_constraint(
        "uq_simulation_runs_idempotency_key", "simulation_runs", ["idempotency_key"]
    )
    op.create_foreign_key(
        "fk_simulation_retry",
        "simulation_runs",
        "simulation_runs",
        ["retry_of"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_simulation_runs_status_created", "simulation_runs", ["status", "created_at"]
    )
    op.alter_column("run_metrics", "value", existing_type=sa.Float(), nullable=True)
    op.add_column(
        "run_metrics",
        sa.Column(
            "calculation_version", sa.String(64), nullable=False, server_default="sumo-m04-v1"
        ),
    )
    op.add_column(
        "run_artifacts",
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "run_artifacts",
        sa.Column(
            "content_type",
            sa.String(100),
            nullable=False,
            server_default="application/octet-stream",
        ),
    )
    op.create_table(
        "simulation_events",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("simulation_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("progress_seconds", sa.Float()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "event_type IN ('queued','starting','progress','cancel_requested',"
            "'cancelled','succeeded','failed','retry')",
            name="ck_simulation_event_type",
        ),
    )
    op.create_index(
        "ix_simulation_events_run_created", "simulation_events", ["run_id", "created_at"]
    )
    op.create_table(
        "simulation_comparisons",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "baseline_run_id",
            sa.Uuid(),
            sa.ForeignKey("simulation_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "modified_run_id",
            sa.Uuid(),
            sa.ForeignKey("simulation_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.drop_constraint("ck_run_state_timestamps", "simulation_runs", type_="check")
    op.create_check_constraint(
        "ck_run_state_timestamps",
        "simulation_runs",
        "(status='queued' AND started_at IS NULL AND finished_at IS NULL) OR "
        "(status='running' AND started_at IS NOT NULL AND finished_at IS NULL) OR "
        "(status='succeeded' AND started_at IS NOT NULL AND finished_at IS NOT NULL) OR "
        "(status IN ('failed','cancelled') AND finished_at IS NOT NULL)",
    )
    op.execute("""CREATE OR REPLACE FUNCTION earthmind_m02_run_guard()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='INSERT' THEN
        IF NEW.status<>'queued' OR NEW.started_at IS NOT NULL OR NEW.finished_at IS NOT NULL THEN
          RAISE EXCEPTION 'New simulation contracts must be queued and unexecuted'
            USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END IF;
      IF OLD.status IN ('succeeded','failed','cancelled') THEN
        IF to_jsonb(OLD)<>to_jsonb(NEW) THEN
          RAISE EXCEPTION 'Terminal simulation records are immutable' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END IF;
      IF (OLD.scenario_id,OLD.seed,OLD.input_sha256,OLD.input_config,
          OLD.idempotency_key,OLD.request_sha256,OLD.retry_of,OLD.attempt_number)
          IS DISTINCT FROM (NEW.scenario_id,NEW.seed,NEW.input_sha256,NEW.input_config,
          NEW.idempotency_key,NEW.request_sha256,NEW.retry_of,NEW.attempt_number) THEN
        RAISE EXCEPTION 'Simulation input identity is immutable' USING ERRCODE='23514';
      END IF;
      IF NEW.status<>OLD.status AND NOT ((OLD.status='queued'
        AND NEW.status IN ('running','failed','cancelled')) OR (OLD.status='running'
        AND NEW.status IN ('succeeded','failed','cancelled'))) THEN
        RAISE EXCEPTION 'Invalid simulation state transition' USING ERRCODE='23514';
      END IF;
      IF NEW.status='running' THEN
        NEW.started_at:=coalesce(NEW.started_at,clock_timestamp()); NEW.finished_at:=NULL;
      ELSIF NEW.status IN ('succeeded','failed','cancelled') THEN
        NEW.finished_at:=coalesce(NEW.finished_at,clock_timestamp());
      END IF;
      RETURN NEW;
    END $$""")


def downgrade() -> None:
    # Research output must not silently disappear during an operational rollback.
    bind = op.get_bind()
    populated = bind.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM simulation_events) "
            "OR EXISTS(SELECT 1 FROM simulation_comparisons) "
            "OR EXISTS(SELECT 1 FROM simulation_runs WHERE idempotency_key IS NOT NULL)"
        )
    ).scalar()
    if populated:
        raise RuntimeError("Refusing to downgrade populated M04 simulation research data")
    op.drop_table("simulation_comparisons")
    op.drop_index("ix_simulation_events_run_created", table_name="simulation_events")
    op.drop_table("simulation_events")
    op.drop_column("run_artifacts", "content_type")
    op.drop_column("run_artifacts", "size_bytes")
    op.drop_column("run_metrics", "calculation_version")
    op.alter_column("run_metrics", "value", existing_type=sa.Float(), nullable=False)
    op.drop_index("ix_simulation_runs_status_created", table_name="simulation_runs")
    op.drop_constraint("fk_simulation_retry", "simulation_runs", type_="foreignkey")
    op.drop_constraint("uq_simulation_runs_idempotency_key", "simulation_runs", type_="unique")
    # Restore the frozen M02 trigger's behavior before removing M04-only columns.
    from pathlib import Path

    frozen = Path(__file__).with_name("0003_geospatial_foundation.triggers.sql").read_text()
    definition = next(
        part
        for part in frozen.split("-- statement --")
        if "CREATE FUNCTION earthmind_m02_run_guard" in part
    )
    op.execute(definition.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))
    for name in (
        "output_manifest_uri",
        "retry_of",
        "attempt_number",
        "cancel_requested",
        "heartbeat_at",
        "worker_id",
        "progress",
        "input_config",
        "request_sha256",
        "idempotency_key",
    ):
        op.drop_column("simulation_runs", name)
    op.drop_column("scenarios", "configuration_checksum")
    op.drop_constraint("ck_run_state_timestamps", "simulation_runs", type_="check")
    op.create_check_constraint(
        "ck_run_state_timestamps",
        "simulation_runs",
        "(status='queued' AND started_at IS NULL AND finished_at IS NULL) OR "
        "(status='running' AND started_at IS NOT NULL AND finished_at IS NULL) OR "
        "(status IN ('succeeded','failed') AND started_at IS NOT NULL "
        "AND finished_at IS NOT NULL) OR "
        "(status='cancelled' AND finished_at IS NOT NULL)",
    )
