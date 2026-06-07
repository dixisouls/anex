"""
Offline broker rank tests (no GCP, no live agents).

    EMBEDDINGS_FAKE=1 WEAVE_DISABLED=1 pytest tests/0003_agent_loop.py -v
"""

from unittest.mock import AsyncMock, patch

import pytest

from contracts.schemas import Agent, Candidate
from backend.config import PLACEHOLDER_MODEL_PRICE, W_MATCH, W_PRICE, W_REP
from backend.market import broker, pricing


@pytest.fixture
def mock_agent():
    return Agent(
        agent_id="writer-01",
        name="Copywriter",
        skills=["writing"],
        capability_text="writes copy",
        model="gemini-3.5-flash",
        margin=0.20,
        reputation=0.5,
        service_url="http://localhost:9001",
    )


@pytest.mark.asyncio
async def test_rank_final_score_formula(mock_agent):
    r = AsyncMock()
    match = 0.8

    with (
        patch.object(broker.registry, "search", new_callable=AsyncMock) as mock_search,
        patch.object(
            broker.registry, "get_agent_cached", new_callable=AsyncMock
        ) as mock_get,
        patch.object(broker.pricing, "model_price", new_callable=AsyncMock) as mock_mp,
    ):
        mock_search.return_value = [("writer-01", match)]
        mock_get.return_value = mock_agent
        mock_mp.return_value = PLACEHOLDER_MODEL_PRICE

        cands = await broker.rank(r, "write a blog post", k=1)

    assert len(cands) == 1
    c = cands[0]
    expected_price = pricing.derived_price(PLACEHOLDER_MODEL_PRICE, mock_agent.margin)
    expected_final = (
        W_MATCH * match + W_REP * mock_agent.reputation - W_PRICE * expected_price
    )
    assert c.price == pytest.approx(expected_price)
    assert c.final_score == pytest.approx(expected_final)


@pytest.mark.asyncio
async def test_rank_sorts_descending():
    r = AsyncMock()
    agents = {
        "a": Agent(
            agent_id="a",
            name="A",
            skills=[],
            capability_text="a",
            model="m1",
            margin=0.1,
            reputation=0.5,
        ),
        "b": Agent(
            agent_id="b",
            name="B",
            skills=[],
            capability_text="b",
            model="m1",
            margin=0.5,
            reputation=0.9,
        ),
    }

    with (
        patch.object(broker.registry, "search", new_callable=AsyncMock) as mock_search,
        patch.object(
            broker.registry, "get_agent_cached", new_callable=AsyncMock
        ) as mock_get,
        patch.object(broker.pricing, "model_price", new_callable=AsyncMock) as mock_mp,
    ):
        mock_search.return_value = [("a", 0.9), ("b", 0.7)]
        mock_get.side_effect = lambda _r, aid: agents[aid]
        mock_mp.return_value = PLACEHOLDER_MODEL_PRICE

        cands = await broker.rank(r, "task", k=2)

    assert len(cands) == 2
    assert cands[0].final_score >= cands[1].final_score


def test_decompose_fallback_on_bad_json(monkeypatch):
    monkeypatch.setattr(
        "backend.market.broker.generate", lambda *a, **k: {"output": "not json"}
    )
    assert broker.decompose("single goal") == ["single goal"]


def test_build_subtask_prompt_first_step():
    prompt = broker._build_subtask_prompt(
        "Translate 'Hello world' to French", "Translate to French", []
    )
    assert "ORIGINAL GOAL: Translate 'Hello world' to French" in prompt
    assert "CURRENT TASK: Translate to French" in prompt
    assert "PRIOR RESULTS" not in prompt


def test_build_subtask_prompt_with_prior():
    prior = [("Translate to French", "Bonjour le monde")]
    prompt = broker._build_subtask_prompt(
        "Translate 'Hello world' to French",
        "Polish the translation",
        prior,
    )
    assert "PRIOR RESULTS:" in prompt
    assert "- Step 0 (Translate to French): Bonjour le monde" in prompt
    assert "CURRENT TASK: Polish the translation" in prompt


@pytest.mark.asyncio
async def test_run_task_dispatches_sequentially(mock_agent):
    r = AsyncMock()
    session = AsyncMock()
    dispatch_order: list[str] = []

    async def fake_wait(dispatch):
        dispatch_order.append(dispatch.subtask_id)
        return f"output-{dispatch.subtask_id}"

    subtask_texts = ["step one", "step two"]
    with (
        patch.object(broker, "decompose", return_value=subtask_texts),
        patch.object(broker, "rank", new_callable=AsyncMock) as mock_rank,
        patch.object(
            broker.registry, "get_agent_cached", new_callable=AsyncMock
        ) as mock_get_agent,
        patch.object(
            broker.registry, "get_model_cached", new_callable=AsyncMock
        ) as mock_get_model,
        patch.object(broker.repo, "create_subtask", new_callable=AsyncMock),
        patch.object(broker.bus, "publish", new_callable=AsyncMock),
        patch("backend.market.broker.get_queue") as mock_get_queue,
    ):
        mock_rank.return_value = [
            Candidate(
                agent_id="writer-01",
                match_score=0.9,
                reputation=0.5,
                price=1.0,
                final_score=1.0,
            )
        ]
        mock_get_agent.return_value = mock_agent
        mock_get_model.return_value = {"provider": "gcp"}
        mock_queue = AsyncMock()
        mock_queue.enqueue_run_and_wait.side_effect = fake_wait
        mock_get_queue.return_value = mock_queue

        await broker._run_task_body(
            r, session, "00000000-0000-0000-0000-000000000001", "goal"
        )

    assert dispatch_order == [
        "00000000-0000-0000-0000-000000000001-0",
        "00000000-0000-0000-0000-000000000001-1",
    ]
    calls = mock_queue.enqueue_run_and_wait.call_args_list
    first_input = calls[0].args[0].subtask_text
    second_input = calls[1].args[0].subtask_text
    assert "PRIOR RESULTS" not in first_input
    assert "output-00000000-0000-0000-0000-000000000001-0" in second_input


def test_derived_price():
    assert pricing.derived_price(10.0, 0.2) == pytest.approx(12.0)
