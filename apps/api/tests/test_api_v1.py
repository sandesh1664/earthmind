import json
import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from earthmind_api.diagnostics import DiagnosticsStore, QueueFullError
from earthmind_api.logging import JsonFormatter
from earthmind_api.main import create_app, get_checks, get_store
from earthmind_api.settings import Settings
from earthmind_contracts import DiagnosticJob, SumoRuntimeRecord
from pydantic import ValidationError
from test_health import FakeChecks


def test_settings_reject_invalid_urls_and_wildcard_cors() -> None:
    for values in (
        {"database_url": "sqlite:///local.db"},
        {"redis_url": "http://redis"},
        {"redis_url": "redis://localhost:99999"},
        {"database_url": "postgresql://localhost:invalid/earthmind"},
        {"cors_origins": ["*"]},
        {"cors_origins": ["https://site.example/path"]},
    ):
        with pytest.raises(ValidationError):
            Settings(**values)
    assert "earthmind_dev" not in Settings().database_url
    with pytest.raises(ValidationError) as invalid:
        Settings(database_url="postgresql://user:private-password@")
    assert "private-password" not in str(invalid.value)


async def test_v1_health_is_exact_and_dependency_independent() -> None:
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"service": "EARTHMIND API", "status": "healthy", "version": "0.1.0"}


async def test_capabilities_never_assume_sumo_is_available() -> None:
    app = create_app()
    store = AsyncMock()
    store.runtime.return_value = None
    app.dependency_overrides[get_checks] = lambda: FakeChecks()
    app.dependency_overrides[get_store] = lambda: store
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/system/capabilities")
    assert response.status_code == 200
    flags = response.json()["capabilities"]
    assert flags["api"] and flags["database"] and flags["redis"] and flags["worker"]
    assert flags["simulation_runtime"] is False
    assert (
        flags["dubai_network_import"]
        is flags["traffic_simulation"]
        is flags["ai_forecasting"]
        is False
    )
    assert response.json()["runtime"] is None


async def test_capabilities_require_a_verified_runtime_record() -> None:
    app = create_app()
    store = AsyncMock()
    store.runtime.return_value = SumoRuntimeRecord(
        verified=True, version="test SUMO", checked_at=datetime.now(UTC), architecture="aarch64"
    )
    app.dependency_overrides[get_checks] = lambda: FakeChecks()
    app.dependency_overrides[get_store] = lambda: store
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/system/capabilities")
    assert response.json()["capabilities"]["simulation_runtime"] is True
    assert response.json()["runtime"]["verified"] is True


async def test_diagnostic_submit_lookup_validation_and_missing_job() -> None:
    app = create_app()
    now = datetime.now(UTC)
    job = DiagnosticJob(
        job_id=uuid4(), kind="diagnostic", status="queued", created_at=now, updated_at=now
    )
    store = AsyncMock()
    store.enqueue.return_value = job
    store.get.return_value = job
    app.dependency_overrides[get_store] = lambda: store
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/diagnostics", json={"kind": "diagnostic"})
        assert response.status_code == 202
        assert UUID(response.json()["job_id"]) == job.job_id
        assert response.headers["location"] == f"/api/v1/diagnostics/{job.job_id}"
        assert (await client.get(response.headers["location"])).status_code == 200
        for payload in (
            {"kind": "run_simulation"},
            {"kind": "diagnostic", "secret": "do-not-echo"},
        ):
            invalid = await client.post("/api/v1/diagnostics", json=payload)
            assert invalid.status_code == 422
            assert "do-not-echo" not in invalid.text
        assert (await client.get("/api/v1/diagnostics/not-a-uuid")).status_code == 422
        store.get.return_value = None
        assert (await client.get(f"/api/v1/diagnostics/{uuid4()}")).status_code == 404


@pytest.mark.parametrize(
    "error,status", [(QueueFullError(), 429), (ConnectionError("private URL"), 503)]
)
async def test_diagnostics_fail_safely(error: Exception, status: int) -> None:
    app = create_app()
    store = AsyncMock()
    store.enqueue.side_effect = error
    app.dependency_overrides[get_store] = lambda: store
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/diagnostics", json={"kind": "diagnostic"})
    assert response.status_code == status
    assert "private" not in response.text


async def test_runtime_record_is_not_accepted_without_fresh_ttl_and_timestamp() -> None:
    cache = AsyncMock()
    record = SumoRuntimeRecord(
        verified=True,
        version="SUMO test",
        checked_at=datetime.now(UTC) - timedelta(minutes=2),
        architecture="aarch64",
    )
    cache.get.return_value = record.model_dump_json()
    cache.ttl.return_value = 30
    store = DiagnosticsStore(cache, 1)
    assert await store.runtime() is None
    cache.get.return_value = "not JSON"
    assert await store.runtime() is None
    cache.get.return_value = record.model_copy(
        update={"checked_at": datetime.now(UTC)}
    ).model_dump_json()
    cache.ttl.return_value = -1
    assert await store.runtime() is None


async def test_queue_reservation_is_one_atomic_operation() -> None:
    cache = AsyncMock()
    cache.eval.return_value = 1
    job = await DiagnosticsStore(cache, 1).enqueue("diagnostic")
    cache.eval.assert_awaited_once()
    arguments = cache.eval.call_args.args
    assert arguments[1] == 2
    assert arguments[4] == "20"
    assert arguments[6] == "300"
    assert arguments[7] == str(job.job_id)
    cache.eval.return_value = 0
    with pytest.raises(QueueFullError):
        await DiagnosticsStore(cache, 1).enqueue("diagnostic")


def test_json_logging_omits_exception_text() -> None:
    error = ValueError("private connection password")
    record = logging.LogRecord(
        "test", logging.ERROR, "", 1, "Dependency failed", (), (ValueError, error, None)
    )
    output = JsonFormatter().format(record)
    assert json.loads(output)["exception_type"] == "ValueError"
    assert "password" not in output


async def test_unhandled_errors_use_central_safe_response() -> None:
    app = create_app()

    @app.get("/test-error")
    async def fail() -> None:
        raise RuntimeError("private internal detail")

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test-error")
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "An internal error occurred"}
    }
