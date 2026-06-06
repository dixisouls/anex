"""Small retry helpers for transient Redis and HTTP failures."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx
import redis.asyncio as redis

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def with_redis_retry(
    coro_factory: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.1,
) -> T:
    last: redis.TimeoutError | None = None
    for attempt in range(attempts):
        try:
            return await coro_factory()
        except redis.TimeoutError as exc:
            last = exc
            if attempt >= attempts - 1:
                raise
            delay = base_delay * (2**attempt)
            logger.warning(
                "redis timeout (attempt %s/%s), retry in %.2fs",
                attempt + 1,
                attempts,
                delay,
            )
            await asyncio.sleep(delay)
    raise last  # pragma: no cover


async def httpx_request_with_retry(
    request: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.25,
) -> T:
    last: httpx.HTTPError | None = None
    for attempt in range(attempts):
        try:
            return await request()
        except (httpx.ReadError, httpx.ConnectError) as exc:
            last = exc
            if attempt >= attempts - 1:
                raise
            delay = base_delay * (2**attempt)
            logger.warning(
                "httpx transient error (attempt %s/%s), retry in %.2fs",
                attempt + 1,
                attempts,
                delay,
            )
            await asyncio.sleep(delay)
    raise last  # pragma: no cover
