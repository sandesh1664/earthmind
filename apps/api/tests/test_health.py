import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import httpx
import pytest
from earthmind_api.dependencies import Infrastructure, readiness
from earthmind_api.main import create_app, get_checks
from earthmind_api.settings import Settings


class FakeChecks:
    def __init__(self, failed: str | None = None, delay: float = 0) -> None:
        self.failed = failed
        self.delay = delay

    async def probe(self, name: str) -> None:
        await asyncio.sleep(self.delay)
        if name == self.failed:
            raise ConnectionError("Internal connection detail that must not be exposed")

    async def database(self) -> None:
        await self.probe("database")

    async def redis(self) -> None:
        await self.probe("redis")

    async def worker(self) -> None:
        await self.probe("worker")


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(Settings())
    app.dependency_overrides[get_checks] = lambda: FakeChecks()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def test_liveness_does_not_require_dependencies(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}
    assert response.headers["cache-control"] == "no-store"


async def test_ready_when_all_dependencies_pass(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "api",
        "checks": {"database": "ok", "redis": "ok", "worker": "ok"},
    }
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("failed", ["database", "redis", "worker"])
async def test_degraded_is_503_without_internal_details(failed: str) -> None:
    app = create_app(Settings())
    app.dependency_overrides[get_checks] = lambda: FakeChecks(failed=failed)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        response = await c.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"][failed] == "error"
    assert "Internal connection" not in response.text


async def test_timeout_is_bounded_and_degraded() -> None:
    async with asyncio.timeout(0.5):
        result = await readiness(FakeChecks(delay=10), budget_seconds=0.01)
    assert result.status == "degraded"
    assert result.checks.model_dump() == {"database": "error", "redis": "error", "worker": "error"}


async def test_cors_allowed_origin(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/live", headers={"Origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


async def test_cors_untrusted_origin(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/live", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in response.headers


async def test_shutdown_closes_database_even_if_redis_close_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = AsyncMock()
    cache.aclose.side_effect = ConnectionError("Redis unavailable during shutdown")
    engine = AsyncMock()
    monkeypatch.setattr("earthmind_api.dependencies.Redis.from_url", lambda *args, **kwargs: cache)
    infrastructure = Infrastructure(Settings())
    infrastructure._engine = engine

    with pytest.raises(ConnectionError, match="Redis unavailable during shutdown"):
        await infrastructure.close()

    cache.aclose.assert_awaited_once()
    engine.dispose.assert_awaited_once()
