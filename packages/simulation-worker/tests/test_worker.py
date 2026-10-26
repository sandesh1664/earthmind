from datetime import datetime
from unittest.mock import AsyncMock

from earthmind_contracts import (
    SUMO_RUNTIME_KEY,
    WORKER_HEARTBEAT_KEY,
    WORKER_HEARTBEAT_TTL_SECONDS,
)
from earthmind_worker.runtime import heartbeat


async def test_heartbeat_expires_so_stopped_workers_are_detected() -> None:
    cache = AsyncMock()
    await heartbeat(cache)
    cache.set.assert_awaited_once()
    args, kwargs = cache.set.call_args
    assert args[0] == WORKER_HEARTBEAT_KEY
    assert datetime.fromisoformat(args[1]).tzinfo is not None
    assert kwargs == {"ex": WORKER_HEARTBEAT_TTL_SECONDS}


async def test_shutdown_closes_redis_even_if_heartbeat_cleanup_fails(monkeypatch) -> None:
    import asyncio

    from earthmind_worker import runtime

    stop = asyncio.Event()
    stop.set()
    cache = AsyncMock()
    cache.delete.side_effect = ConnectionError("Redis unavailable during shutdown")
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, "add_signal_handler", lambda *args: None)
    monkeypatch.setattr(runtime.asyncio, "Event", lambda: stop)
    monkeypatch.setattr(runtime.Redis, "from_url", lambda *args, **kwargs: cache)
    await runtime.run()
    cache.delete.assert_awaited_once_with(WORKER_HEARTBEAT_KEY, SUMO_RUNTIME_KEY)
    cache.aclose.assert_awaited_once()


async def test_shutdown_cancels_a_native_check_during_startup(monkeypatch) -> None:
    import asyncio

    from earthmind_worker import runtime

    started = asyncio.Event()
    cancelled = asyncio.Event()
    stop = asyncio.Event()

    async def verify(*_args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(runtime, "verify_and_publish_runtime", verify)
    task = asyncio.create_task(runtime.startup_check(AsyncMock(), stop, asyncio.Lock(), 5))
    await started.wait()
    stop.set()
    assert await task is False
    assert cancelled.is_set()
