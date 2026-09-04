"""Agentic checkout ("one door") — agent -> AP2 -> CAN_PAY -> settle/block."""

from __future__ import annotations

from syncore.payments.agentic_checkout import AgenticCheckoutService

TEXT = "1kg aloo, 100g mirch aur 2 Maggi under 500"


def test_allow_path_settles_with_mock_and_builds_ap2_chain():
    svc = AgenticCheckoutService()
    r = svc.checkout(text=TEXT)
    assert r["stage"] == "SETTLED"                       # mock provider settles autonomously
    assert r["decision"]["outcome"] == "ALLOW"
    chain = r["ap2_mandates"]
    assert set(chain.keys()) == {"intent_mandate", "cart_mandate", "payment_mandate"}
    # AP2 cart mandate binds to the very cart the gate evaluated.
    assert chain["cart_mandate"]["cart_hash"] == r["cart"]["cart_hash"]
    assert r["txn"]["state"].endswith("SETTLED")


def test_low_per_txn_limit_is_blocked_by_the_gate():
    svc = AgenticCheckoutService()
    r = svc.checkout(text=TEXT, per_txn_paise=1000)      # ₹10 cap, basket is more
    assert r["stage"] == "BLOCKED"
    assert r["decision"]["outcome"] == "DENY"
    assert r["blocked_by"] == "PER_TXN_LIMIT"
    assert r.get("txn") is None                          # nothing executed
    # A PaymentMandate is still minted, recording the DENY verdict (evidence).
    assert r["ap2_mandates"]["payment_mandate"]["policy_outcome"] == "DENY"


def test_checks_are_the_deterministic_ordered_gate():
    svc = AgenticCheckoutService()
    r = svc.checkout(text=TEXT)
    names = [c["name"] for c in r["decision"]["checks"]]
    # first checks are always identity/state before any money math
    assert names[0] == "AGENT_IDENTITY"
    assert "CART_BINDING" in names
    assert "PER_TXN_LIMIT" in names
