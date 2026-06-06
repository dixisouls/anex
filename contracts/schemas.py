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
    match_score: float    # cosine similarity of subtask vs capability, 0 to 1
    reputation: float     # the agent's current reputation, 0 to 1
    price: float          # the agent's current price
    final_score: float    #  w1 * match + w2 * reputation - w3 * price, any real number

class Agent(BaseModel):
    """The agent record. The public roster (GET /agents) returns these fields
    with service_url excluded. The redis hash stores these fields plus
    service_url plus the capability vector (the vector is never JSON, it is 
    raw float32 bytes in redis, so it is not modelled here).

    To serialize for the public roster: agent.model_dump(exclude={"service_url"}).
    """

    agent_id: str
    name: str
    skills: list[str]
    capability_text: str
    model: str
    tools: list[str] = Field(default_factory=list)
    reputation: float = 0.5
    credits: float = 100.0
    price: float = 5.0
    hires: int = 0
    wins: int = 0

    # Internal only. Where the broker sends the hire (localhost port in dev,
    # Cloud Run URL after). Excluded from public roster.
    service_url: Optional[str] = None

class Task(BaseModel):
    """A posted goal and its decomposition. Stored at task:{task_id} in redis."""

    task_id: str
    goal: str
    subtasks: list[Subtask] = Field(default_factory=list)
    status: Literal["posted", "running", "complete"] = "posted"