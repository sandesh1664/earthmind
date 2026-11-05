"""One native execution at a time, durable database claims and cancel-safe subprocesses."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import platform
import signal
import sys
import time
from collections.abc import Awaitable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from earthmind_api.dependencies import Infrastructure
from earthmind_api.settings import Settings as ApiSettings
from earthmind_api.simulation_worker_store import SimulationWorkerStore
from earthmind_contracts.simulation import (
    SIMULATION_QUEUE_KEY,
    ProgressUpdate,
    PublishedResult,
    WorkerClaim,
)
from redis.asyncio import Redis
from redis.exceptions import RedisError

from earthmind_worker.jobs import publish_runtime
from earthmind_worker.runtime_check import EXPECTED_SUMO_VERSION
from earthmind_worker.settings import Settings
from earthmind_worker.simulation_artifacts import (
    SimulationResourceLimit,
    atomic_json,
    output_bytes,
)
from earthmind_worker.simulation_environment import runner_environment

logger = logging.getLogger(__name__)


async def terminate_group(process: asyncio.subprocess.Process) -> None:
    """The isolated Python child and SUMO share this group; neither may outlive a job."""
    if process.returncode is not None:
        # The runner reaps its SUMO child normally. A killed runner can leave an
        # inherited process group alive, so still signal the owned group below.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        return
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        await asyncio.wait_for(process.wait(), 3)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        await process.wait()


def _progress(path: Path) -> tuple[ProgressUpdate | None, bool]:
    if not path.exists():
        return None, False
    if path.is_symlink() or path.stat().st_size > 65536:
        raise ValueError("Runner progress exceeds its restricted protocol")
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError("Runner progress must be an object")
    progress = ProgressUpdate.model_validate(value.get("progress"))
    native_verified = (
        value.get("engine_version") == EXPECTED_SUMO_VERSION and progress.simulated_seconds > 0
    )
    return progress, native_verified


def failure_summary(path: Path, returncode: int | None) -> tuple[str, str]:
    messages = {
        "input_invalid": (
            "Retained SUMO input or demand validation failed. "
            "Revalidate the scenario and verify its network checksums."
        ),
        "output_invalid": "SUMO output or replay verification failed; no results were published.",
        "resource_limit": (
            "Simulation exceeded a file or memory resource budget, "
            "or its workspace became unavailable."
        ),
        "worker_lost": "Native execution was interrupted; retry creates a new tracked attempt.",
        "execution_failed": "Native SUMO execution failed; inspect its bounded engine log.",
    }
    code = "resource_limit" if returncode in {-9, -24, -25} else "execution_failed"
    if path.exists() and not path.is_symlink() and path.stat().st_size <= 16384:
        try:
            recorded = json.loads(path.read_bytes())
            candidate = recorded.get("code") if isinstance(recorded, dict) else None
            if candidate == "cancelled":
                code = "worker_lost"
            elif candidate in messages:
                code = candidate
        except (ValueError, OSError, TypeError):
            pass
    return code, messages[code]


async def execute_claim(
    store: SimulationWorkerStore, cache: Redis, claim: WorkerClaim, configuration: Settings
) -> None:
    try:
        root = Path(configuration.simulation_artifacts_root).resolve(strict=True)
        workspace = root / f".{claim.run_id}-{uuid4().hex}.partial"
        workspace.mkdir(mode=0o700)
        atomic_json(workspace / "input.json", claim.model_dump(mode="json"), 65536)
    except (OSError, ValueError):
        await store.fail(
            claim.run_id,
            "resource_limit",
            "Worker artifact workspace is unavailable; verify its mounted volume and permissions",
        )
        return
    process: asyncio.subprocess.Process | None = None
    published = False
    started = time.monotonic()
    last_native_seconds = float("-inf")
    marker_warning_active = False
    try:
        with (workspace / "runner.log").open("wb") as log:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "earthmind_worker.simulation_runner",
                "--workspace",
                str(workspace),
                stdout=log,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
                env=runner_environment(configuration),
            )
            while process.returncode is None:
                if time.monotonic() - started > configuration.simulation_timeout_seconds:
                    await terminate_group(process)
                    await store.fail(
                        claim.run_id, "timeout", "SUMO exceeded its wall-clock execution limit"
                    )
                    return
                output_bytes(workspace)
                progress, native_verified = _progress(workspace / "progress.json")
                if not await store.heartbeat(claim.run_id, progress):
                    await terminate_group(process)
                    await store.fail(
                        claim.run_id,
                        "worker_lost",
                        "Native execution stopped after cancellation or loss of its worker lease",
                    )
                    return
                if (
                    native_verified
                    and progress is not None
                    and progress.simulated_seconds > last_native_seconds
                ):
                    # A currently advancing real SUMO run is stronger runtime evidence
                    # than expiring the M01 marker while its tiny probe waits for the lock.
                    last_native_seconds = progress.simulated_seconds
                    try:
                        await publish_runtime(
                            cache,
                            {
                                "verified": True,
                                "version": EXPECTED_SUMO_VERSION,
                                "checked_at": datetime.now(UTC).isoformat(),
                                "architecture": platform.machine(),
                            },
                        )
                    except (RedisError, OSError, TimeoutError):
                        if not marker_warning_active:
                            logger.warning(
                                "Runtime marker unavailable; continuing the owned native simulation"
                            )
                        marker_warning_active = True
                    else:
                        marker_warning_active = False
                try:
                    await asyncio.wait_for(
                        process.wait(), configuration.simulation_poll_interval_seconds
                    )
                except TimeoutError:
                    pass
            progress, _native = _progress(workspace / "progress.json")
            if not await store.heartbeat(claim.run_id, progress):
                await store.fail(
                    claim.run_id,
                    "worker_lost",
                    "Native output was not published after cancellation or lease loss",
                )
                return
            if process.returncode != 0:
                code, message = failure_summary(workspace / "failure.json", process.returncode)
                await store.fail(claim.run_id, code, message)
                return
            result_path = workspace / "published-result.json"
            if result_path.is_symlink() or not 1 <= result_path.stat().st_size <= 1024 * 1024:
                raise ValueError("Runner result exceeds its restricted publication protocol")
            result = PublishedResult.model_validate_json(result_path.read_bytes())
            if result.input_sha256 != claim.input_sha256:
                raise ValueError("Runner result differs from the claimed immutable input checksum")
            final = root / str(claim.run_id)
            if final.exists():
                raise ValueError("Run output already exists; duplicate publication is refused")
            workspace.rename(final)
            workspace = final
            published = await store.publish(claim.run_id, result)
            if not published:
                await store.fail(
                    claim.run_id,
                    "worker_lost",
                    "Completed output was not adopted after cancellation or lease loss",
                )
                return
            logger.info("Verified synthetic SUMO run published: %s", claim.run_id)
    except SimulationResourceLimit:
        if process is not None:
            await terminate_group(process)
        with contextlib.suppress(Exception):
            await store.fail(
                claim.run_id,
                "resource_limit",
                "Simulation reached its bounded output/log resource limit; "
                "no results were published",
            )
    except asyncio.CancelledError:
        if process is not None:
            await terminate_group(process)
        with contextlib.suppress(Exception):
            await store.fail(
                claim.run_id,
                "worker_lost",
                "Worker stopped during native execution; retry creates a new attempt",
            )
        raise
    except Exception:
        if process is not None:
            await terminate_group(process)
        with contextlib.suppress(Exception):
            await store.fail(
                claim.run_id,
                "execution_failed",
                "Worker could not publish verified SUMO outputs; inspect bounded run diagnostics",
            )
        logger.warning("Simulation execution failed for run %s", claim.run_id)
    finally:
        if process is not None:
            await terminate_group(process)
        if not published and workspace.exists() and workspace.name.endswith(".partial"):
            # Retain bounded diagnostics under a nonpublic name. Only registered
            # artifact categories of succeeded runs can be served by the API.
            workspace.rename(root / f".{claim.run_id}-{uuid4().hex}.failed")


async def consume_simulations(
    cache: Redis, stop: asyncio.Event, lock: asyncio.Lock, configuration: Settings
) -> None:
    infrastructure = Infrastructure(ApiSettings())
    store = SimulationWorkerStore(
        infrastructure,
        f"worker-{platform.node()[:48]}-{os.getpid()}-{uuid4().hex[:8]}",
        lease_seconds=configuration.simulation_lease_seconds,
    )
    await infrastructure.open()
    last_reconciliation = float("-inf")
    try:
        while not stop.is_set():
            try:
                if time.monotonic() - last_reconciliation >= 5:
                    recovered = await store.reconcile_stale()
                    if recovered:
                        logger.warning("Marked %d stale simulation leases terminal", recovered)
                    last_reconciliation = time.monotonic()
                async with lock:
                    if stop.is_set():
                        return
                    claim = await store.claim()
                    if claim is not None:
                        await execute_claim(store, cache, claim, configuration)
                        continue
            except asyncio.CancelledError:
                raise
            except Exception:
                # Driver errors can include connection strings. Never log native exception text.
                logger.warning("Durable simulation queue unavailable; retrying safely")
            try:
                await cast(Awaitable[Any], cache.blpop([SIMULATION_QUEUE_KEY], timeout=1))
            except Exception:
                # Redis is a wake-up hint. Durable database polling still claims jobs.
                try:
                    await asyncio.wait_for(
                        stop.wait(), configuration.simulation_poll_interval_seconds
                    )
                except TimeoutError:
                    pass
    finally:
        await infrastructure.close()
