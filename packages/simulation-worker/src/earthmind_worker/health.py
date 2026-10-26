"""Container health probe; succeeds only while the worker heartbeat has a TTL."""

import asyncio

from earthmind_contracts import WORKER_HEARTBEAT_KEY
from redis.asyncio import Redis

from earthmind_worker.settings import Settings


async def check() -> None:
    cache: Redis = Redis.from_url(
        Settings().redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        if await cache.ttl(WORKER_HEARTBEAT_KEY) <= 0:
            raise SystemExit("Worker heartbeat absent or expired")
    finally:
        await cache.aclose()


if __name__ == "__main__":
    asyncio.run(check())
