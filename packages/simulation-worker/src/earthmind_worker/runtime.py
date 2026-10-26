import asyncio
import logging
import signal
from datetime import UTC, datetime

from earthmind_contracts import (
    SUMO_RUNTIME_KEY,
    WORKER_HEARTBEAT_KEY,
    WORKER_HEARTBEAT_TTL_SECONDS,
)
from redis.asyncio import Redis

from earthmind_worker.jobs import MAX_REDIS_FAILURES, consume, verify_and_publish_runtime
from earthmind_worker.settings import Settings

logger = logging.getLogger(__name__)


async def heartbeat(cache: Redis) -> None:
    await cache.set(
        WORKER_HEARTBEAT_KEY,
        datetime.now(UTC).isoformat(),
        ex=WORKER_HEARTBEAT_TTL_SECONDS,
    )


async def pulse(cache: Redis, stop: asyncio.Event, interval: float) -> None:
    failures = 0
    while not stop.is_set():
        try:
            await heartbeat(cache)
            failures = 0
        except Exception:
            failures += 1
            logger.warning("Worker heartbeat failed (%d/%d)", failures, MAX_REDIS_FAILURES)
            if failures >= MAX_REDIS_FAILURES:
                raise RuntimeError("Worker heartbeat failed five consecutive attempts") from None
        try:
            await asyncio.wait_for(stop.wait(), interval)
        except TimeoutError:
            pass


async def runtime_checks(
    cache: Redis, stop: asyncio.Event, lock: asyncio.Lock, configuration: Settings
) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), configuration.worker_runtime_check_interval_seconds)
        except TimeoutError:
            await verify_and_publish_runtime(cache, lock, configuration.worker_job_timeout_seconds)


class StopWorker(Exception):
    """Internal structured-concurrency signal for graceful process termination."""


async def wait_for_stop(stop: asyncio.Event) -> None:
    await stop.wait()
    raise StopWorker


async def startup_check(
    cache: Redis, stop: asyncio.Event, lock: asyncio.Lock, budget_seconds: float
) -> bool:
    verifier = asyncio.create_task(verify_and_publish_runtime(cache, lock, budget_seconds))
    stopper = asyncio.create_task(stop.wait())
    try:
        completed, _ = await asyncio.wait((verifier, stopper), return_when=asyncio.FIRST_COMPLETED)
        if verifier in completed:
            await verifier
            return not stop.is_set()
        return False
    finally:
        for task in (verifier, stopper):
            if not task.done():
                task.cancel()
        await asyncio.gather(verifier, stopper, return_exceptions=True)


async def run(settings: Settings | None = None) -> None:
    configuration = settings or Settings()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    cache: Redis = Redis.from_url(
        configuration.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    logger.info("Simulation worker started (bounded M01 diagnostics)")
    lock = asyncio.Lock()
    try:
        if stop.is_set():
            return
        if not await startup_check(cache, stop, lock, configuration.worker_job_timeout_seconds):
            return
        try:
            async with asyncio.TaskGroup() as tasks:
                tasks.create_task(
                    pulse(cache, stop, configuration.worker_heartbeat_interval_seconds)
                )
                tasks.create_task(
                    consume(cache, stop, lock, configuration.worker_job_timeout_seconds)
                )
                tasks.create_task(runtime_checks(cache, stop, lock, configuration))
                tasks.create_task(wait_for_stop(stop))
        except* StopWorker:
            pass
    finally:
        try:
            await cache.delete(WORKER_HEARTBEAT_KEY, SUMO_RUNTIME_KEY)
        except Exception:
            logger.warning("Worker marker cleanup failed; records will expire", exc_info=True)
        finally:
            await cache.aclose()
        logger.info("Simulation worker stopped")
