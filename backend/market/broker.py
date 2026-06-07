"""Broker: decompose → match → rank → dispatch → judge."""

import json
import uuid

import weave

from contracts.events import (
    AgentHired,
    CandidatesRanked,
    SubtaskSkipped,
    TaskExecuted,
    TaskPosted,
    TaskScored,
)
from contracts.schemas import Agent, Candidate, Subtask
from backend.config import (
    GCP_CHAT_MODEL,
    RANK_RECALL_K,
    RERANK_FINALISTS,
    W_MATCH,
    W_PRICE,
    W_REP,
)
from backend.db import repo
from backend.infra.db import session_scope
from backend.infra.model_router import generate
from backend.infra.redis_client import get_redis
from backend.market import pricing, registry
from backend.market.capabilities import TIER_RANK
from backend.market.judge import judge
from backend.market.ledger import charge_hire, settle
from backend.market.seed_agents import AGENTS_BY_CAPABILITY, SEED_AGENTS, SUGGESTED_PROMPTS
from backend.ports.factory import get_embeddings, get_event_bus, get_queue
from backend.ports.queue import RunDispatch

bus = get_event_bus()
emb = get_embeddings()

BROKER_DECOMPOSE_SYSTEM = (
    "You are the ANEX task broker. Split goals into ordered, self-contained "
    "subtasks that map to specialist agent skills. Reply only with JSON."
)
BROKER_RERANK_SYSTEM = (
    "You are the ANEX hiring broker. Pick the single best-matched agent "
    "for a subtask. Reply only with JSON."
)

_SKIP_BUDGET_MSG = (
    "No agent tier within your preference fits the remaining budget."
)
_SKIP_UNAVAILABLE_MSG = "No agent available to execute this step."


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


async def resolve_broker_llm(
    r, broker_model: str
) -> tuple[str, str]:
    """Resolve model id + provider for broker LLM calls."""
    cached = await registry.get_model_cached(r, broker_model)
    if cached is not None:
        return broker_model, cached["provider"]
    return GCP_CHAT_MODEL, "gcp"


@weave.op
def decompose(
    goal: str,
    *,
    model: str,
    provider: str,
    system: str | None = BROKER_DECOMPOSE_SYSTEM,
) -> list[str]:
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
    raw = generate(model, provider, prompt, system=system)["output"]
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


async def resolve_tier_variants(
    r,
    hits: list[tuple[str, float]],
    ceiling: float,
    *,
    agents_by_capability: dict[str, list[Agent]] | None = None,
    preferred_tier: str = "pro",
) -> list[tuple[float, Agent, float]]:
    """Map vector hits to one affordable tier variant per capability family.

  Picks the highest allowed tier (up to preferred_tier) whose derived hire
  price fits within ceiling. Dedupes multiple tier siblings returned by vector recall.
    """
    max_rank = TIER_RANK.get(preferred_tier, TIER_RANK["pro"])
    catalog = agents_by_capability if agents_by_capability is not None else AGENTS_BY_CAPABILITY
    seen: set[str] = set()
    out: list[tuple[float, Agent, float]] = []

    for agent_id, match in hits:
        hit = await registry.get_agent_cached(r, agent_id)
        if hit is None:
            continue
        cap_id = hit.capability_id
        if cap_id in seen:
            continue

        siblings = catalog.get(cap_id)
        if not siblings:
            siblings = [hit]

        chosen: Agent | None = None
        chosen_price: float | None = None
        for sib in sorted(siblings, key=lambda a: TIER_RANK[a.service_tier], reverse=True):
            if TIER_RANK.get(sib.service_tier, 0) > max_rank:
                continue
            mp = await pricing.model_price(r, sib.model)
            price = pricing.derived_price(mp, sib.margin)
            if price <= ceiling:
                chosen = sib
                chosen_price = price
                break

        if chosen is None or chosen_price is None:
            continue

        seen.add(cap_id)
        out.append((match, chosen, chosen_price))

    return out


@weave.op
async def rank(
    r,
    subtask_text: str,
    *,
    ceiling: float | None = None,
    preferred_tier: str = "pro",
    k: int = RANK_RECALL_K,
) -> list[Candidate]:
    query_vec = emb.embed_bytes(subtask_text, task_type="RETRIEVAL_QUERY")
    hits = await registry.search(r, query_vec, k=k)

    if ceiling is not None:
        resolved = await resolve_tier_variants(
            r, hits, ceiling, preferred_tier=preferred_tier
        )
    else:
        resolved = []
        for agent_id, match in hits:
            a = await registry.get_agent_cached(r, agent_id)
            if a is None:
                continue
            mp = await pricing.model_price(r, a.model)
            price = pricing.derived_price(mp, a.margin)
            resolved.append((match, a, price))

    out: list[Candidate] = []
    for match, agent, price in resolved:
        final = W_MATCH * match + W_REP * agent.reputation - W_PRICE * price
        out.append(
            Candidate(
                agent_id=agent.agent_id,
                match_score=match,
                reputation=agent.reputation,
                price=price,
                final_score=final,
            )
        )
    out.sort(key=lambda c: c.final_score, reverse=True)
    return out


@weave.op
async def select_best(
    r,
    subtask_text: str,
    cands: list[Candidate],
    *,
    model: str,
    provider: str,
    system: str | None = BROKER_RERANK_SYSTEM,
) -> Candidate:
    """LLM re-rank: pick the best-fit agent among the cosine finalists.

    Cosine recall is good at breadth but often returns an over-narrow specialist
    as the nearest neighbour. A single cheap call inspecting each finalist's
    name/skills/capability fixes the 'close but wrong' mismatch. Falls back to
    the cosine top on any error or unknown id, and skips the call for <=1
    candidate.
    """
    if len(cands) <= 1:
        return cands[0]

    finalists = cands[:RERANK_FINALISTS]
    lines: list[str] = []
    for c in finalists:
        a = await registry.get_agent_cached(r, c.agent_id)
        if a is None:
            continue
        skills = ", ".join(a.skills)
        lines.append(
            f"- {c.agent_id} | {a.name} | skills: {skills} | {a.capability_text}"
        )
    if not lines:
        return cands[0]

    prompt = (
        "Pick the single best agent to perform TASK. Choose the one whose skills "
        "and capability most directly produce the required deliverable.\n"
        'Reply ONLY JSON: {"agent_id": "<id>", "reason": "<one line>"}.\n\n'
        f"TASK:\n{subtask_text}\n\nAGENTS:\n" + "\n".join(lines)
    )
    valid = {c.agent_id for c in finalists}
    try:
        raw = generate(model, provider, prompt, system=system)["output"]
        data = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
        chosen_id = str(data.get("agent_id", "")).strip()
        if chosen_id in valid:
            return next(c for c in finalists if c.agent_id == chosen_id)
    except Exception:
        pass
    return cands[0]


@weave.op
async def run_task(
    task_id: str,
    goal: str,
    *,
    user_id: str,
    budget: float,
    broker_model: str = GCP_CHAT_MODEL,
    preferred_tier: str = "pro",
) -> None:
    """Root trace for one posted task; decompose/rank/judge/settle nest under this op."""
    async with session_scope() as session:
        r = get_redis()
        await _run_task_body(
            r,
            session,
            task_id,
            goal,
            user_id=user_id,
            budget=budget,
            broker_model=broker_model,
            preferred_tier=preferred_tier,
        )


async def _live_credits(user_uuid) -> float:
    """Fresh read so concurrent trades / prior hires are reflected in the budget."""
    async with session_scope() as session:
        user = await repo.get_user(session, user_uuid)
        return float(user.credits)


async def _run_task_body(
    r,
    session,
    task_id: str,
    goal: str,
    *,
    user_id: str,
    budget: float,
    broker_model: str = GCP_CHAT_MODEL,
    preferred_tier: str = "pro",
) -> None:
    queue = get_queue()
    llm_model, llm_provider = await resolve_broker_llm(r, broker_model)
    subtask_texts = decompose(
        goal, model=llm_model, provider=llm_provider, system=BROKER_DECOMPOSE_SYSTEM
    )
    subtasks = [
        Subtask(subtask_id=f"{task_id}-{i}", text=t)
        for i, t in enumerate(subtask_texts)
    ]

    task_uuid = uuid.UUID(task_id)
    for i, text in enumerate(subtask_texts):
        await repo.create_subtask(session, task_id=task_uuid, order_index=i, text=text)

    await bus.publish(
        TaskPosted(
            task_id=task_id,
            goal=goal,
            subtasks=subtasks,
            broker_model=broker_model,
            preferred_tier=preferred_tier,
        )
    )

    user_uuid = uuid.UUID(user_id)
    remaining_budget = float(budget)
    prior_results: list[tuple[str, str]] = []
    for st in subtasks:
        ceiling = min(remaining_budget, await _live_credits(user_uuid))
        cands = await rank(
            r, st.text, ceiling=ceiling, preferred_tier=preferred_tier
        )
        if not cands:
            await bus.publish(
                SubtaskSkipped(
                    subtask_id=st.subtask_id,
                    reason="budget",
                    message=_SKIP_BUDGET_MSG,
                )
            )
            continue
        affordable = [c for c in cands if c.price <= ceiling]
        if not affordable:
            await bus.publish(
                SubtaskSkipped(
                    subtask_id=st.subtask_id,
                    reason="budget",
                    message=_SKIP_BUDGET_MSG,
                )
            )
            continue
        top = await select_best(
            r,
            st.text,
            affordable,
            model=llm_model,
            provider=llm_provider,
            system=BROKER_RERANK_SYSTEM,
        )
        a = await registry.get_agent_cached(r, top.agent_id)
        if a is None or not a.service_url:
            await bus.publish(
                SubtaskSkipped(
                    subtask_id=st.subtask_id,
                    reason="unavailable",
                    message=_SKIP_UNAVAILABLE_MSG,
                )
            )
            continue
        model = await registry.get_model_cached(r, a.model)
        if model is None:
            await bus.publish(
                SubtaskSkipped(
                    subtask_id=st.subtask_id,
                    reason="unavailable",
                    message=_SKIP_UNAVAILABLE_MSG,
                )
            )
            continue

        # Pay the hire (own committed txn) before dispatching the work.
        await charge_hire(
            r,
            user_id=user_uuid,
            agent_id=top.agent_id,
            price=top.price,
            task_id=task_id,
            subtask_id=st.subtask_id,
        )
        remaining_budget -= top.price

        ranked = [top] + [c for c in affordable if c.agent_id != top.agent_id]
        await bus.publish(
            CandidatesRanked(subtask_id=st.subtask_id, candidates=ranked)
        )
        await bus.publish(
            AgentHired(
                subtask_id=st.subtask_id,
                agent_id=top.agent_id,
                price=top.price,
                budget_remaining=remaining_budget,
            )
        )
        config = {
            "model": a.model,
            "provider": model["provider"],
            "system": SUGGESTED_PROMPTS.get(a.capability_id) or a.capability_text,
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

    await repo.mark_task_complete(session, task_uuid)


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
            subtask_id=subtask_id,
        )
