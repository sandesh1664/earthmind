"""A bounded, single-consumer Redis queue for two whitelisted M01 diagnostics."""

import asyncio
import json
import logging
import os
import platform
import signal
import sys
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from earthmind_contracts import (
    DIAGNOSTIC_JOB_PREFIX,
    DIAGNOSTIC_JOB_TTL_SECONDS,
    DIAGNOSTIC_QUEUE_KEY,
    SUMO_RUNTIME_KEY,
    SUMO_RUNTIME_TTL_SECONDS,
    DiagnosticJob,
    SumoRuntimeRecord,
)
from pydantic import JsonValue, TypeAdapter, ValidationError
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

logger = logging.getLogger(__name__)
json_object = TypeAdapter(dict[str, JsonValue])
MAX_REDIS_FAILURES = 5


class NativeEngineBusy(RuntimeError):
    """The single native execution slot is occupied, not an unavailable runtime."""


async def execute_sumo(budget_seconds: float) -> dict[str, JsonValue]:
    """Isolate native tools, bound wall time, and kill their process group on cancellation."""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "earthmind_worker.runtime_check",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), budget_seconds)
        if process.returncode != 0:
            logger.warning("SUMO probe failed: %s", stderr.decode(errors="replace")[:2000])
            raise RuntimeError("SUMO runtime check failed")
        value: Any = json.loads(stdout)
        result = json_object.validate_python(value)
        if result.get("verified") is not True or result.get("vehicles_completed") != 2:
            raise RuntimeError("SUMO fixture did not complete both synthetic vehicles")
        return result
    finally:
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()


async def publish_runtime(cache: Redis, result: dict[str, JsonValue]) -> SumoRuntimeRecord:
    record = SumoRuntimeRecord.model_validate(
        {key: result[key] for key in ("verified", "version", "checked_at", "architecture")}
    )
    await cache.set(SUMO_RUNTIME_KEY, record.model_dump_json(), ex=SUMO_RUNTIME_TTL_SECONDS)
    return record


async def publish_unavailable_runtime(cache: Redis) -> None:
    record = SumoRuntimeRecord(
        verified=False,
        version="unavailable",
        checked_at=datetime.now(UTC),
        architecture=platform.machine(),
    )
    await cache.set(SUMO_RUNTIME_KEY, record.model_dump_json(), ex=SUMO_RUNTIME_TTL_SECONDS)


async def verify_and_publish_runtime(
    cache: Redis, lock: asyncio.Lock, budget_seconds: float
) -> None:
    try:
        async with asyncio.timeout(budget_seconds):
            async with lock:
                result = await execute_sumo(budget_seconds)
        await publish_runtime(cache, result)
        logger.info("SUMO synthetic runtime verified")
    except (RuntimeError, OSError, ValueError, TimeoutError):
        logger.warning("SUMO runtime unavailable", exc_info=True)
        await publish_unavailable_runtime(cache)


async def process_job(cache: Redis, job_id: str, lock: asyncio.Lock, budget_seconds: float) -> None:
    try:
        identifier = str(UUID(job_id))
    except ValueError:
        logger.warning("Discarding an invalid diagnostic queue identifier")
        return
    key = f"{DIAGNOSTIC_JOB_PREFIX}{identifier}"
    encoded = await cache.get(key)
    if encoded is None:
        return
    try:
        job = DiagnosticJob.model_validate_json(encoded)
    except ValidationError:
        logger.warning("Discarding a diagnostic record with an invalid contract")
        return
    if str(job.job_id) != identifier or job.status != "queued":
        return
    job = job.model_copy(update={"status": "running", "updated_at": datetime.now(UTC)})
    await cache.set(key, job.model_dump_json(), ex=DIAGNOSTIC_JOB_TTL_SECONDS)
    try:
        if job.kind == "diagnostic":
            result: dict[str, JsonValue] = {
                "kind": "diagnostic",
                "worker_pid": os.getpid(),
                "architecture": platform.machine(),
                "message": "Worker consumed this diagnostic from the Redis queue.",
            }
        else:
            if lock.locked():
                raise NativeEngineBusy
            async with asyncio.timeout(budget_seconds):
                async with lock:
                    result = await execute_sumo(budget_seconds)
            result["worker_pid"] = os.getpid()
            await publish_runtime(cache, result)
        job = job.model_copy(
            update={
                "status": "succeeded",
                "updated_at": datetime.now(UTC),
                "result": result,
                "error": None,
            }
        )
    except NativeEngineBusy:
        job = job.model_copy(
            update={
                "status": "failed",
                "updated_at": datetime.now(UTC),
                "result": None,
                "error": (
                    "The native engine is busy with a simulation. "
                    "Retry this diagnostic after that run finishes."
                ),
            }
        )
    except (RuntimeError, OSError, ValueError, TimeoutError):
        logger.warning("Diagnostic execution failed for %s", identifier, exc_info=True)
        if job.kind == "sumo_runtime":
            await publish_unavailable_runtime(cache)
        job = job.model_copy(
            update={
                "status": "failed",
                "updated_at": datetime.now(UTC),
                "result": None,
                "error": "The worker could not complete this bounded diagnostic.",
            }
        )
    await cache.set(key, job.model_dump_json(), ex=DIAGNOSTIC_JOB_TTL_SECONDS)


async def consume(
    cache: Redis, stop: asyncio.Event, lock: asyncio.Lock, budget_seconds: float
) -> None:
    failures = 0
    while not stop.is_set():
        try:
            pending = cast(
                Awaitable[tuple[str, str] | None], cache.blpop([DIAGNOSTIC_QUEUE_KEY], timeout=1)
            )
            item = await pending
            failures = 0
            if item is not None:
                await process_job(cache, str(item[1]), lock, budget_seconds)
        except (RedisConnectionError, RedisTimeoutError, OSError):
            failures += 1
            if failures >= MAX_REDIS_FAILURES:
                raise RuntimeError("Redis queue failed five consecutive attempts") from None
            logger.warning("Redis queue unavailable; retry %d/%d", failures, MAX_REDIS_FAILURES)
            try:
                await asyncio.wait_for(stop.wait(), min(2 ** (failures - 1), 5))
            except TimeoutError:
                pass
