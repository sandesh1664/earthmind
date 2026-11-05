import asyncio
import json
import signal
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from earthmind_contracts import (
    DIAGNOSTIC_JOB_PREFIX,
    DIAGNOSTIC_JOB_TTL_SECONDS,
    SUMO_RUNTIME_KEY,
    SUMO_RUNTIME_TTL_SECONDS,
    DiagnosticJob,
    SumoRuntimeRecord,
)
from earthmind_worker import jobs
from redis.exceptions import ConnectionError as RedisConnectionError


def queued(kind="diagnostic"):
    now = datetime.now(UTC)
    return DiagnosticJob(job_id=uuid4(), kind=kind, status="queued", created_at=now, updated_at=now)


async def test_diagnostic_is_consumed_and_completed_by_worker() -> None:
    job = queued()
    cache = AsyncMock()
    cache.get.return_value = job.model_dump_json()
    await jobs.process_job(cache, str(job.job_id), asyncio.Lock(), 5)
    running = DiagnosticJob.model_validate_json(cache.set.call_args_list[0].args[1])
    completed = DiagnosticJob.model_validate_json(cache.set.call_args_list[1].args[1])
    assert running.status == "running"
    assert completed.status == "succeeded"
    assert completed.created_at == job.created_at
    assert completed.result["kind"] == "diagnostic"
    assert completed.result["worker_pid"] > 0
    assert cache.set.call_args_list[1].args[0] == f"{DIAGNOSTIC_JOB_PREFIX}{job.job_id}"
    assert cache.set.call_args_list[1].kwargs == {"ex": DIAGNOSTIC_JOB_TTL_SECONDS}


async def test_expired_job_is_not_resurrected() -> None:
    cache = AsyncMock()
    cache.get.return_value = None
    await jobs.process_job(cache, str(uuid4()), asyncio.Lock(), 5)
    cache.set.assert_not_awaited()


async def test_invalid_kind_never_executes_any_command(monkeypatch) -> None:
    job = queued()
    encoded = job.model_dump(mode="json")
    encoded["kind"] = "shell_command"
    cache = AsyncMock()
    cache.get.return_value = json.dumps(encoded)
    execute = AsyncMock()
    monkeypatch.setattr(jobs, "execute_sumo", execute)
    await jobs.process_job(cache, str(job.job_id), asyncio.Lock(), 5)
    execute.assert_not_awaited()
    cache.set.assert_not_awaited()


async def test_failed_native_probe_records_failed_job_without_claiming_success(monkeypatch) -> None:
    job = queued("sumo_runtime")
    cache = AsyncMock()
    cache.get.return_value = job.model_dump_json()
    monkeypatch.setattr(jobs, "execute_sumo", AsyncMock(side_effect=TimeoutError("deadline")))
    await jobs.process_job(cache, str(job.job_id), asyncio.Lock(), 5)
    completed = DiagnosticJob.model_validate_json(cache.set.call_args_list[-1].args[1])
    assert completed.status == "failed"
    assert completed.result is None
    assert completed.error
    runtime_update = next(
        call for call in cache.set.call_args_list if call.args[0] == SUMO_RUNTIME_KEY
    )
    assert SumoRuntimeRecord.model_validate_json(runtime_update.args[1]).verified is False


async def test_runtime_failure_publishes_unavailable_record(monkeypatch) -> None:
    cache = AsyncMock()
    monkeypatch.setattr(jobs, "execute_sumo", AsyncMock(side_effect=RuntimeError("missing binary")))
    await jobs.verify_and_publish_runtime(cache, asyncio.Lock(), 5)
    cache.set.assert_awaited_once()
    assert cache.set.call_args.args[0] == SUMO_RUNTIME_KEY
    record = SumoRuntimeRecord.model_validate_json(cache.set.call_args.args[1])
    assert record.verified is False
    assert cache.set.call_args.kwargs == {"ex": SUMO_RUNTIME_TTL_SECONDS}


async def test_job_deadline_includes_waiting_for_the_native_runtime_lock(monkeypatch) -> None:
    job = queued("sumo_runtime")
    cache = AsyncMock()
    cache.get.return_value = job.model_dump_json()
    lock = asyncio.Lock()
    await lock.acquire()
    execute = AsyncMock()
    monkeypatch.setattr(jobs, "execute_sumo", execute)
    try:
        await asyncio.wait_for(jobs.process_job(cache, str(job.job_id), lock, 0.01), 1)
    finally:
        lock.release()
    completed = DiagnosticJob.model_validate_json(cache.set.call_args_list[-1].args[1])
    assert completed.status == "failed"
    execute.assert_not_awaited()


async def test_native_timeout_kills_the_entire_probe_process_group(monkeypatch) -> None:
    process = AsyncMock()
    process.pid = 4321
    process.returncode = None

    async def communicate():
        await asyncio.Event().wait()

    process.communicate.side_effect = communicate
    monkeypatch.setattr(jobs.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    kills = []
    monkeypatch.setattr(jobs.os, "killpg", lambda pid, sig: kills.append((pid, sig)))
    with pytest.raises(TimeoutError):
        await jobs.execute_sumo(0.01)
    assert kills == [(4321, signal.SIGKILL)]
    process.wait.assert_awaited_once()


async def test_redis_queue_failure_retries_are_bounded(monkeypatch) -> None:
    cache = AsyncMock()
    cache.blpop.side_effect = RedisConnectionError("offline")

    async def no_wait(awaitable, _timeout):
        awaitable.close()
        raise TimeoutError

    monkeypatch.setattr(jobs.asyncio, "wait_for", no_wait)
    with pytest.raises(RuntimeError, match="five consecutive attempts"):
        await jobs.consume(cache, asyncio.Event(), asyncio.Lock(), 5)
    assert cache.blpop.await_count == jobs.MAX_REDIS_FAILURES


async def test_busy_native_slot_is_not_misreported_as_an_unavailable_engine(monkeypatch) -> None:
    job = queued("sumo_runtime")
    cache = AsyncMock()
    cache.get.return_value = job.model_dump_json()
    execute = AsyncMock()
    monkeypatch.setattr(jobs, "execute_sumo", execute)
    lock = asyncio.Lock()
    async with lock:
        await jobs.process_job(cache, str(job.job_id), lock, 5)
    completed = DiagnosticJob.model_validate_json(cache.set.call_args_list[-1].args[1])
    assert completed.status == "failed"
    assert "busy" in completed.error
    execute.assert_not_awaited()
    assert all(call.args[0] != SUMO_RUNTIME_KEY for call in cache.set.call_args_list)
