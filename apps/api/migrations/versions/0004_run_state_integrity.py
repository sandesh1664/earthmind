"""Enforce run-state timestamps and align storage with public geometry budgets.

Revision 0003 remains immutable. Existing inconsistent research rows cause this
migration to fail validation rather than silently rewriting their history.
"""

from alembic import op

revision = "0004_run_state_integrity"
down_revision = "0003_geospatial_foundation"
branch_labels = None
depends_on = None

STATE_INVARIANT = (
    "(status='queued' AND started_at IS NULL AND finished_at IS NULL) "
    "OR (status='running' AND started_at IS NOT NULL AND finished_at IS NULL) "
    "OR (status IN ('succeeded','failed') AND started_at IS NOT NULL "
    "AND finished_at IS NOT NULL) "
    "OR (status='cancelled' AND finished_at IS NOT NULL)"
)


def upgrade() -> None:
    op.create_check_constraint("ck_run_state_timestamps", "simulation_runs", STATE_INVARIANT)
    op.create_check_constraint(
        "ck_run_started_after_creation",
        "simulation_runs",
        "started_at IS NULL OR started_at >= created_at",
    )
    op.create_check_constraint(
        "ck_regions_vertex_budget", "regions", "ST_NPoints(boundary) <= 5000"
    )
    op.create_check_constraint("ck_edges_vertex_budget", "road_edges", "ST_NPoints(geom) <= 5000")


def downgrade() -> None:
    # Constraint removal preserves every row; it only relaxes these added guards.
    op.drop_constraint("ck_edges_vertex_budget", "road_edges", type_="check")
    op.drop_constraint("ck_regions_vertex_budget", "regions", type_="check")
    op.drop_constraint("ck_run_started_after_creation", "simulation_runs", type_="check")
    op.drop_constraint("ck_run_state_timestamps", "simulation_runs", type_="check")
