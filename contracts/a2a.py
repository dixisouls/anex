"""
A2A (Agent-to-Agent) protocol schemas.

Implements the core Google A2A spec types needed for task delegation:
  AgentCard   — capability declaration at /.well-known/agent.json
  Task        — unit of work passed to POST /tasks/send
  Message     — user or agent turn carrying Parts
  TextPart    — plain-text content within a Message
  Artifact    — output produced by a completed task
  TaskStatus  — current state of a task
  TaskState   — state machine enum

Spec reference: https://google.github.io/A2A
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Parts ─────────────────────────────────────────────────────────────────────


class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


Part = TextPart  # extend with FilePart / DataPart as needed


# ── Message ───────────────────────────────────────────────────────────────────


class Message(BaseModel):
    role: Literal["user", "agent"]
    parts: list[TextPart]

    @staticmethod
    def user(text: str) -> "Message":
        return Message(role="user", parts=[TextPart(text=text)])

    def text(self) -> str:
        return " ".join(p.text for p in self.parts if isinstance(p, TextPart))


# ── Artifact ──────────────────────────────────────────────────────────────────


class Artifact(BaseModel):
    name: str | None = None
    parts: list[TextPart]

    def text(self) -> str:
        return " ".join(p.text for p in self.parts if isinstance(p, TextPart))


# ── Task state machine ────────────────────────────────────────────────────────


class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    INPUT_REQUIRED = "input-required"


class TaskStatus(BaseModel):
    state: TaskState
    message: Message | None = None
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ── Task ──────────────────────────────────────────────────────────────────────


class A2ATask(BaseModel):
    """Inbound task sent by an orchestrator to POST /tasks/send."""

    id: str
    session_id: str | None = None
    message: Message
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2ATaskResult(BaseModel):
    """Response returned by POST /tasks/send."""

    id: str
    status: TaskStatus
    artifacts: list[Artifact] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @staticmethod
    def completed(task_id: str, output: str) -> "A2ATaskResult":
        return A2ATaskResult(
            id=task_id,
            status=TaskStatus(state=TaskState.COMPLETED),
            artifacts=[Artifact(parts=[TextPart(text=output)])],
        )

    @staticmethod
    def failed(task_id: str, reason: str) -> "A2ATaskResult":
        return A2ATaskResult(
            id=task_id,
            status=TaskStatus(
                state=TaskState.FAILED,
                message=Message(role="agent", parts=[TextPart(text=reason)]),
            ),
        )

    def output_text(self) -> str | None:
        if not self.artifacts:
            return None
        return self.artifacts[0].text() or None


# ── Agent Card ────────────────────────────────────────────────────────────────


class AgentSkill(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)


class AgentCapabilities(BaseModel):
    streaming: bool = False
    push_notifications: bool = False
    state_transition_history: bool = False


class AgentCard(BaseModel):
    """Served at GET /.well-known/agent.json."""

    name: str
    description: str
    url: str
    version: str = "1.0.0"
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    skills: list[AgentSkill] = Field(default_factory=list)
    default_input_modes: list[str] = Field(default=["text"])
    default_output_modes: list[str] = Field(default=["text"])
