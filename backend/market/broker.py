"""Broker: decompose → match → rank → dispatch → judge."""

import json
import uuid

import weave

from contracts.events import (
    AgentHired,
    CandidatesRanked,
    TaskExecuted,
    TaskPosted,
    TaskScored,
)
from contracts.schemas import Candidate, Subtask
from backend.config import GCP_CHAT_MODEL, W_MATCH, W_PRICE, W_REP
from backend.db import repo
from backend.infra.db import session_scope
from backend.infra.model_router import generate
from backend.infra.redis_client import get_redis
from backend.market import pricing, registry
from backend.market.judge import judge
from backend.market.ledger import settle
from backend.market.seed_agents import SEED_AGENTS, SUGGESTED_PROMPTS
from backend.ports.factory import get_embeddings, get_event_bus, get_queue
from backend.ports.queue import RunDispatch

bus = get_event_bus()
emb = get_embeddings()


def _build_skill_catalog(limit: int = 64) -> str:
    """Deduplicated, evenly-sampled skill list advertised to the decomposer so
    subtasks are worded to match capabilities the roster actually has."""
    seen: dict[str, str] = {}
    for a in SEED_AGENTS:
        for s in a.skills:
            norm = " ".join(str(s).split())
            key = norm.lower()
            if norm and key not in seen:
                seen[key] = norm
    skills = list(seen.values())
    if len(skills) > limit:
        step = len(skills) / limit
        skills = [skills[int(i * step)] for i in range(limit)]
    return ", ".join(sorted(skills))


_SKILL_CATALOG = _build_skill_catalog()


def _build_subtask_prompt(
    goal: str,
    subtask_text: str,
    prior_results: list[tuple[str, str]],
) -> str:
    if not prior_results:
        return f"ORIGINAL GOAL: {goal}\n\nCURRENT TASK: {subtask_text}"
    lines = [
        f"- Step {i} ({text}): {output}"
        for i, (text, output) in enumerate(prior_results)
    ]
    return (
        f"ORIGINAL GOAL: {goal}\n\n"
        f"PRIOR RESULTS:\n"
        + "\n".join(lines)
        + f"\n\nCURRENT TASK: {subtask_text}"
    )


@weave.op
def decompose(goal: str) -> list[str]:
    prompt = (
        "Split GOAL into 1-4 ordered subtasks for specialized agents.\n"
        "Each subtask string MUST be self-contained: include concrete content "
        "from GOAL (phrases, names, code, data) so an agent can execute it "
        "without seeing the original goal.\n"
        "Word each subtask to align with the available agent skills below so it "
        "can be matched to a specialist. Do not invent capabilities outside this "
        "list.\n"
        f"AVAILABLE AGENT SKILLS: {_SKILL_CATALOG}\n"
        "Reply ONLY a JSON list of strings.\n\n"
        f"GOAL: {goal}"
    )
    raw = generate(GCP_CHAT_MODEL, "gcp", prompt)["output"]
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            items = json.loads(raw[start:end])
            texts = [str(x).strip() for x in items if str(x).strip()]
            if texts:
                return texts[:4]
    except Exception:
        pass
    return [goal]


@weave.op
async def rank(r, subtask_text: str, k: int = 5) -> list[Candidate]:
    hits = await registry.search(r, emb.embed_bytes(subtask_text), k=k)
    out: list[Candidate] = []
    for agent_id, match in hits:
        a = await registry.get_agent_cached(r, agent_id)
        if a is None:
            continue
        mp = await pricing.model_price(r, a.model)
        price = pricing.derived_price(mp, a.margin)
        final = W_MATCH * match + W_REP * a.reputation - W_PRICE * price
        out.append(
            Candidate(
                agent_id=agent_id,
                match_score=match,
                reputation=a.reputation,
                price=price,
                final_score=final,
            )
        )
    out.sort(key=lambda c: c.final_score, reverse=True)
    return out


@weave.op
async def run_task(task_id: str, goal: str) -> None:
    """Root trace for one posted task; decompose/rank/judge/settle nest under this op."""
    async with session_scope() as session:
        r = get_redis()
        await _run_task_body(r, session, task_id, goal)


async def _run_task_body(r, session, task_id: str, goal: str) -> None:
    queue = get_queue()
    subtask_texts = decompose(goal)
    subtasks = [
        Subtask(subtask_id=f"{task_id}-{i}", text=t)
        for i, t in enumerate(subtask_texts)
    ]

    task_uuid = uuid.UUID(task_id)
    for i, text in enumerate(subtask_texts):
        await repo.create_subtask(session, task_id=task_uuid, order_index=i, text=text)

    await bus.publish(TaskPosted(task_id=task_id, goal=goal, subtasks=subtasks))

    prior_results: list[tuple[str, str]] = []
    for st in subtasks:
        cands = await rank(r, st.text)
        if not cands:
            continue
        await bus.publish(
            CandidatesRanked(subtask_id=st.subtask_id, candidates=cands)
        )
        top = cands[0]
        await bus.publish(
            AgentHired(subtask_id=st.subtask_id, agent_id=top.agent_id)
        )
        a = await registry.get_agent_cached(r, top.agent_id)
        if a is None or not a.service_url:
            continue
        model = await registry.get_model_cached(r, a.model)
        if model is None:
            continue
        config = {
            "model": a.model,
            "provider": model["provider"],
            "system": SUGGESTED_PROMPTS.get(top.agent_id) or a.capability_text,
            "tools": a.tools,
        }
        agent_input = _build_subtask_prompt(goal, st.text, prior_results)
        output = await queue.enqueue_run_and_wait(
            RunDispatch(
                subtask_id=st.subtask_id,
                agent_id=top.agent_id,
                service_url=a.service_url,
                subtask_text=agent_input,
                config=config,
                task_id=task_id,
            )
        )
        if output is not None:
            prior_results.append((st.text, output))


async def handle_run_result(
    r,
    session,
    *,
    subtask_id: str,
    agent_id: str,
    output: str,
    task_id: str,
) -> None:
    if await registry.subtask_already_scored(r, subtask_id):
        return

    subtask = await repo.get_subtask(session, subtask_id)
    subtask_text = subtask.text if subtask else ""

    await bus.publish(
        TaskExecuted(
            subtask_id=subtask_id,
            agent_id=agent_id,
            output_preview=output,
        )
    )
    score, _reason = judge(subtask_text, output)
    await bus.publish(
        TaskScored(subtask_id=subtask_id, agent_id=agent_id, judge_score=score)
    )
    await repo.save_subtask_result(
        session,
        subtask_id=subtask_id,
        agent_id=agent_id,
        output_preview=output,
        judge_score=score,
    )
    a = await registry.get_agent_cached(r, agent_id)
    if a is not None:
        mp = await pricing.model_price(r, a.model)
        await settle(
            r,
            session,
            agent_id=agent_id,
            model_id=a.model,
            judge_score=score,
            derived_price=pricing.derived_price(mp, a.margin),
            task_id=task_id,
        )
