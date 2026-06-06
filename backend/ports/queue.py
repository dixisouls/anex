"""Queue port: hire dispatch (local HTTP or Cloud Tasks in cloud)."""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class RunDispatch:
    subtask_id: str
    agent_id: str
    service_url: str
    subtask_text: str
    config: dict
    task_id: str


class Queue(Protocol):
    async def enqueue_run(self, dispatch: RunDispatch) -> str: ...

    async def enqueue_run_and_wait(self, dispatch: RunDispatch) -> str | None: ...
