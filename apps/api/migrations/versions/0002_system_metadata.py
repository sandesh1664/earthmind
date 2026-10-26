"""M01 system metadata and a single foundation seed."""

import sqlalchemy as sa
from alembic import op

revision = "0002_system_metadata"
down_revision = "0001_postgis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_metadata",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_name", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("application_name", name="uq_system_metadata_application_name"),
        sa.CheckConstraint("length(application_name) > 0", name="ck_system_metadata_name_nonempty"),
        sa.CheckConstraint("schema_version >= 1", name="ck_system_metadata_schema_version"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_system_metadata_timestamp_order"),
    )
    op.create_index("ix_system_metadata_created_at", "system_metadata", ["created_at"])
    op.execute(
        "INSERT INTO system_metadata (id, application_name, schema_version) VALUES "
        "('00000000-0000-4000-8000-000000000001', 'EARTHMIND', 1) "
        "ON CONFLICT (application_name) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_index("ix_system_metadata_created_at", table_name="system_metadata")
    op.drop_table("system_metadata")
