"""Global cap on concurrent broker task pipelines."""

from __future__ import annotations

import asyncio

from backend.config import MAX_CONCURRENT_TASKS

_sem: asyncio.Semaphore | None = None


def get_task_semaphore() -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    return _sem


def reset_task_semaphore() -> None:
    """Test helper: rebuild semaphore after MAX_CONCURRENT_TASKS override."""
    global _sem
    _sem = None


def task_slots_status() -> dict[str, int]:
    sem = get_task_semaphore()
    available = sem._value
    return {
        "max": MAX_CONCURRENT_TASKS,
        "available": available,
        "in_use": MAX_CONCURRENT_TASKS - available,
    }
