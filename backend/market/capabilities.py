"""Capability catalog: stable specialist families expanded into tiered agents."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from contracts.schemas import Agent

ServiceTier = Literal["pro", "flash", "lite"]

TIER_RANK: dict[str, int] = {"pro": 3, "flash": 2, "lite": 1}

DEFAULT_TIER_MODELS: dict[str, str] = {
    "pro": "gemini-3.1-pro-preview",
    "flash": "gemini-3.5-flash",
    "lite": "gemini-3.1-flash-lite",
}

_DATA_PATH = Path(__file__).resolve().parent / "data" / "capabilities.json"


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    name: str
    skills: list[str]
    capability_text: str
    margin: float
    tiers: list[str]
    tier_models: dict[str, str]
    suggested_prompt: str | None = None

    def highest_tier(self) -> str:
        return max(self.tiers, key=lambda t: TIER_RANK[t])


def _load_specs() -> list[CapabilitySpec]:
    raw = json.loads(_DATA_PATH.read_text())
    specs: list[CapabilitySpec] = []
    for item in raw:
        specs.append(
            CapabilitySpec(
                capability_id=item["capability_id"],
                name=item["name"],
                skills=list(item["skills"]),
                capability_text=item["capability_text"],
                margin=float(item["margin"]),
                tiers=list(item["tiers"]),
                tier_models=dict(item["tier_models"]),
                suggested_prompt=item.get("suggested_prompt"),
            )
        )
    return specs


CAPABILITIES: list[CapabilitySpec] = _load_specs()

SUGGESTED_PROMPTS: dict[str, str] = {
    spec.capability_id: spec.suggested_prompt
    for spec in CAPABILITIES
    if spec.suggested_prompt
}

PRIMARY_TIER_BY_CAPABILITY: dict[str, str] = {
    spec.capability_id: spec.highest_tier() for spec in CAPABILITIES
}


def build_tiered_roster() -> list[Agent]:
    agents: list[Agent] = []
    for spec in CAPABILITIES:
        for tier in spec.tiers:
            agents.append(
                Agent(
                    agent_id=f"{spec.capability_id}-{tier}",
                    capability_id=spec.capability_id,
                    service_tier=tier,  # type: ignore[arg-type]
                    name=spec.name,
                    skills=spec.skills,
                    capability_text=spec.capability_text,
                    model=spec.tier_models[tier],
                    tools=[],
                    margin=spec.margin,
                )
            )
    return agents


def build_agents_by_capability(agents: list[Agent]) -> dict[str, list[Agent]]:
    out: dict[str, list[Agent]] = {}
    for agent in agents:
        out.setdefault(agent.capability_id, []).append(agent)
    for siblings in out.values():
        siblings.sort(key=lambda a: TIER_RANK[a.service_tier], reverse=True)
    return out
