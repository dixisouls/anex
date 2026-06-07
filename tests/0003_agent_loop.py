"""
Offline broker rank tests (no GCP, no live agents).

    EMBEDDINGS_FAKE=1 WEAVE_DISABLED=1 pytest tests/0003_agent_loop.py -v
"""

from unittest.mock import AsyncMock, patch

import pytest

from contracts.schemas import Agent, Candidate
from backend.config import PLACEHOLDER_MODEL_PRICE, W_MATCH, W_PRICE, W_REP
from backend.market import broker, pricing


def _writer_agent(tier: str = "flash", margin: float = 0.20) -> Agent:
    return Agent(
        agent_id=f"writer-{tier}",
        capability_id="writer",
        service_tier=tier,  # type: ignore[arg-type]
        name="Copywriter",
        skills=["writing"],
        capability_text="writes copy",
        model="gemini-3.5-flash",
        margin=margin,
        reputation=0.5,
        service_url="http://localhost:9001",
    )


@pytest.fixture
def mock_agent():
    return _writer_agent()


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
        mock_search.return_value = [("writer-flash", match)]
        mock_get.return_value = mock_agent
        mock_mp.return_value = PLACEHOLDER_MODEL_PRICE

        cands = await broker.rank(r, "write a blog post", ceiling=1000.0, k=1)

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
        "a-pro": Agent(
            agent_id="a-pro",
            capability_id="a",
            service_tier="pro",
            name="A",
            skills=[],
            capability_text="a",
            model="m1",
            margin=0.1,
            reputation=0.5,
        ),
        "b-pro": Agent(
            agent_id="b-pro",
            capability_id="b",
            service_tier="pro",
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
        patch.object(broker, "resolve_tier_variants", new_callable=AsyncMock) as mock_resolve,
    ):
        mock_search.return_value = [("a-pro", 0.9), ("b-pro", 0.7)]
        mock_get.side_effect = lambda _r, aid: agents[aid]
        mock_mp.return_value = PLACEHOLDER_MODEL_PRICE
        mock_resolve.return_value = [
            (0.9, agents["a-pro"], pricing.derived_price(PLACEHOLDER_MODEL_PRICE, 0.1)),
            (0.7, agents["b-pro"], pricing.derived_price(PLACEHOLDER_MODEL_PRICE, 0.5)),
        ]

        cands = await broker.rank(r, "task", ceiling=1000.0, k=2)

    assert len(cands) == 2
    assert cands[0].final_score >= cands[1].final_score


def test_decompose_fallback_on_bad_json(monkeypatch):
    monkeypatch.setattr(
        "backend.market.broker.generate", lambda *a, **k: {"output": "not json"}
    )
    assert broker.decompose(
        "single goal", model="gemini-3.5-flash", provider="gcp"
    ) == ["single goal"]


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
        patch.object(
            broker,
            "resolve_broker_llm",
            new_callable=AsyncMock,
            return_value=("gemini-3.5-flash", "gcp"),
        ),
        patch.object(broker, "decompose", return_value=subtask_texts),
        patch.object(broker, "rank", new_callable=AsyncMock) as mock_rank,
        patch.object(broker, "_live_credits", new_callable=AsyncMock) as mock_live,
        patch.object(broker, "charge_hire", new_callable=AsyncMock) as mock_charge,
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
                agent_id="writer-flash",
                match_score=0.9,
                reputation=0.5,
                price=1.0,
                final_score=1.0,
            )
        ]
        mock_live.return_value = 1000.0
        mock_get_agent.return_value = mock_agent
        mock_get_model.return_value = {"provider": "gcp"}
        mock_queue = AsyncMock()
        mock_queue.enqueue_run_and_wait.side_effect = fake_wait
        mock_get_queue.return_value = mock_queue

        await broker._run_task_body(
            r,
            session,
            "00000000-0000-0000-0000-000000000001",
            "goal",
            user_id="00000000-0000-0000-0000-0000000000aa",
            budget=1000.0,
        )

    assert dispatch_order == [
        "00000000-0000-0000-0000-000000000001-0",
        "00000000-0000-0000-0000-000000000001-1",
    ]
    assert mock_charge.await_count == 2
    assert all(c.kwargs["price"] == 1.0 for c in mock_charge.await_args_list)
    calls = mock_queue.enqueue_run_and_wait.call_args_list
    first_input = calls[0].args[0].subtask_text
    second_input = calls[1].args[0].subtask_text
    assert "PRIOR RESULTS" not in first_input
    assert "output-00000000-0000-0000-0000-000000000001-0" in second_input


@pytest.mark.asyncio
async def test_run_task_skips_unaffordable_subtask(mock_agent):
    """When no candidate fits the budget, the subtask is skipped, not hired."""
    r = AsyncMock()
    session = AsyncMock()

    with (
        patch.object(
            broker,
            "resolve_broker_llm",
            new_callable=AsyncMock,
            return_value=("gemini-3.5-flash", "gcp"),
        ),
        patch.object(broker, "decompose", return_value=["only step"]),
        patch.object(broker, "rank", new_callable=AsyncMock) as mock_rank,
        patch.object(broker, "_live_credits", new_callable=AsyncMock) as mock_live,
        patch.object(broker, "charge_hire", new_callable=AsyncMock) as mock_charge,
        patch.object(broker, "select_best", new_callable=AsyncMock) as mock_select,
        patch.object(broker.repo, "create_subtask", new_callable=AsyncMock),
        patch.object(broker.bus, "publish", new_callable=AsyncMock) as mock_pub,
        patch("backend.market.broker.get_queue") as mock_get_queue,
    ):
        mock_rank.return_value = []
        mock_live.return_value = 1000.0
        mock_queue = AsyncMock()
        mock_get_queue.return_value = mock_queue

        await broker._run_task_body(
            r,
            session,
            "00000000-0000-0000-0000-000000000002",
            "goal",
            user_id="00000000-0000-0000-0000-0000000000bb",
            budget=10.0,
        )

    mock_charge.assert_not_awaited()
    mock_select.assert_not_awaited()
    mock_queue.enqueue_run_and_wait.assert_not_awaited()
    published = [c.args[0] for c in mock_pub.await_args_list]
    skipped = [e for e in published if getattr(e, "type", "") == "subtask_skipped"]
    assert skipped
    assert skipped[0].message == broker._SKIP_BUDGET_MSG


def _cand(agent_id: str, final: float) -> Candidate:
    return Candidate(
        agent_id=agent_id,
        match_score=final,
        reputation=0.5,
        price=1.0,
        final_score=final,
    )


@pytest.mark.asyncio
async def test_select_best_single_candidate_skips_llm():
    r = AsyncMock()
    cands = [_cand("only-01", 0.9)]
    with patch.object(broker, "generate") as mock_gen:
        chosen = await broker.select_best(
            r, "task", cands, model="gemini-3.5-flash", provider="gcp"
        )
    assert chosen.agent_id == "only-01"
    mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_select_best_picks_llm_choice(mock_agent):
    r = AsyncMock()
    cands = [_cand("a", 0.9), _cand("b", 0.7), _cand("c", 0.6)]
    with (
        patch.object(
            broker.registry, "get_agent_cached", new_callable=AsyncMock
        ) as mock_get,
        patch.object(broker, "generate") as mock_gen,
    ):
        mock_get.return_value = mock_agent
        mock_gen.return_value = {"output": '{"agent_id": "b", "reason": "best fit"}'}
        chosen = await broker.select_best(
            r, "task", cands, model="gpt-4.1", provider="openai"
        )
    assert chosen.agent_id == "b"
    mock_gen.assert_called_once()
    assert mock_gen.call_args.args[0] == "gpt-4.1"
    assert mock_gen.call_args.args[1] == "openai"
    assert mock_gen.call_args.kwargs.get("system") == broker.BROKER_RERANK_SYSTEM


@pytest.mark.asyncio
async def test_select_best_falls_back_on_unknown_id(mock_agent):
    r = AsyncMock()
    cands = [_cand("a", 0.9), _cand("b", 0.7)]
    with (
        patch.object(
            broker.registry, "get_agent_cached", new_callable=AsyncMock
        ) as mock_get,
        patch.object(broker, "generate") as mock_gen,
    ):
        mock_get.return_value = mock_agent
        mock_gen.return_value = {"output": '{"agent_id": "nonexistent"}'}
        chosen = await broker.select_best(
            r, "task", cands, model="gemini-3.5-flash", provider="gcp"
        )
    assert chosen.agent_id == "a"


@pytest.mark.asyncio
async def test_select_best_falls_back_on_bad_json(mock_agent):
    r = AsyncMock()
    cands = [_cand("a", 0.9), _cand("b", 0.7)]
    with (
        patch.object(
            broker.registry, "get_agent_cached", new_callable=AsyncMock
        ) as mock_get,
        patch.object(broker, "generate") as mock_gen,
    ):
        mock_get.return_value = mock_agent
        mock_gen.return_value = {"output": "not json at all"}
        chosen = await broker.select_best(
            r, "task", cands, model="gemini-3.5-flash", provider="gcp"
        )
    assert chosen.agent_id == "a"


def test_decompose_passes_system_prompt(monkeypatch):
    calls: list[dict] = []

    def fake_generate(model, provider, prompt, system=None):
        calls.append(
            {"model": model, "provider": provider, "system": system, "prompt": prompt}
        )
        return {"output": '["step one"]'}

    monkeypatch.setattr("backend.market.broker.generate", fake_generate)
    broker.decompose("my goal", model="gpt-4.1", provider="openai")
    assert len(calls) == 1
    assert calls[0]["model"] == "gpt-4.1"
    assert calls[0]["provider"] == "openai"
    assert calls[0]["system"] == broker.BROKER_DECOMPOSE_SYSTEM


def test_derived_price():
    assert pricing.derived_price(10.0, 0.2) == pytest.approx(12.0)


def _writer_siblings() -> dict[str, list[Agent]]:
    pro = _writer_agent("pro", margin=0.20)
    flash = _writer_agent("flash", margin=0.20)
    lite = _writer_agent("lite", margin=0.20)
    return {"writer": [pro, flash, lite]}


@pytest.mark.asyncio
async def test_resolve_tier_prefers_pro_when_affordable():
    r = AsyncMock()
    siblings = _writer_siblings()
    index = {a.agent_id: a for a in siblings["writer"]}
    with (
        patch.object(
            broker.registry, "get_agent_cached", new_callable=AsyncMock
        ) as mock_get,
        patch.object(broker.pricing, "model_price", new_callable=AsyncMock) as mock_mp,
    ):
        mock_get.side_effect = lambda _r, aid: index[aid]
        mock_mp.side_effect = [100.0, 50.0, 20.0]
        resolved = await broker.resolve_tier_variants(
            r, [("writer-pro", 0.9)], ceiling=200.0, agents_by_capability=siblings
        )
    assert len(resolved) == 1
    assert resolved[0][1].agent_id == "writer-pro"


@pytest.mark.asyncio
async def test_resolve_tier_downgrades_to_flash():
    r = AsyncMock()
    siblings = _writer_siblings()
    index = {a.agent_id: a for a in siblings["writer"]}
    with (
        patch.object(
            broker.registry, "get_agent_cached", new_callable=AsyncMock
        ) as mock_get,
        patch.object(broker.pricing, "model_price", new_callable=AsyncMock) as mock_mp,
    ):
        mock_get.side_effect = lambda _r, aid: index[aid]
        mock_mp.side_effect = [100.0, 50.0, 20.0]
        resolved = await broker.resolve_tier_variants(
            r, [("writer-pro", 0.9)], ceiling=80.0, agents_by_capability=siblings
        )
    assert resolved[0][1].agent_id == "writer-flash"


@pytest.mark.asyncio
async def test_resolve_tier_downgrades_to_lite():
    r = AsyncMock()
    siblings = _writer_siblings()
    index = {a.agent_id: a for a in siblings["writer"]}
    with (
        patch.object(
            broker.registry, "get_agent_cached", new_callable=AsyncMock
        ) as mock_get,
        patch.object(broker.pricing, "model_price", new_callable=AsyncMock) as mock_mp,
    ):
        mock_get.side_effect = lambda _r, aid: index[aid]
        mock_mp.side_effect = [100.0, 50.0, 20.0]
        resolved = await broker.resolve_tier_variants(
            r, [("writer-pro", 0.9)], ceiling=30.0, agents_by_capability=siblings
        )
    assert resolved[0][1].agent_id == "writer-lite"


@pytest.mark.asyncio
async def test_resolve_tier_respects_preferred_tier_ceiling():
    """When preferred_tier=flash, pro is excluded even if affordable."""
    r = AsyncMock()
    siblings = _writer_siblings()
    index = {a.agent_id: a for a in siblings["writer"]}
    with (
        patch.object(
            broker.registry, "get_agent_cached", new_callable=AsyncMock
        ) as mock_get,
        patch.object(broker.pricing, "model_price", new_callable=AsyncMock) as mock_mp,
    ):
        mock_get.side_effect = lambda _r, aid: index[aid]
        mock_mp.side_effect = [100.0, 50.0, 20.0]
        resolved = await broker.resolve_tier_variants(
            r,
            [("writer-pro", 0.9)],
            ceiling=200.0,
            agents_by_capability=siblings,
            preferred_tier="flash",
        )
    assert len(resolved) == 1
    assert resolved[0][1].agent_id == "writer-flash"


@pytest.mark.asyncio
async def test_resolve_tier_dedupes_siblings():
    r = AsyncMock()
    siblings = _writer_siblings()
    index = {a.agent_id: a for a in siblings["writer"]}
    with (
        patch.object(
            broker.registry, "get_agent_cached", new_callable=AsyncMock
        ) as mock_get,
        patch.object(broker.pricing, "model_price", new_callable=AsyncMock) as mock_mp,
    ):
        mock_get.side_effect = lambda _r, aid: index[aid]
        mock_mp.return_value = 10.0
        resolved = await broker.resolve_tier_variants(
            r,
            [("writer-pro", 0.9), ("writer-flash", 0.95), ("writer-lite", 0.99)],
            ceiling=1000.0,
            agents_by_capability=siblings,
        )
    assert len(resolved) == 1
    assert resolved[0][1].agent_id == "writer-pro"


@pytest.mark.asyncio
async def test_single_tier_capability():
    r = AsyncMock()
    flash_only = Agent(
        agent_id="summarizer-flash",
        capability_id="summarizer",
        service_tier="flash",
        name="Summarizer",
        skills=["summarization"],
        capability_text="summarizes documents",
        model="gemini-3.5-flash",
        margin=0.15,
    )
    catalog = {"summarizer": [flash_only]}
    with (
        patch.object(
            broker.registry, "get_agent_cached", new_callable=AsyncMock, return_value=flash_only
        ),
        patch.object(broker.pricing, "model_price", new_callable=AsyncMock) as mock_mp,
    ):
        mock_mp.return_value = 10.0
        resolved = await broker.resolve_tier_variants(
            r,
            [("summarizer-flash", 0.8)],
            ceiling=1000.0,
            agents_by_capability=catalog,
        )
    assert resolved[0][1].agent_id == "summarizer-flash"


@pytest.mark.asyncio
async def test_run_task_downgrades_mid_task():
    r = AsyncMock()
    session = AsyncMock()
    hired: list[str] = []

    async def fake_rank(_r, _text, *, ceiling, preferred_tier="pro", k=10):
        tier = "writer-pro" if ceiling >= 100.0 else "writer-lite"
        return [
            Candidate(
                agent_id=tier,
                match_score=0.9,
                reputation=0.5,
                price=10.0 if tier.endswith("pro") else 1.0,
                final_score=1.0,
            )
        ]

    with (
        patch.object(
            broker,
            "resolve_broker_llm",
            new_callable=AsyncMock,
            return_value=("gemini-3.5-flash", "gcp"),
        ),
        patch.object(broker, "decompose", return_value=["step one", "step two"]),
        patch.object(broker, "rank", side_effect=fake_rank),
        patch.object(broker, "_live_credits", new_callable=AsyncMock, return_value=1000.0),
        patch.object(broker, "select_best", new_callable=AsyncMock) as mock_select,
        patch.object(broker, "charge_hire", new_callable=AsyncMock) as mock_charge,
        patch.object(
            broker.registry, "get_agent_cached", new_callable=AsyncMock
        ) as mock_get_agent,
        patch.object(
            broker.registry, "get_model_cached", new_callable=AsyncMock, return_value={"provider": "gcp"}
        ),
        patch.object(broker.repo, "create_subtask", new_callable=AsyncMock),
        patch.object(broker.bus, "publish", new_callable=AsyncMock),
        patch("backend.market.broker.get_queue") as mock_get_queue,
    ):
        mock_select.side_effect = lambda _r, _t, cands, **_: cands[0]
        mock_get_agent.side_effect = lambda _r, aid: _writer_agent(aid.split("-")[1])
        mock_queue = AsyncMock()
        mock_queue.enqueue_run_and_wait.return_value = "done"
        mock_get_queue.return_value = mock_queue

        def capture_charge(*_a, **kw):
            hired.append(kw["agent_id"])

        mock_charge.side_effect = capture_charge

        await broker._run_task_body(
            r,
            session,
            "00000000-0000-0000-0000-000000000003",
            "goal",
            user_id="00000000-0000-0000-0000-0000000000cc",
            budget=105.0,
        )

    assert hired == ["writer-pro", "writer-lite"]
