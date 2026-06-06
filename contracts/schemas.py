"""
These are the core data objects that cross track boundries:
the Agent record, the Subtask and Candidate rows, and the Task record.

Pydantic v2.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Subtask(BaseModel):
    """One unit of work the broker decomposes a goal into. Order matters:
    the broker produces an ordered list and the list order is the run order."""

    subtask_id: str
    text: str


class Candidate(BaseModel):
    """One ranked agent for a subtask, as produced by the broker's match and
    rank step. A candidate list is sorted by final_score, highest first."""

    agent_id: str
    match_score: float
    reputation: float
    price: float  # derived hire price = model_price(model) * (1 + margin)
    final_score: float


class Agent(BaseModel):
    """The agent record. price is derived at read time when serving GET /agents."""

    agent_id: str
    name: str
    skills: list[str]
    capability_text: str
    model: str
    tools: list[str] = Field(default_factory=list)
    reputation: float = 0.5
    credits: float = 100.0
    margin: float = 0.2
    price: float | None = None
    hires: int = 0
    wins: int = 0
    service_url: Optional[str] = None


class Task(BaseModel):
    """A posted goal and its decomposition. Stored at task:{task_id} in redis."""

    task_id: str
    goal: str
    subtasks: list[Subtask] = Field(default_factory=list)
    status: Literal["posted", "running", "complete"] = "posted"


class Model(BaseModel):
    model_id: str
    name: str
    provider: Literal["gcp", "openai"]
    tier: Literal["pro", "flash", "lite"]
    executable: bool = True
    shares: float
    credits: float
    price: float
    ipo_price: float


class Holding(BaseModel):
    model_id: str
    shares: float
    price: float
    value: float


class Portfolio(BaseModel):
    user_id: str
    credits: float
    holdings: list[Holding]
    holdings_value: float
    total: float


class UserPublic(BaseModel):
    user_id: str
    name: str
    email: str | None = None
    credits: float
    is_sim: bool
    net_worth: float | None = None
