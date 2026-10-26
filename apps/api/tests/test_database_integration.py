"""Explicit integration tests; run after migrations against the local Compose DB."""

import os
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from earthmind_api.dependencies import Infrastructure
from earthmind_api.models import SystemMetadata
from earthmind_api.settings import Settings
from sqlalchemy import select, text

pytestmark = pytest.mark.integration


async def test_metadata_seed_schema_and_transaction_rollback() -> None:
    url = os.environ.get("EARTHMIND_TEST_DATABASE_URL")
    if not url:
        pytest.skip("EARTHMIND_TEST_DATABASE_URL must select the live migrated database")
    infrastructure = Infrastructure(Settings(database_url=url))
    try:
        async with infrastructure.session() as session:
            seeded = (
                await session.scalars(
                    select(SystemMetadata).where(SystemMetadata.application_name == "EARTHMIND")
                )
            ).one()
            assert isinstance(seeded.id, UUID)
            assert seeded.schema_version == 1
            assert seeded.created_at.utcoffset() == timedelta(0)
            assert seeded.updated_at >= seeded.created_at
            indexes = (
                (
                    await session.execute(
                        text("SELECT indexname FROM pg_indexes WHERE tablename='system_metadata'")
                    )
                )
                .scalars()
                .all()
            )
            assert "ix_system_metadata_created_at" in indexes
        key = f"rollback-{uuid4()}"
        with pytest.raises(RuntimeError, match="rollback probe"):
            async with infrastructure.session() as session:
                session.add(SystemMetadata(application_name=key, schema_version=1))
                await session.flush()
                raise RuntimeError("rollback probe")
        async with infrastructure.session() as session:
            assert (
                await session.scalars(
                    select(SystemMetadata).where(SystemMetadata.application_name == key)
                )
            ).first() is None
        key = f"commit-{uuid4()}"
        async with infrastructure.session() as session:
            session.add(SystemMetadata(application_name=key, schema_version=1))
        async with infrastructure.session() as session:
            committed = (
                await session.scalars(
                    select(SystemMetadata).where(SystemMetadata.application_name == key)
                )
            ).one()
            await session.delete(committed)
    finally:
        await infrastructure.close()
