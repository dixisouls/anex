"""Local Queue: fire-and-forget HTTP dispatch to agent services."""

import asyncio
import logging
import uuid

import httpx

from backend.infra.db import session_scope
from backend.infra.redis_client import get_redis
from backend.ports.queue import RunDispatch

logger = logging.getLogger(__name__)


class LocalQueue:
    async def enqueue_run(self, dispatch: RunDispatch) -> str:
        dispatch_id = f"local-{uuid.uuid4().hex[:12]}"
        asyncio.create_task(self._run(dispatch))
        return dispatch_id

    async def enqueue_run_and_wait(self, dispatch: RunDispatch) -> str | None:
        return await self._run(dispatch)

    async def _run(self, dispatch: RunDispatch) -> str | None:
        from backend.market import broker

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{dispatch.service_url}/run",
                    json={
                        "subtask_text": dispatch.subtask_text,
                        "config": dispatch.config,
                    },
                )
                resp.raise_for_status()
                output = resp.json()["output"]
            async with session_scope() as session:
                await broker.handle_run_result(
                    get_redis(),
                    session,
                    subtask_id=dispatch.subtask_id,
                    agent_id=dispatch.agent_id,
                    output=output,
                    task_id=dispatch.task_id,
                )
            return output
        except Exception:
            logger.exception(
                "local queue dispatch failed subtask=%s agent=%s",
                dispatch.subtask_id,
                dispatch.agent_id,
            )
            return None
