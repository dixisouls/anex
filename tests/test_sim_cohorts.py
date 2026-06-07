"""
Tests for hybrid role-based sim investor cohorts.

    WEAVE_DISABLED=1 pytest tests/test_sim_cohorts.py -v
"""

from unittest.mock import MagicMock

import pytest

from backend.sim import cohorts
from backend.sim import runner as sim_runner
from backend.sim import strategies


def test_default_cohort_counts():
    cohorts_list = cohorts.default_cohorts()
    total = cohorts.total_investor_count(cohorts_list)
    assert total == 8 + 6 + 20 + 4
    math_n = sum(c.count for c in cohorts_list if c.mode == "math")
    llm_n = sum(c.count for c in cohorts_list if c.mode == "llm")
    assert math_n == 14
    assert llm_n == 24


def test_expand_assignments_rotates_strategies():
    spec = [
        cohorts.InvestorCohort(
            name="retail",
            mode="llm",
            strategies=(strategies.NOISE, strategies.VALUE),
            count=4,
            cadence_s=12.0,
        )
    ]
    assigns = cohorts.expand_assignments(spec, stagger_s=0.0)
    assert len(assigns) == 4
    assert [a.strategy for a in assigns] == [
        strategies.NOISE,
        strategies.VALUE,
        strategies.NOISE,
        strategies.VALUE,
    ]
    assert all(a.mode == "llm" and a.cadence_s == 12.0 for a in assigns)


def test_whale_cohort_trade_cap():
    whale = next(c for c in cohorts.default_cohorts() if c.name == "whale")
    assert whale.trade_cap == 250.0
    assigns = cohorts.expand_assignments([whale], stagger_s=0.0)
    assert all(a.trade_cap == 250.0 for a in assigns)


def test_spawn_cohort_investors_creates_one_task_per_assignment(monkeypatch):
    created: list = []

    def fake_create_task(coro):
        created.append(coro)
        return MagicMock()

    monkeypatch.setattr(sim_runner.asyncio, "create_task", fake_create_task)
    sim_runner._tasks = []
    assignments = cohorts.expand_assignments(cohorts.default_cohorts())
    ids = [f"user-{i}" for i in range(len(assignments))]
    sim_runner._spawn_cohort_investors("http://localhost:8000", ids, assignments)
    assert len(created) == len(assignments)
    assert len(sim_runner._tasks) == len(assignments)


def test_cohort_mm_and_quant_are_math():
    assigns = cohorts.expand_assignments(cohorts.default_cohorts())
    math = [a for a in assigns if a.mode == "math"]
    llm = [a for a in assigns if a.mode == "llm"]
    assert {a.cohort for a in math} == {"mm", "quant"}
    assert {a.cohort for a in llm} == {"retail", "whale"}
