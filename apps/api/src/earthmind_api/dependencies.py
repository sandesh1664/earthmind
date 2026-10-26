"""Lifespan-scoped infrastructure clients and bounded readiness probes."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Protocol, cast

from earthmind_contracts import WORKER_HEARTBEAT_KEY, CheckStatus, DependencyChecks, ReadyHealth
from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from earthmind_api.settings import Settings

logger = logging.getLogger(__name__)


class HealthChecks(Protocol):
    async def database(self) -> None: ...

    async def redis(self) -> None: ...

    async def worker(self) -> None: ...


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    infrastructure = cast(Infrastructure, request.app.state.infrastructure)
    async with infrastructure.session() as session:
        yield session


class Infrastructure:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._engine: AsyncEngine | None = None
        self.cache: Redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.health_timeout_seconds,
            socket_timeout=settings.health_timeout_seconds,
        )

    async def open(self) -> None:
        # Engine creation and connections are lazy, keeping liveness independent.
        return None

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = create_async_engine(
                self.settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1),
                pool_size=5,
                max_overflow=0,
                pool_timeout=self.settings.health_timeout_seconds,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 2, "options": "-c statement_timeout=2000"},
            )
        return self._engine

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except BaseException:
                await session.rollback()
                raise

    async def close(self) -> None:
        try:
            await self.cache.aclose()
        finally:
            if self._engine is not None:
                await self._engine.dispose()

    async def database(self) -> None:
        async with self.engine.connect() as connection:
            cursor = await connection.execute(text("SELECT 1, PostGIS_Version()"))
            row = cursor.fetchone()
            if row is None or row[0] != 1 or not row[1]:
                raise RuntimeError("Database or PostGIS probe failed")

    async def redis(self) -> None:
        if not await self.cache.ping():
            raise RuntimeError("Redis ping failed")

    async def worker(self) -> None:
        if await self.cache.ttl(WORKER_HEARTBEAT_KEY) <= 0:
            raise RuntimeError("Worker heartbeat is absent or expired")


async def readiness(checks: HealthChecks, budget_seconds: float) -> ReadyHealth:
    async def probe(name: str, check: Callable[[], Awaitable[None]]) -> CheckStatus:
        try:
            async with asyncio.timeout(budget_seconds):
                await check()
            return "ok"
        except Exception:
            logger.warning("Readiness dependency failed: %s", name, exc_info=True)
            return "error"

    database, redis, worker = await asyncio.gather(
        probe("database", checks.database),
        probe("redis", checks.redis),
        probe("worker", checks.worker),
    )
    dependencies = DependencyChecks(database=database, redis=redis, worker=worker)
    return ReadyHealth(
        status="ok" if all(value == "ok" for value in (database, redis, worker)) else "degraded",
        checks=dependencies,
    )
