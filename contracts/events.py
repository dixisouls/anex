"""
Market events pushed to the feed. Every event carries event_id and ts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, Field, TypeAdapter

from .schemas import Candidate, Subtask


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventBase(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    ts: str = Field(default_factory=_now_iso)


class TaskPosted(EventBase):
    type: Literal["task_posted"] = "task_posted"
    task_id: str
    goal: str
    subtasks: list[Subtask]
    broker_model: str | None = None
    preferred_tier: str | None = None


class CandidatesRanked(EventBase):
    type: Literal["candidates_ranked"] = "candidates_ranked"
    subtask_id: str
    candidates: list[Candidate]


class AgentHired(EventBase):
    type: Literal["agent_hired"] = "agent_hired"
    subtask_id: str
    agent_id: str
    price: float = 0.0
    budget_remaining: float = 0.0


class SubtaskSkipped(EventBase):
    type: Literal["subtask_skipped"] = "subtask_skipped"
    subtask_id: str
    reason: str = "budget"
    message: str | None = None


class TaskExecuted(EventBase):
    type: Literal["task_executed"] = "task_executed"
    subtask_id: str
    agent_id: str
    output_preview: str


class TaskScored(EventBase):
    type: Literal["task_scored"] = "task_scored"
    subtask_id: str
    agent_id: str
    judge_score: float


class ReputationChanged(EventBase):
    type: Literal["reputation_changed"] = "reputation_changed"
    agent_id: str
    old: float
    new: float


class CreditsChanged(EventBase):
    type: Literal["credits_changed"] = "credits_changed"
    agent_id: str
    old: float
    new: float


class AgentUpgraded(EventBase):
    type: Literal["agent_upgraded"] = "agent_upgraded"
    agent_id: str
    change_type: str
    detail: str
    cost: float


class ModelListed(EventBase):
    type: Literal["model_listed"] = "model_listed"
    model_id: str
    name: str
    provider: str
    tier: str
    ipo_price: float


class PriceChanged(EventBase):
    type: Literal["price_changed"] = "price_changed"
    model_id: str
    old: float
    new: float
    reason: str


class EarningsInjected(EventBase):
    type: Literal["earnings_injected"] = "earnings_injected"
    model_id: str
    agent_id: str
    amount: float
    judge_score: float


class TradeExecuted(EventBase):
    type: Literal["trade_executed"] = "trade_executed"
    trade_id: str
    user_id: str
    model_id: str
    side: str
    shares: float
    credits: float
    price: float


class PortfolioChanged(EventBase):
    type: Literal["portfolio_changed"] = "portfolio_changed"
    user_id: str
    credits: float
    holdings_value: float
    total: float


MarketEvent = Annotated[
    Union[
        TaskPosted,
        CandidatesRanked,
        AgentHired,
        SubtaskSkipped,
        TaskExecuted,
        TaskScored,
        ReputationChanged,
        CreditsChanged,
        AgentUpgraded,
        ModelListed,
        PriceChanged,
        EarningsInjected,
        TradeExecuted,
        PortfolioChanged,
    ],
    Field(discriminator="type"),
]

EVENT_ADAPTER: TypeAdapter[MarketEvent] = TypeAdapter(MarketEvent)


def parse_event(data: dict) -> MarketEvent:
    return EVENT_ADAPTER.validate_python(data)
