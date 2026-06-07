"""Role-based investor cohorts for hybrid math + LLM market simulation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from backend.config import TRADE_CAP
from backend.sim import strategies

InvestorMode = Literal["math", "llm"]


@dataclass(frozen=True)
class InvestorCohort:
    """One sim role: N investors sharing mode, cadence, and strategy palette."""

    name: str
    mode: InvestorMode
    strategies: tuple[str, ...]
    count: int
    cadence_s: float
    trade_cap: float | None = None


@dataclass(frozen=True)
class InvestorAssignment:
    """Flattened spawn spec for a single sim-investor user."""

    cohort: str
    mode: InvestorMode
    strategy: str
    cadence_s: float
    trade_cap: float
    start_delay_s: float


def _int_env(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))


def _float_env(key: str, default: float) -> float:
    return float(os.getenv(key, str(default)))


def default_cohorts() -> list[InvestorCohort]:
    """Agent-heavy hybrid: fast math liquidity + slower discretionary LLM."""
    return [
        InvestorCohort(
            name="mm",
            mode="math",
            strategies=(strategies.MARKET_MAKER, strategies.STAT_ARB),
            count=_int_env("SIM_MM_COUNT", 8),
            cadence_s=_float_env("SIM_MM_CADENCE_S", 3.0),
        ),
        InvestorCohort(
            name="quant",
            mode="math",
            strategies=(strategies.MOMENTUM, strategies.VALUE, strategies.STAT_ARB),
            count=_int_env("SIM_QUANT_COUNT", 6),
            cadence_s=_float_env("SIM_QUANT_CADENCE_S", 6.0),
        ),
        InvestorCohort(
            name="retail",
            mode="llm",
            strategies=(
                strategies.NOISE,
                strategies.MOMENTUM,
                strategies.CONTRARIAN,
                strategies.VALUE,
            ),
            count=_int_env("SIM_RETAIL_COUNT", 20),
            cadence_s=_float_env("SIM_RETAIL_CADENCE_S", 12.0),
        ),
        InvestorCohort(
            name="whale",
            mode="llm",
            strategies=(strategies.VALUE, strategies.MOMENTUM),
            count=_int_env("SIM_WHALE_COUNT", 4),
            cadence_s=_float_env("SIM_WHALE_CADENCE_S", 30.0),
            trade_cap=_float_env("SIM_WHALE_TRADE_CAP", 250.0),
        ),
    ]


def cohorts_enabled() -> bool:
    return os.getenv("SIM_USE_COHORTS", "1").strip().lower() in ("1", "true", "yes")


def total_investor_count(cohorts: list[InvestorCohort]) -> int:
    return sum(c.count for c in cohorts)


def expand_assignments(
    cohorts: list[InvestorCohort],
    *,
    stagger_s: float = 0.35,
) -> list[InvestorAssignment]:
    """One assignment per investor, strategies rotated within each cohort."""
    out: list[InvestorAssignment] = []
    slot = 0
    for cohort in cohorts:
        if cohort.count <= 0:
            continue
        cap = cohort.trade_cap if cohort.trade_cap is not None else TRADE_CAP
        palette = cohort.strategies or (strategies.NOISE,)
        for i in range(cohort.count):
            out.append(
                InvestorAssignment(
                    cohort=cohort.name,
                    mode=cohort.mode,
                    strategy=palette[i % len(palette)],
                    cadence_s=cohort.cadence_s,
                    trade_cap=cap,
                    start_delay_s=slot * stagger_s,
                )
            )
            slot += 1
    return out
