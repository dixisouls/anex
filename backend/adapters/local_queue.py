"""Local Queue: A2A task dispatch to agent services."""

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
            task_payload = {
                "id": dispatch.subtask_id,
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": dispatch.subtask_text}],
                },
                "metadata": {"config": dispatch.config},
            }
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{dispatch.service_url}/tasks/send",
                    json=task_payload,
                )
                resp.raise_for_status()
                data = resp.json()

            # extract output from first artifact
            artifacts = data.get("artifacts") or []
            output = None
            if artifacts:
                parts = artifacts[0].get("parts") or []
                output = next(
                    (p["text"] for p in parts if p.get("type") == "text"), None
                )

            if output:
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
