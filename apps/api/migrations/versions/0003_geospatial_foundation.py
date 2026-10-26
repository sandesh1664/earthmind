"""M02 spatial persistence and database-backed research integrity.

The SQL below is a frozen revision snapshot, not mutable current ORM metadata.
Downgrade refuses populated M02 tables; it never silently destroys research data.
"""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0003_geospatial_foundation"
down_revision = "0002_system_metadata"
branch_labels = None
depends_on = None

DDL = tuple(Path(__file__).with_suffix(".sql").read_text().split("\n-- statement --\n"))


def upgrade() -> None:
    for statement in DDL:
        op.execute(statement)
    for statement in TRIGGERS:
        op.execute(statement)


def downgrade() -> None:
    bind = op.get_bind()
    tables = (
        "run_metrics",
        "run_artifacts",
        "simulation_runs",
        "scenario_interventions",
        "scenarios",
        "road_edges",
        "intersections",
        "demand_profiles",
        "network_versions",
        "audit_events",
        "users",
        "regions",
        "data_sources",
    )
    for table in tables:
        if bind.scalar(sa.text(f'SELECT EXISTS (SELECT 1 FROM "{table}" LIMIT 1)')):
            raise RuntimeError(
                "M02 downgrade refused: populated research tables require "
                "an explicit data-preserving export/migration plan"
            )
    for table in tables:
        op.execute(f'DROP TABLE "{table}"')
    op.execute("DROP FUNCTION earthmind_m02_network_guard()")
    op.execute("DROP FUNCTION earthmind_m02_child_guard()")
    op.execute("DROP FUNCTION earthmind_m02_run_guard()")
    op.execute("DROP FUNCTION earthmind_m02_region_guard()")


TRIGGERS = tuple(
    Path(__file__)
    .with_name("0003_geospatial_foundation.triggers.sql")
    .read_text()
    .split("\n-- statement --\n")
)
