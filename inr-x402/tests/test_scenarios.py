"""The 6 demo scenarios, end-to-end over HTTP against the live stack."""
from __future__ import annotations

import httpx


def _get_invoice(stack, path: str) -> dict:
    r = httpx.get(f"{stack.merchant_base}{path}", timeout=5.0)
    assert r.status_code == 402, r.text
    return r.json()


# 1) HAPPY PATH ---------------------------------------------------------------
def test_happy_path(new_agent, stack):
    agent, agent_id, mandate = new_agent()
    result = agent.pay("/api/summarize")

    assert result.ok is True
    assert result.status == "settled"
    assert result.receipt is not None
    assert result.receipt["status"] == "settled"
    assert result.receipt["amountPaise"] == 50
    assert result.receipt["utrn"].startswith("BK")
    assert result.receipt_verified is True         # facilitator signature checks out
    assert result.data["resource"] == "summarize"  # content delivered

    # Ledger shows the double-entry pair for this nonce.
    entries = stack.ledger(result.nonce)
    types = sorted(e["type"] for e in entries)
    assert types == ["credit", "debit"]


# 2) POLICY REJECT (over per-txn limit) --------------------------------------
def test_policy_reject_over_per_txn_limit(new_agent):
    # Mandate caps per-txn at 10 paise, but summarize costs 50.
    agent, _, _ = new_agent(per_txn=10, daily=5000)
    result = agent.pay("/api/summarize")

    assert result.ok is False
    assert result.status == "rejected"
    assert result.reason == "over_per_txn_limit"
    assert result.receipt is None


# 3) REPLAY -------------------------------------------------------------------
def test_replay_detected(new_agent, stack):
    agent, agent_id, mandate = new_agent()

    # Build ONE signed intent and present the SAME X-PAYMENT header twice.
    invoice = _get_invoice(stack, "/api/summarize")
    intent = agent._build_intent(invoice)
    header = agent._payment_header(intent)

    first = httpx.get(f"{stack.merchant_base}/api/summarize",
                      headers={"X-PAYMENT": header}, timeout=5.0)
    assert first.status_code == 200, first.text

    second = httpx.get(f"{stack.merchant_base}/api/summarize",
                       headers={"X-PAYMENT": header}, timeout=5.0)
    assert second.status_code == 402
    assert second.json()["reason"] == "replay_detected"


# 4) BANK DECLINE -------------------------------------------------------------
def test_bank_decline_graceful(new_agent, stack):
    stack.set_fail_rate(1.0)   # force every debit to decline
    try:
        agent, _, _ = new_agent()
        result = agent.pay("/api/summarize")

        assert result.ok is False
        assert result.status == "rejected"
        assert result.reason == "bank_declined"
        assert result.attempts == 2      # tried once, retried once with fresh nonce
    finally:
        stack.set_fail_rate(0.0)         # restore for other tests


# 5) REVERSAL -----------------------------------------------------------------
def test_reversal_within_window_and_idempotent(new_agent, stack):
    agent, _, _ = new_agent()
    result = agent.pay("/api/summarize")
    assert result.ok and result.status == "settled"
    nonce = result.nonce

    rev = httpx.post(f"{stack.facilitator_url}/reverse",
                     json={"nonce": nonce}, timeout=5.0).json()
    assert rev["ok"] is True
    assert rev["receipt"]["status"] == "reversed"

    # Ledger now carries a reversal entry alongside the debit/credit pair.
    types = sorted(e["type"] for e in stack.ledger(nonce))
    assert "reversal" in types

    # Second reverse is a no-op (idempotent).
    rev2 = httpx.post(f"{stack.facilitator_url}/reverse",
                      json={"nonce": nonce}, timeout=5.0).json()
    assert rev2["ok"] is True
    assert rev2.get("note") == "already_reversed"
    # Exactly one reversal row despite two reverse calls.
    reversal_rows = [e for e in stack.ledger(nonce) if e["type"] == "reversal"]
    assert len(reversal_rows) == 1


# 6) RECOVERY (dropped 200 response) -----------------------------------------
def test_receipt_recovery_after_dropped_response(new_agent, stack):
    agent, _, _ = new_agent()
    # simulate_timeout_once fires the settle request, drops the response, then
    # recovers via GET /receipt/{nonce}.
    result = agent.pay("/api/summarize", simulate_timeout_once=True)

    assert result.ok is True
    assert result.status == "recovered"
    assert result.receipt["status"] == "settled"
    assert result.receipt_verified is True

    # Debit happened exactly once (no double charge on recovery).
    debit_rows = [e for e in stack.ledger(result.nonce) if e["type"] == "debit"]
    assert len(debit_rows) == 1
