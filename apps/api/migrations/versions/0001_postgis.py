"""M01 infrastructure baseline: require PostGIS without creating domain tables."""

from alembic import op

revision = "0001_postgis"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    # Keep the shared extension and any spatial data when rolling back application metadata.
    pass
