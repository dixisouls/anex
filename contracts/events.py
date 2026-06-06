"""
The eight events the backend pushes and the frontend renders. Every event
carries event_id and ts, both auto-filled on construction so no two callers
stamp them differently. Construct an event with just its payload fields.

    ev = TaskScored(subtask_id="s-001", agent_id="writer-01", judge_score=0.95)
    redis.xadd("market:feed", {"data": ev.model_dump_json()})

The /feed endpoint reads entries off the stream and forwards each as a server-sent
event. The frontend switches on the `type` field.

Pydantic v2.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, Field, TypeAdapter

from .schemas import Candidate, Subtask

def _now_iso() -> str:
    """UTC timestamp in ISO 8601 format, for example 2026-06-02T18:30:00.123456+00:00."""
    return datetime.now(timezone.utc).isoformat()

class EventBase(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    ts: str = Field(default_factory=_now_iso)

class TaskPosted(EventBase):
    type: Literal["task_posted"] = "task_posted"
    task_id: str
    goal: str
    subtasks: list[Subtask]

class CandidatesRanked(EventBase):
    type: Literal["candidates_ranked"] = "candidates_ranked"
    subtask_id: str
    candidates: list[Candidate] # sorted by final_score, highest first

class AgentHired(EventBase):
    type: Literal["agent_hired"] = "agent_hired"
    subtask_id: str
    agent_id: str

class TaskExecuted(EventBase):
    type: Literal["task_executed"] = "task_executed"
    subtask_id: str
    agent_id: str
    output_preview: str

class TaskScored(EventBase):
    type: Literal["task_scored"] = "task_scored"
    subtask_id: str
    agent_id: str
    judge_score: float # 0 to 1

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
    change_type: str # model_swap, add_tool, price_bump
    detail: str      # human readable, for example "gemini-flash to gemini-pro"
    cost: float

MarketEvent = Annotated[
    Union[
        TaskPosted,
        CandidatesRanked,
        AgentHired,
        TaskExecuted,
        TaskScored,
        ReputationChanged,
        CreditsChanged,
        AgentUpgraded,
    ],
    Field(discriminator="type")
]

# Use this to validate or parse an event coming back as dict or JSON string,
# for example when reading off the stream
# ev = EVENT_ADAPTER.validate_json(raw)
EVENT_ADAPTER: TypeAdapter[MarketEvent] = TypeAdapter(MarketEvent)

def parse_event(data: dict) -> MarketEvent:
    """Turn plain dict (one stream entry) into the right event model."""
    return EVENT_ADAPTER.validate_python(data)