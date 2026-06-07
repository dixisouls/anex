"""
Offline tests for password hashing and the credit-charging hire path.

    WEAVE_DISABLED=1 pytest tests/0006_credits_auth.py -v
"""

from unittest.mock import AsyncMock, patch

import pytest

from contracts.schemas import Portfolio
from backend.infra.passwords import hash_password, verify_password
from backend.market import ledger


def test_password_hash_roundtrip():
    stored = hash_password("hunter2")
    assert stored.startswith("pbkdf2_sha256$")
    assert verify_password("hunter2", stored)
    assert not verify_password("wrong", stored)


def test_password_hash_is_salted():
    a = hash_password("same")
    b = hash_password("same")
    assert a != b  # random salt
    assert verify_password("same", a)
    assert verify_password("same", b)


def test_verify_handles_garbage():
    assert not verify_password("x", None)
    assert not verify_password("x", "")
    assert not verify_password("x", "not-a-valid-format")
    assert not verify_password("", hash_password("x"))


@pytest.mark.asyncio
async def test_charge_hire_debits_user_and_credits_agent():
    r = AsyncMock()
    fake_session = AsyncMock()

    class _Scope:
        async def __aenter__(self):
            return fake_session

        async def __aexit__(self, *exc):
            return False

    portfolio_val = Portfolio(
        user_id="u1",
        credits=950.0,
        holdings=[],
        holdings_value=0.0,
        total=950.0,
    )

    with (
        patch.object(ledger, "session_scope", lambda: _Scope()),
        patch.object(ledger.repo, "adjust_user_credits", new_callable=AsyncMock) as deb,
        patch.object(
            ledger.repo, "adjust_agent_credits", new_callable=AsyncMock
        ) as cred,
        patch.object(ledger.repo, "add_ledger_entry", new_callable=AsyncMock) as entry,
        patch.object(ledger.registry, "reproject_agent", new_callable=AsyncMock),
        patch.object(ledger.portfolio, "value", new_callable=AsyncMock) as pval,
        patch.object(ledger.bus, "publish", new_callable=AsyncMock) as pub,
    ):
        cred.return_value = (100.0, 150.0)
        pval.return_value = portfolio_val

        await ledger.charge_hire(
            r, user_id="u1", agent_id="writer-01", price=50.0, task_id="t1"
        )

    deb.assert_awaited_once()
    assert deb.await_args.args[2] == -50.0  # user debited
    cred.assert_awaited_once()
    assert cred.await_args.args[2] == 50.0  # agent treasury credited
    entry.assert_awaited_once()
    assert entry.await_args.kwargs["kind"] == "hire"
    assert entry.await_args.kwargs["credits_delta"] == 50.0

    published = [c.args[0].type for c in pub.await_args_list]
    assert "credits_changed" in published
    assert "portfolio_changed" in published


@pytest.mark.asyncio
async def test_grant_credits_increases_balance_and_emits_portfolio():
    r = AsyncMock()
    fake_session = AsyncMock()

    class _Scope:
        async def __aenter__(self):
            return fake_session

        async def __aexit__(self, *exc):
            return False

    from backend.market import credits

    portfolio_val = Portfolio(
        user_id="u1",
        credits=1200.0,
        holdings=[],
        holdings_value=0.0,
        total=1200.0,
    )

    with (
        patch.object(credits, "session_scope", lambda: _Scope()),
        patch.object(credits.repo, "adjust_user_credits", new_callable=AsyncMock) as adj,
        patch.object(credits.portfolio, "value", new_callable=AsyncMock) as pval,
        patch.object(credits.bus, "publish", new_callable=AsyncMock) as pub,
    ):
        pval.return_value = portfolio_val
        new_bal = await credits.grant_credits(r, user_id="u1", amount=200.0)

    adj.assert_awaited_once()
    assert adj.await_args.args[2] == 200.0
    assert new_bal == 1200.0
    published = [c.args[0].type for c in pub.await_args_list]
    assert "portfolio_changed" in published
