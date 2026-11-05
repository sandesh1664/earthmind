"""Actual owned process-group termination plus isolated worker transaction boundaries."""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from earthmind_contracts.simulation import (
    DemandConfig,
    SimulationInput,
    WorkerClaim,
    canonical_checksum,
)
from earthmind_worker.settings import Settings
from earthmind_worker.simulation_jobs import execute_claim, terminate_group


def claim() -> WorkerClaim:
    config = SimulationInput(
        network_version_id=uuid4(),
        network_artifact="fixture-only-not-geography",
        network_sha256="a" * 64,
        source_sha256="b" * 64,
        mapping_sha256="c" * 64,
        demand=DemandConfig(),
    )
    return WorkerClaim(
        run_id=uuid4(),
        input_config=config,
        seed=config.demand.seed,
        input_sha256=canonical_checksum(config.model_dump(mode="json")),
    )


@pytest.mark.skipif(os.name != "posix", reason="Production native process groups require POSIX")
async def test_owned_native_process_group_does_not_leave_a_live_grandchild(tmp_path: Path) -> None:
    marker = tmp_path / "native-heartbeat"
    child_code = (
        "import pathlib,sys,time\n"
        "path=pathlib.Path(sys.argv[1])\n"
        "while True:\n path.write_text(str(time.monotonic()));time.sleep(0.02)\n"
    )
    parent_code = (
        "import pathlib,subprocess,sys,time\n"
        "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]])\n"
        "deadline=time.monotonic()+3\n"
        "while not pathlib.Path(sys.argv[2]).exists() "
        "and time.monotonic()<deadline: time.sleep(0.01)\n"
        "print('ready',flush=True)\n"
        "time.sleep(60)\n"
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        parent_code,
        child_code,
        str(marker),
        start_new_session=True,
        stdout=asyncio.subprocess.PIPE,
    )
    try:
        assert process.stdout is not None
        assert await asyncio.wait_for(process.stdout.readline(), 4) == b"ready\n"
        assert marker.exists(), "The actual grandchild must be running before cancellation"
        await terminate_group(process)
        assert process.returncode is not None
        last = marker.read_text()
        await asyncio.sleep(0.15)
        assert marker.read_text() == last, "The owned grandchild must stop doing work"
    finally:
        await terminate_group(process)


async def test_lost_lease_or_cancel_stops_actual_child_before_any_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import earthmind_worker.simulation_jobs as jobs

    create = asyncio.create_subprocess_exec
    children: list[asyncio.subprocess.Process] = []

    async def launch_fixture(*_arguments: object, **options: object) -> asyncio.subprocess.Process:
        process = await create(sys.executable, "-c", "import time;time.sleep(60)", **options)
        children.append(process)
        return process

    monkeypatch.setattr(jobs.asyncio, "create_subprocess_exec", launch_fixture)
    store, cache = AsyncMock(), AsyncMock()
    store.heartbeat.return_value = False
    requested = claim()
    await execute_claim(store, cache, requested, Settings(simulation_artifacts_root=str(tmp_path)))
    assert children[0].returncode is not None
    store.publish.assert_not_awaited()
    store.fail.assert_awaited_once()
    assert store.fail.call_args.args[1] == "worker_lost"
    assert not (tmp_path / str(requested.run_id)).exists()
    assert len(list(tmp_path.glob("*.failed"))) == 1


async def test_shutdown_interrupts_owned_child_and_records_tracked_worker_loss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import earthmind_worker.simulation_jobs as jobs

    create = asyncio.create_subprocess_exec
    started = asyncio.Event()
    children: list[asyncio.subprocess.Process] = []

    async def launch_fixture(*_arguments: object, **options: object) -> asyncio.subprocess.Process:
        process = await create(sys.executable, "-c", "import time;time.sleep(60)", **options)
        children.append(process)
        started.set()
        return process

    monkeypatch.setattr(jobs.asyncio, "create_subprocess_exec", launch_fixture)
    store, cache = AsyncMock(), AsyncMock()
    store.heartbeat.return_value = True
    task = asyncio.create_task(
        execute_claim(store, cache, claim(), Settings(simulation_artifacts_root=str(tmp_path)))
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert children[0].returncode is not None
    store.publish.assert_not_awaited()
    assert store.fail.call_args.args[1] == "worker_lost"


def test_native_and_runner_environments_do_not_inherit_service_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from earthmind_worker.simulation_environment import native_environment, runner_environment

    monkeypatch.setenv("DATABASE_URL", "private-unit-fixture-only")
    monkeypatch.setenv("EARTHMIND_DEV_WRITE_TOKEN", "private-unit-fixture-only")
    monkeypatch.setenv("NEXT_PUBLIC_CESIUM_ION_TOKEN", "public-unit-fixture-only")
    monkeypatch.setenv("REDIS_URL", "private-unit-fixture-only")
    monkeypatch.setenv("PATH", "/usr/bin")
    native = native_environment()
    assert native["PATH"] == "/usr/bin"
    for environment in [native, runner_environment(Settings())]:
        assert not any(
            name in environment
            for name in [
                "DATABASE_URL",
                "EARTHMIND_DEV_WRITE_TOKEN",
                "NEXT_PUBLIC_CESIUM_ION_TOKEN",
                "REDIS_URL",
            ]
        )


async def test_missing_artifact_volume_fails_claim_without_waiting_for_lease_expiry(
    tmp_path: Path,
) -> None:
    store, cache = AsyncMock(), AsyncMock()
    await execute_claim(
        store,
        cache,
        claim(),
        Settings(simulation_artifacts_root=str(tmp_path / "missing-volume")),
    )
    store.publish.assert_not_awaited()
    store.fail.assert_awaited_once()
    assert store.fail.call_args.args[1] == "resource_limit"
    assert "mounted volume" in store.fail.call_args.args[2]


def test_native_failure_protocol_maps_only_allowlisted_codes_and_never_raw_errors(
    tmp_path: Path,
) -> None:
    from earthmind_worker.simulation_jobs import failure_summary

    path = tmp_path / "failure.json"
    path.write_text('{"code":"input_invalid","message":"private-example-credential"}')
    code, message = failure_summary(path, 1)
    assert code == "input_invalid"
    assert "network checksums" in message
    assert "private-example-credential" not in message
    path.write_text('{"code":"unknown","message":"private-example-credential"}')
    assert failure_summary(path, 1)[0] == "execution_failed"
    path.unlink()
    assert failure_summary(path, -25)[0] == "resource_limit"


async def test_redis_runtime_marker_failure_does_not_kill_healthy_owned_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Only the controller protocol is a fixture; this is not native SUMO evidence."""
    import json

    import earthmind_worker.simulation_jobs as jobs
    from redis.exceptions import ConnectionError as RedisConnectionError

    create = asyncio.create_subprocess_exec
    requested = claim()
    children: list[asyncio.subprocess.Process] = []
    payload = {
        "engine_version": "unit-protocol-fixture-not-native",
        "input_sha256": requested.input_sha256,
        "manifest_path": f"{requested.run_id}/replay-manifest.json",
        "metrics": [
            {
                "metric_name": "unit_protocol_counter",
                "value": 1,
                "unit": "count",
                "aggregation": "unit_fixture",
                "calculation_version": "not-SUMO-output",
            }
        ],
        "artifacts": [
            {
                "artifact_type": "unit_protocol_fixture",
                "relative_path": f"{requested.run_id}/unit-fixture.json",
                "checksum_sha256": "0" * 64,
                "size_bytes": 0,
                "content_type": "application/json",
            }
        ],
    }
    child_code = (
        "import json,pathlib,sys,time\n"
        "root=pathlib.Path(sys.argv[1])\n"
        "for step in [1,2]:\n"
        " data={'engine_version':'1.15.0','progress':{'simulated_seconds':step,"
        "'duration_seconds':600,'departed':0,'completed':0,'active':0}}\n"
        " temporary=root/'progress.writing'\n"
        " temporary.write_text(json.dumps(data))\n"
        " temporary.replace(root/'progress.json')\n"
        " time.sleep(0.2)\n"
        "(root/'published-result.json').write_text(sys.argv[2])\n"
    )

    async def launch_fixture(*arguments: object, **options: object) -> asyncio.subprocess.Process:
        process = await create(
            sys.executable, "-c", child_code, str(arguments[-1]), json.dumps(payload), **options
        )
        children.append(process)
        return process

    marker = AsyncMock(side_effect=RedisConnectionError("unit-private-marker-detail"))
    monkeypatch.setattr(jobs.asyncio, "create_subprocess_exec", launch_fixture)
    monkeypatch.setattr(jobs, "publish_runtime", marker)
    store, cache = AsyncMock(), AsyncMock()
    store.heartbeat.return_value = True
    store.publish.return_value = True
    await execute_claim(
        store,
        cache,
        requested,
        Settings(simulation_artifacts_root=str(tmp_path), simulation_poll_interval_seconds=0.1),
    )
    assert children[0].returncode == 0, "Redis marker failure must not terminate the healthy child"
    assert marker.await_count >= 2, "The fixture must exercise repeated marker publication failures"
    store.fail.assert_not_awaited()
    store.publish.assert_awaited_once()
    assert (tmp_path / str(requested.run_id)).is_dir()
    messages = [record.getMessage() for record in caplog.records]
    assert sum("Runtime marker unavailable" in message for message in messages) == 1
    assert all("unit-private-marker-detail" not in message for message in messages)


async def test_database_heartbeat_failure_still_stops_child_and_blocks_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import earthmind_worker.simulation_jobs as jobs

    create = asyncio.create_subprocess_exec
    children: list[asyncio.subprocess.Process] = []

    async def launch_fixture(*_arguments: object, **options: object) -> asyncio.subprocess.Process:
        process = await create(sys.executable, "-c", "import time;time.sleep(60)", **options)
        children.append(process)
        return process

    monkeypatch.setattr(jobs.asyncio, "create_subprocess_exec", launch_fixture)
    marker = AsyncMock()
    monkeypatch.setattr(jobs, "publish_runtime", marker)
    store, cache = AsyncMock(), AsyncMock()
    store.heartbeat.side_effect = OSError("unit-private-database-detail")
    await execute_claim(store, cache, claim(), Settings(simulation_artifacts_root=str(tmp_path)))
    assert children[0].returncode is not None
    store.fail.assert_awaited_once()
    assert store.fail.call_args.args[1] == "execution_failed"
    store.publish.assert_not_awaited()
    marker.assert_not_awaited()
