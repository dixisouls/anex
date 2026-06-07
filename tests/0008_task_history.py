"""
Offline tests for task history repo helpers and feed backlog.

    WEAVE_DISABLED=1 pytest tests/0008_task_history.py -v
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.db import repo
from backend.db.models import Subtask, Task
from backend.market import feed


def _subtask(**kwargs) -> Subtask:
    defaults = {
        "id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "order_index": 0,
        "text": "do something",
        "assigned_agent_id": None,
        "output_preview": None,
        "judge_score": None,
    }
    defaults.update(kwargs)
    return Subtask(**defaults)


def test_derive_subtask_stage_progression():
    assert repo.derive_subtask_stage(_subtask()) == "posted"
    assert (
        repo.derive_subtask_stage(_subtask(assigned_agent_id="writer-01")) == "hired"
    )
    assert (
        repo.derive_subtask_stage(
            _subtask(assigned_agent_id="writer-01", output_preview="done")
        )
        == "executed"
    )
    assert (
        repo.derive_subtask_stage(
            _subtask(
                assigned_agent_id="writer-01",
                output_preview="done",
                judge_score=Decimal("0.91"),
            )
        )
        == "scored"
    )


def test_subtask_public_id():
    tid = uuid.UUID("00000000-0000-0000-0000-000000000001")
    assert repo.subtask_public_id(tid, 2) == "00000000-0000-0000-0000-000000000001-2"


def test_task_to_detail_shape():
    from backend.api.app import _task_to_detail

    tid = uuid.uuid4()
    task = Task(
        id=tid,
        goal="write copy",
        status="running",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        subtasks=[
            Subtask(
                id=uuid.uuid4(),
                task_id=tid,
                order_index=0,
                text="draft",
                assigned_agent_id="writer-01",
                output_preview="hello",
                judge_score=Decimal("0.8"),
            )
        ],
    )
    detail = _task_to_detail(task)
    assert detail.task_id == str(tid)
    assert detail.goal == "write copy"
    assert detail.status == "running"
    assert len(detail.subtasks) == 1
    assert detail.subtasks[0].subtask_id == f"{tid}-0"
    assert detail.subtasks[0].stage == "scored"


@pytest.mark.asyncio
async def test_read_recent_returns_oldest_first():
    r = AsyncMock()
    payload = b'{"event_id":"e1","ts":"2026-01-01T00:00:00Z","type":"task_posted","task_id":"t1","goal":"g","subtasks":[]}'
    r.xrevrange.return_value = [
        (b"2-0", {b"data": payload}),
        (b"1-0", {b"data": payload}),
    ]
    out = await feed.read_recent(r, count=2)
    assert [eid for eid, _ in out] == ["1-0", "2-0"]
    assert len(out) == 2


@pytest.mark.asyncio
async def test_hide_task_for_user_sets_hidden_at():
    user_id = uuid.uuid4()
    task_id = uuid.uuid4()
    task = Task(id=task_id, goal="hide me", user_id=user_id, status="complete")

    class _Result:
        def scalar_one_or_none(self):
            return task

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result())

    ok = await repo.hide_task_for_user(session, user_id, task_id)
    assert ok is True
    assert task.hidden_at is not None
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_hide_task_for_user_missing_returns_false():
    class _Result:
        def scalar_one_or_none(self):
            return None

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result())

    ok = await repo.hide_task_for_user(session, uuid.uuid4(), uuid.uuid4())
    assert ok is False


@pytest.mark.asyncio
async def test_list_tasks_for_user_orders_and_loads_subtasks():
    user_id = uuid.uuid4()
    task_a = Task(id=uuid.uuid4(), goal="a", user_id=user_id, status="running")
    task_b = Task(id=uuid.uuid4(), goal="b", user_id=user_id, status="complete")

    class _Scalars:
        def unique(self):
            return self

        def all(self):
            return [task_b, task_a]

    class _Result:
        def scalars(self):
            return _Scalars()

    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result())

    tasks = await repo.list_tasks_for_user(session, user_id, limit=10)
    assert tasks == [task_b, task_a]
    session.execute.assert_awaited_once()
