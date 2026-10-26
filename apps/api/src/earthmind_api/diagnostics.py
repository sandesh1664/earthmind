"""Bounded Redis diagnostic queue. Models and constants live in contracts."""

import asyncio
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from earthmind_contracts import (
    DIAGNOSTIC_JOB_PREFIX,
    DIAGNOSTIC_JOB_TTL_SECONDS,
    DIAGNOSTIC_QUEUE_KEY,
    DIAGNOSTIC_QUEUE_LIMIT,
    SUMO_RUNTIME_KEY,
    SUMO_RUNTIME_TTL_SECONDS,
    DiagnosticJob,
    DiagnosticKind,
    SumoRuntimeRecord,
)
from pydantic import ValidationError
from redis.asyncio import Redis

# One Redis operation reserves queue space and persists the job before publication.
ENQUEUE_SCRIPT = """
if redis.call('LLEN', KEYS[1]) >= tonumber(ARGV[1]) then return 0 end
redis.call('SET', KEYS[2], ARGV[2], 'EX', ARGV[3])
redis.call('RPUSH', KEYS[1], ARGV[4])
return 1
"""


class QueueFullError(Exception):
    pass


class DiagnosticsStore:
    def __init__(self, cache: Redis, timeout_seconds: float) -> None:
        self.cache = cache
        self.timeout_seconds = timeout_seconds

    async def enqueue(self, kind: DiagnosticKind) -> DiagnosticJob:
        now = datetime.now(UTC)
        job = DiagnosticJob(
            job_id=uuid4(), kind=kind, status="queued", created_at=now, updated_at=now
        )
        async with asyncio.timeout(self.timeout_seconds):
            accepted = await cast(
                Awaitable[int],
                self.cache.eval(
                    ENQUEUE_SCRIPT,
                    2,
                    DIAGNOSTIC_QUEUE_KEY,
                    f"{DIAGNOSTIC_JOB_PREFIX}{job.job_id}",
                    str(DIAGNOSTIC_QUEUE_LIMIT),
                    job.model_dump_json(),
                    str(DIAGNOSTIC_JOB_TTL_SECONDS),
                    str(job.job_id),
                ),
            )
        if accepted != 1:
            raise QueueFullError("Diagnostic queue is full")
        return job

    async def get(self, job_id: UUID) -> DiagnosticJob | None:
        async with asyncio.timeout(self.timeout_seconds):
            value = await self.cache.get(f"{DIAGNOSTIC_JOB_PREFIX}{job_id}")
        return None if value is None else DiagnosticJob.model_validate_json(value)

    async def runtime(self) -> SumoRuntimeRecord | None:
        async with asyncio.timeout(self.timeout_seconds):
            value = await self.cache.get(SUMO_RUNTIME_KEY)
            ttl = await self.cache.ttl(SUMO_RUNTIME_KEY)
        if value is None or ttl <= 0:
            return None
        try:
            record = SumoRuntimeRecord.model_validate_json(value)
        except ValidationError:
            return None
        age = (datetime.now(UTC) - record.checked_at).total_seconds()
        return record if record.verified and 0 <= age <= SUMO_RUNTIME_TTL_SECONDS else None
