"""M04 unit/security contracts; these isolated fixtures are not SUMO execution proof."""

import hashlib
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from earthmind_api.dependencies import get_session
from earthmind_api.main import create_app
from earthmind_api.request_limits import GeoBodyLimitMiddleware
from earthmind_api.settings import Settings
from earthmind_api.simulation_artifacts import (
    artifact_path,
    validate_result_metrics,
    verified_bytes,
)
from earthmind_contracts.simulation import (
    ArtifactValue,
    DemandConfig,
    MetricValue,
    ProgressUpdate,
    PublishedResult,
    ReplayEvent,
    ReplayFrame,
    ScenarioCreate,
    SimulationInput,
    TrajectoryChunk,
    VehicleSample,
    canonical_checksum,
)
from fastapi import FastAPI
from pydantic import ValidationError


def test_seeded_configuration_has_stable_canonical_identity() -> None:
    first = DemandConfig(trip_target=500, seed=7)
    second = DemandConfig(seed=7, trip_target=500)
    assert canonical_checksum(first.model_dump(mode="json")) == canonical_checksum(
        second.model_dump(mode="json")
    )
    assert canonical_checksum(first.model_dump(mode="json")) != canonical_checksum(
        first.model_copy(update={"seed": 8}).model_dump(mode="json")
    )
    assert first.effective_trip_count == 500
    assert DemandConfig(trip_target=1000, demand_multiplier=1.2).effective_trip_count == 1200


@pytest.mark.parametrize(
    "values",
    [
        {"trip_target": 0},
        {"trip_target": 5001},
        {"trip_target": 2000, "demand_multiplier": 3},
        {"duration_seconds": 29},
        {"duration_seconds": 3601},
        {"seed": -1},
        {"vehicle_class": "truck"},
        {"od_policy": "observed_rta"},
        {"sample_interval_seconds": 0},
        {"demand_multiplier": float("nan")},
        {"arbitrary_command": "echo unsafe"},
    ],
)
def test_demand_rejects_unbounded_or_unsupported_controls(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        DemandConfig.model_validate(values)


def test_input_and_scenario_cannot_accept_arbitrary_paths_or_hidden_controls() -> None:
    with pytest.raises(ValidationError):
        SimulationInput(
            network_version_id=uuid4(),
            network_artifact="../../outside",
            network_sha256="a" * 64,
            source_sha256="b" * 64,
            mapping_sha256="c" * 64,
            demand=DemandConfig(),
        )
    with pytest.raises(ValidationError):
        ScenarioCreate.model_validate(
            {"name": "probe", "network_version_id": str(uuid4()), "road_closures": ["edge"]}
        )
    with pytest.raises(ValidationError):
        ScenarioCreate(name="bad\nname", network_version_id=uuid4())


def test_progress_uses_reported_simulation_time_and_rejects_impossible_counts() -> None:
    value = ProgressUpdate(
        duration_seconds=600, simulated_seconds=35, departed=20, completed=4, active=16
    )
    assert value.simulated_seconds == 35
    with pytest.raises(ValidationError):
        ProgressUpdate(duration_seconds=600, simulated_seconds=601)
    with pytest.raises(ValidationError):
        ProgressUpdate(duration_seconds=600, departed=1, completed=2)


def test_replay_contract_retains_discontinuities_and_exact_native_event_times() -> None:
    run_id = uuid4()
    sample = VehicleSample(
        id="v00001", longitude=55.27, latitude=25.19, heading=90, speed=8, segment_id=3
    )
    value = TrajectoryChunk(
        run_id=run_id,
        chunk_id="000000",
        frames=[ReplayFrame(time=2, vehicles=[sample]), ReplayFrame(time=4, vehicles=[])],
        events=[ReplayEvent(id=sample.id, time=3, type="arrived")],
    )
    restored = TrajectoryChunk.model_validate_json(value.model_dump_json())
    assert restored.frames[0].vehicles[0].segment_id == 3
    assert restored.events[0].time == 3
    assert restored.frames[1].vehicles == []
    with pytest.raises(ValidationError):
        TrajectoryChunk(
            run_id=run_id,
            chunk_id="000000",
            frames=[ReplayFrame(time=4, vehicles=[]), ReplayFrame(time=2, vehicles=[])],
        )
    with pytest.raises(ValidationError):
        VehicleSample(id="v", longitude=float("nan"), latitude=25, heading=0, speed=1)


@pytest.mark.parametrize(
    "tail",
    [
        "../outside.txt",
        "../other/secret.txt",
        "/absolute.txt",
        "a/../../outside.txt",
        "a\\outside.txt",
        "./value.json",
        "a//value.json",
    ],
)
def test_artifact_paths_reject_traversal_and_noncanonical_references(
    tmp_path: Path, tail: str
) -> None:
    run_id = uuid4()
    (tmp_path / str(run_id)).mkdir()
    with pytest.raises((ValueError, FileNotFoundError)):
        artifact_path(tmp_path, run_id, f"{run_id}/{tail}")


def test_artifact_lookup_checks_scope_symlinks_size_and_checksum(tmp_path: Path) -> None:
    run_id = uuid4()
    directory = tmp_path / str(run_id)
    directory.mkdir()
    payload = b'{"contract_fixture_only":true}'
    (directory / "value.json").write_bytes(payload)
    reference = f"{run_id}/value.json"
    checksum = hashlib.sha256(payload).hexdigest()
    assert verified_bytes(tmp_path, run_id, reference, checksum, len(payload)) == payload
    with pytest.raises(ValueError):
        verified_bytes(tmp_path, run_id, reference, "0" * 64, len(payload))
    with pytest.raises(ValueError):
        verified_bytes(tmp_path, run_id, reference, checksum, len(payload) + 1)
    with pytest.raises(ValueError):
        verified_bytes(tmp_path, run_id, reference, checksum, len(payload), max_bytes=4)
    outside = tmp_path / "outside.txt"
    outside.write_text("unit fixture")
    (directory / "escape.txt").symlink_to(outside)
    with pytest.raises(ValueError):
        artifact_path(tmp_path, run_id, f"{run_id}/escape.txt")
    with pytest.raises(ValueError):
        artifact_path(tmp_path, uuid4(), reference)


def result_metrics(completed: int = 0) -> PublishedResult:
    values = {
        "generated_trips": 2,
        "departed_trips": 2,
        "completed_trips": completed,
        "incomplete_trips": 2 - completed,
        "mean_trip_duration": None if completed == 0 else 3,
        "mean_time_loss": None if completed == 0 else 1,
        "mean_waiting_time": None if completed == 0 else 0,
        "mean_moving_speed": None,
        "teleports": 0,
        "simulation_duration": 5,
        "worker_execution_time": 1,
    }
    return PublishedResult(
        engine_version="contract-fixture-only",
        input_sha256="a" * 64,
        manifest_path=f"{uuid4()}/manifest.json",
        metrics=[
            MetricValue(metric_name=name, value=value, unit="fixture")
            for name, value in values.items()
        ],
        artifacts=[
            ArtifactValue(
                artifact_type="replay_manifest",
                relative_path="unused-fixture.json",
                checksum_sha256="b" * 64,
                size_bytes=0,
                content_type="application/json",
            )
        ],
    )


def test_zero_qualifying_trip_means_are_unavailable_and_counts_are_consistent() -> None:
    value = result_metrics()
    validate_result_metrics(value, 2)
    bad = value.model_copy(
        update={
            "metrics": [
                metric.model_copy(update={"value": 0})
                if metric.metric_name == "mean_trip_duration"
                else metric
                for metric in value.metrics
            ]
        }
    )
    with pytest.raises(ValueError):
        validate_result_metrics(bad, 2)
    with pytest.raises(ValueError):
        validate_result_metrics(value, 3)
    validate_result_metrics(result_metrics(completed=1), 2)
    with pytest.raises(ValidationError):
        MetricValue(metric_name="delay", value=float("inf"), unit="s")


async def test_expensive_mutations_keep_the_existing_server_write_gate() -> None:
    application = create_app(Settings(dev_write_token="test-only-not-a-working-development-secret"))

    async def no_database():
        yield None

    application.dependency_overrides[get_session] = no_database
    paths = [
        "/api/v1/scenarios",
        "/api/v1/simulations",
        f"/api/v1/scenarios/{uuid4()}/validate",
        f"/api/v1/simulations/{uuid4()}/cancel",
        "/api/v1/comparisons",
    ]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test"
    ) as client:
        for path in paths:
            response = await client.post(path, json={})
            assert response.status_code == 403
            assert "test-only-not-a-working-development-secret" not in response.text


async def test_m04_streaming_body_budget_and_openapi_contracts() -> None:
    application = FastAPI()
    application.add_middleware(GeoBodyLimitMiddleware, max_bytes=262144)

    @application.post("/api/v1/scenarios")
    async def create() -> dict[str, bool]:
        return {"accepted": True}

    async def body():
        yield b'{"data":"'
        yield b"x" * 64000
        yield b"x" * 64000
        yield b'"}'

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/scenarios", content=body())
    assert response.status_code == 413
    schema = create_app().openapi()
    for path in [
        "/api/v1/scenarios",
        "/api/v1/simulations",
        "/api/v1/comparisons",
        "/api/v1/simulations/{run_id}/replay/manifest",
        "/api/v1/simulations/{run_id}/replay/chunks/{chunk_id}",
    ]:
        assert path in schema["paths"]
    assert schema["paths"]["/api/v1/simulations"]["post"]["security"]
