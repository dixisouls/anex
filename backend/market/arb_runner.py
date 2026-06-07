"""Background mean-reversion / noise kernel across all listed models."""

from __future__ import annotations

import asyncio
import logging
import random

from backend.config import ARB_ENABLED, ARB_INTERVAL_S
from backend.db import repo
from backend.infra.db import session_scope
from backend.infra.redis_client import get_redis
from backend.market import exchange

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None


async def _arb_loop() -> None:
    rng = random.Random()
    while True:
        try:
            r = get_redis()
            async with session_scope() as session:
                models = await repo.list_models(session)
                for m in models:
                    try:
                        await exchange.inject_arb(
                            session,
                            r,
                            model_id=m.model_id,
                            dt=ARB_INTERVAL_S,
                            rng=rng,
                        )
                    except Exception:
                        logger.exception("arb tick failed model=%s", m.model_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("arb loop error")
        await asyncio.sleep(ARB_INTERVAL_S)


async def start() -> None:
    global _task
    if not ARB_ENABLED:
        return
    await stop()
    _task = asyncio.create_task(_arb_loop())
    logger.info("arb kernel started interval_s=%s", ARB_INTERVAL_S)


async def stop() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
