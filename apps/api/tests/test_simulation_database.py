"""Real PostgreSQL transaction tests, rolled back; not native SUMO execution proof."""

import hashlib
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from earthmind_api.dependencies import Infrastructure, get_session
from earthmind_api.fixtures import DEMAND_ID, NETWORK_ID
from earthmind_api.geospatial_models import RunArtifact, RunMetric, Scenario, SimulationRun
from earthmind_api.main import create_app
from earthmind_api.seed import seed
from earthmind_api.settings import Settings
from earthmind_api.simulation_service import get_run
from earthmind_api.simulation_worker_store import SimulationWorkerStore
from earthmind_contracts.simulation import (
    ArtifactValue,
    DemandConfig,
    MetricValue,
    ProgressUpdate,
    PublishedResult,
    ReplayManifest,
    SimulationInput,
    canonical_checksum,
)
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


@pytest.fixture
async def simulation_session() -> AsyncIterator[AsyncSession]:
    url = os.environ.get("EARTHMIND_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires explicitly configured real migrated PostgreSQL database")
    infrastructure = Infrastructure(Settings(database_url=url))
    async with infrastructure.engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False) as session:
            try:
                await seed(session)
                yield session
            finally:
                await transaction.rollback()
    await infrastructure.close()


async def contract_run(session: AsyncSession) -> SimulationRun:
    demand = DemandConfig(trip_target=2, duration_seconds=30)
    scenario = Scenario(
        network_version_id=NETWORK_ID,
        demand_profile_id=DEMAND_ID,
        name="M04 rollback contract fixture",
        description="No native execution; transaction test only",
        duration_seconds=30,
        config={"schema_version": 1, "demand": demand.model_dump(mode="json")},
        configuration_checksum="a" * 64,
    )
    session.add(scenario)
    await session.flush()
    snapshot = SimulationInput(
        network_version_id=NETWORK_ID,
        network_artifact="unit-contract",
        network_sha256="a" * 64,
        source_sha256="b" * 64,
        mapping_sha256="c" * 64,
        demand=demand,
    )
    value = SimulationRun(
        scenario_id=scenario.id,
        seed=demand.seed,
        input_sha256=canonical_checksum(snapshot.model_dump(mode="json")),
        input_config=snapshot.model_dump(mode="json"),
        progress=ProgressUpdate(duration_seconds=30).model_dump(mode="json"),
        created_at=datetime(1990, 1, 1, tzinfo=UTC),
        idempotency_key=f"test-{uuid4()}",
        request_sha256="d" * 64,
    )
    session.add(value)
    await session.flush()
    return value


def bound_store(
    session: AsyncSession, root: Path, worker: str = "test-worker"
) -> SimulationWorkerStore:
    @asynccontextmanager
    async def transaction():
        yield session
        await session.flush()

    infrastructure = SimpleNamespace(
        settings=Settings(simulation_artifacts_root=str(root)), session=transaction
    )
    return SimulationWorkerStore(cast(Infrastructure, infrastructure), worker)


def contract_output(root: Path, run: SimulationRun) -> PublishedResult:
    directory = root / str(run.id)
    directory.mkdir()
    manifest = ReplayManifest(
        run_id=run.id,
        network_version_id=NETWORK_ID,
        duration_seconds=30,
        sample_interval_seconds=2,
        chunks=[],
        counts=[],
    )
    payload = manifest.model_dump_json().encode()
    (directory / "manifest.json").write_bytes(payload)
    values = {
        "generated_trips": 2,
        "departed_trips": 0,
        "completed_trips": 0,
        "incomplete_trips": 2,
        "mean_trip_duration": None,
        "mean_time_loss": None,
        "mean_waiting_time": None,
        "mean_moving_speed": None,
        "teleports": 0,
        "simulation_duration": 30,
        "worker_execution_time": 1,
    }
    return PublishedResult(
        engine_version="contract-fixture-not-native-proof",
        input_sha256=run.input_sha256,
        manifest_path=f"{run.id}/manifest.json",
        metrics=[
            MetricValue(metric_name=name, value=value, unit="contract_fixture")
            for name, value in values.items()
        ],
        artifacts=[
            ArtifactValue(
                artifact_type="replay_manifest",
                relative_path=f"{run.id}/manifest.json",
                checksum_sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
                content_type="application/json",
            )
        ],
    )


async def test_atomic_claim_progress_publication_and_duplicate_fencing(
    simulation_session: AsyncSession, tmp_path: Path
) -> None:
    session = simulation_session
    run = await contract_run(session)
    store = bound_store(session, tmp_path)
    claim = await store.claim()
    assert claim is not None and claim.run_id == run.id
    await session.refresh(run)
    assert run.status == "running" and run.started_at is not None
    assert not await bound_store(session, tmp_path, "another-worker").heartbeat(run.id)
    assert await store.heartbeat(run.id, ProgressUpdate(duration_seconds=30, simulated_seconds=30))
    output = contract_output(tmp_path, run)
    assert await store.publish(run.id, output)
    await session.flush()
    await session.refresh(run)
    assert run.status == "succeeded" and run.finished_at is not None
    assert not await store.publish(run.id, output)
    assert (
        await session.scalar(
            select(func.count()).select_from(RunArtifact).where(RunArtifact.run_id == run.id)
        )
        == 1
    )
    metric = await session.scalar(
        select(RunMetric).where(
            RunMetric.run_id == run.id, RunMetric.metric_name == "mean_trip_duration"
        )
    )
    assert metric is not None and metric.value is None
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(
                text("UPDATE simulation_runs SET status='running' WHERE id=:id"), {"id": run.id}
            )


async def test_cancellation_fences_publication_and_late_success(
    simulation_session: AsyncSession, tmp_path: Path
) -> None:
    session = simulation_session
    run = await contract_run(session)
    store = bound_store(session, tmp_path)
    await store.claim()
    run.cancel_requested = True
    await session.flush()
    assert not await store.heartbeat(run.id)
    output = contract_output(tmp_path, run)
    assert not await store.publish(run.id, output)
    await store.fail(run.id, "cancelled", "Test fixture cancellation acknowledged", cancelled=True)
    await session.refresh(run)
    assert run.status == "cancelled"
    assert not await store.publish(run.id, output)
    assert (
        await session.scalar(
            select(func.count()).select_from(RunArtifact).where(RunArtifact.run_id == run.id)
        )
        == 0
    )


async def test_expired_lease_is_failed_and_cannot_publish(
    simulation_session: AsyncSession, tmp_path: Path
) -> None:
    session = simulation_session
    run = await contract_run(session)
    store = bound_store(session, tmp_path)
    await store.claim()
    run.heartbeat_at = datetime.now(UTC) - timedelta(seconds=60)
    await session.flush()
    assert not await store.heartbeat(run.id)
    assert await store.reconcile_stale() >= 1
    await session.refresh(run)
    assert run.status == "failed" and run.error_code == "worker_lost"
    assert not await store.publish(run.id, contract_output(tmp_path, run))


async def test_new_state_guard_supports_queued_failure_and_immutable_input(
    simulation_session: AsyncSession,
) -> None:
    session = simulation_session
    run = await contract_run(session)
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(
                text("UPDATE simulation_runs SET input_config='{}'::jsonb WHERE id=:id"),
                {"id": run.id},
            )
    run.status = "failed"
    run.error_code = "input_invalid"
    await session.flush()
    await session.refresh(run)
    assert run.started_at is None and run.finished_at is not None
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(
                text("UPDATE simulation_runs SET status='succeeded' WHERE id=:id"), {"id": run.id}
            )


async def test_real_network_api_scenario_idempotency_cancel_and_tracked_retry(
    simulation_session: AsyncSession, tmp_path: Path
) -> None:
    inputs = Path(__file__).resolve().parents[3] / "data/dubai-osm"
    manifest_path = inputs / "recovery-v1/import-manifest.json"
    if not manifest_path.exists():
        pytest.skip("Retained actual Dubai SUMO inputs required; no substitute geography")
    network_id = json.loads(manifest_path.read_text())["network_id"]
    token = "test-only-not-a-working-development-secret"
    app = create_app(
        Settings(
            dev_write_token=token,
            simulation_inputs_root=str(inputs),
            simulation_artifacts_root=str(tmp_path),
        )
    )
    app.state.infrastructure = SimpleNamespace(cache=AsyncMock())

    async def override_session():
        yield simulation_session

    app.dependency_overrides[get_session] = override_session
    headers = {"X-Earthmind-Dev-Token": token, "Idempotency-Key": f"test-{uuid4()}"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        catalogue = await client.get("/api/v1/simulation-networks")
        assert catalogue.status_code == 200
        actual = next(item for item in catalogue.json()["items"] if item["id"] == network_id)
        assert actual["validation"]["valid"] is True
        scenario = await client.post(
            "/api/v1/scenarios",
            headers=headers,
            json={
                "name": "Real network transaction test; no execution",
                "network_version_id": network_id,
                "demand": {"trip_target": 2, "duration_seconds": 30},
            },
        )
        assert scenario.status_code == 201, scenario.text
        scenario_id = scenario.json()["id"]
        payload = {"scenario_id": scenario_id}
        first = await client.post("/api/v1/simulations", headers=headers, json=payload)
        assert first.status_code == 202, first.text
        repeated = await client.post("/api/v1/simulations", headers=headers, json=payload)
        assert repeated.status_code == 202 and repeated.json()["id"] == first.json()["id"]
        conflict = await client.post(
            "/api/v1/simulations", headers=headers, json={**payload, "seed": 9}
        )
        assert conflict.status_code == 409
        identifier = first.json()["id"]
        assert (await client.get(f"/api/v1/simulations/{identifier}/metrics")).status_code == 409
        cancelled = await client.post(
            f"/api/v1/simulations/{identifier}/cancel", headers=headers, json={}
        )
        assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
        retried = await client.post(
            "/api/v1/simulations",
            headers={**headers, "Idempotency-Key": f"test-{uuid4()}"},
            json={"scenario_id": scenario_id, "retry_of": identifier},
        )
        assert retried.status_code == 202 and retried.json()["id"] != identifier
        assert retried.json()["attempt_number"] == 2 and retried.json()["retry_of"] == identifier
        await get_run(simulation_session, UUID(retried.json()["id"]))
