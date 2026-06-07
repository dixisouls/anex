"""
Cross-session subtask persistence (broker commit + save result).

    WEAVE_DISABLED=1 pytest tests/0009_subtask_persistence.py -v
"""

import uuid

import pytest

from backend.db import repo
from backend.infra.db import session_scope


@pytest.mark.asyncio
async def test_subtask_pipeline_persists_across_sessions():
    """local_queue uses a separate session; subtasks must be committed first."""
    task_id = uuid.uuid4()
    agent_id: str | None = None

    async with session_scope() as session:
        agents = await repo.list_agents(session)
        if not agents:
            pytest.skip("no agents in DB — run seeder first")
        agent_id = agents[0].agent_id
        task = await repo.create_task(session, goal="persist me")
        task_id = task.id
        await repo.create_subtask(
            session, task_id=task_id, order_index=0, text="step one"
        )
        await session.commit()

    subtask_id = repo.subtask_public_id(task_id, 0)
    candidates = [
        {
            "agent_id": agent_id,
            "match_score": 0.9,
            "reputation": 0.5,
            "price": 10.0,
            "final_score": 0.8,
        }
    ]

    async with session_scope() as session:
        await repo.update_subtask(
            session,
            subtask_id,
            candidates_json=candidates,
            assigned_agent_id=agent_id,
            hire_price=10.0,
            budget_remaining=90.0,
        )

    async with session_scope() as session:
        await repo.save_subtask_result(
            session,
            subtask_id=subtask_id,
            agent_id=agent_id,
            output_preview="hello world",
            judge_score=0.85,
        )

    async with session_scope() as session:
        st = await repo.get_subtask(session, subtask_id)
        assert st is not None
        assert st.candidates_json == candidates
        assert st.assigned_agent_id == agent_id
        assert float(st.hire_price) == pytest.approx(10.0)
        assert st.output_preview == "hello world"
        assert float(st.judge_score) == pytest.approx(0.85)
        assert repo.derive_subtask_stage(st) == "scored"
