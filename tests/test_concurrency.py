"""
Concurrency cap and retry helpers (offline).

    EMBEDDINGS_FAKE=1 WEAVE_DISABLED=1 pytest tests/test_concurrency.py -v
"""

import asyncio
from unittest.mock import patch

import httpx
import pytest
import redis.asyncio as redis

from backend.api import task_pool
from backend.config import MAX_CONCURRENT_TASKS
from backend.infra import retry as retry_mod
from backend.sim import runner as sim_runner


@pytest.fixture(autouse=True)
def reset_semaphore():
    task_pool.reset_task_semaphore()
    yield
    task_pool.reset_task_semaphore()


def test_task_slots_status_initial():
    status = task_pool.task_slots_status()
    assert status["max"] == MAX_CONCURRENT_TASKS
    assert status["available"] == MAX_CONCURRENT_TASKS
    assert status["in_use"] == 0


@pytest.mark.asyncio
async def test_task_semaphore_limits_concurrency():
    sem = task_pool.get_task_semaphore()
    entered = 0
    max_seen = 0
    lock = asyncio.Lock()

    async def worker():
        nonlocal entered, max_seen
        async with sem:
            async with lock:
                entered += 1
                max_seen = max(max_seen, entered)
            await asyncio.sleep(0.05)
            async with lock:
                entered -= 1

    await asyncio.gather(*(worker() for _ in range(MAX_CONCURRENT_TASKS * 3)))
    assert max_seen <= MAX_CONCURRENT_TASKS


@pytest.mark.asyncio
async def test_redis_retry_succeeds_after_timeout():
    calls = 0

    async def flaky():
        nonlocal calls
        calls += 1
        if calls < 2:
            raise redis.TimeoutError("simulated")
        return "ok"

    result = await retry_mod.with_redis_retry(flaky, attempts=3, base_delay=0.01)
    assert result == "ok"
    assert calls == 2


@pytest.mark.asyncio
async def test_httpx_retry_succeeds_after_read_error():
    calls = 0

    async def flaky():
        nonlocal calls
        calls += 1
        if calls < 2:
            raise httpx.ReadError("simulated")
        return "ok"

    result = await retry_mod.httpx_request_with_retry(flaky, attempts=3, base_delay=0.01)
    assert result == "ok"
    assert calls == 2


@pytest.mark.asyncio
async def test_wait_for_task_slot_polls_until_available(monkeypatch):
    responses = [{"available": 0}, {"available": 1}]
    sleeps: list[float] = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeClient:
        async def get(self, path):
            assert path == "/task/slots"
            return FakeResponse(responses.pop(0))

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(sim_runner.asyncio, "sleep", fake_sleep)
    await sim_runner._wait_for_task_slot(FakeClient(), poll_s=0.5)
    assert sleeps == [0.5]


@pytest.mark.asyncio
async def test_run_task_holds_semaphore_while_running():
    """Concurrent pipelines cannot exceed MAX_CONCURRENT_TASKS."""
    sem = task_pool.get_task_semaphore()
    active = 0
    peak = 0
    lock = asyncio.Lock()

    async def pipeline():
        nonlocal active, peak
        async with sem:
            async with lock:
                active += 1
                peak = max(peak, active)
            await asyncio.sleep(0.03)
            async with lock:
                active -= 1

    await asyncio.gather(*(pipeline() for _ in range(MAX_CONCURRENT_TASKS + 2)))
    assert peak <= MAX_CONCURRENT_TASKS
