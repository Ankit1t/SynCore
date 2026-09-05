"""AP2 mandate layer — mapping, evidence chain, and tamper detection."""

from __future__ import annotations

from syncore.ap2 import build_mandate_chain
from syncore.domain.money import to_paise
from syncore.payments.control_plane import Phase2ControlPlane
from syncore.payments.models import CartLine, SpendingLimits


def _harness():
    cp = Phase2ControlPlane()
    d = cp.create_delegation(
        user_id="u", agent_id="syncore_agent",
        limits=SpendingLimits(per_txn_paise=to_paise(500), daily_paise=to_paise(1500),
                              monthly_paise=to_paise(15000)),
        allowed_categories=["GROCERY"], allowed_merchants=[],
    )
    lines = [
        CartLine(sku="potato", name="Potato 1kg", quantity=1, unit_price_paise=to_paise(40),
                 line_total_paise=to_paise(40), category="GROCERY"),
        CartLine(sku="maggi", name="Maggi 2-pack", quantity=2, unit_price_paise=to_paise(14),
                 line_total_paise=to_paise(28), category="GROCERY"),
    ]
    cart = cp.build_cart(merchant_id="zepto", merchant_category="GROCERY", lines=lines,
                         delivery_paise=to_paise(20))
    intent, res = cp.create_payment_intent(user_id="u", agent_id="syncore_agent",
                                           delegation_id=d.id, cart=cart, idempotency_key="ap2-ik")
    return cp, d, cart, intent, res


def test_chain_maps_all_three_mandates():
    _, d, cart, intent, res = _harness()
    chain = build_mandate_chain(delegation=d, cart=cart, intent=intent, decision=res.decision,
                                natural_language_intent="grocery run")
    assert chain.intent_mandate.mandate_type == "IntentMandate"
    assert chain.cart_mandate.mandate_type == "CartMandate"
    assert chain.payment_mandate is not None
    assert chain.payment_mandate.mandate_type == "PaymentMandate"


def test_cart_mandate_binds_to_the_same_cart_hash():
    _, d, cart, intent, res = _harness()
    chain = build_mandate_chain(delegation=d, cart=cart, intent=intent, decision=res.decision)
    assert chain.cart_mandate.cart_hash == cart.cart_hash
    assert chain.cart_mandate.total_paise == cart.final_total_paise


def test_evidence_chain_links_and_verifies():
    _, d, cart, intent, res = _harness()
    chain = build_mandate_chain(delegation=d, cart=cart, intent=intent, decision=res.decision)
    # intent -> cart -> payment digests are linked
    assert chain.cart_mandate.intent_mandate_ref == chain.intent_mandate.content_digest
    assert chain.payment_mandate.cart_mandate_ref == chain.cart_mandate.content_digest
    assert chain.verify() is True


def test_tampering_breaks_the_chain():
    _, d, cart, intent, res = _harness()
    chain = build_mandate_chain(delegation=d, cart=cart, intent=intent, decision=res.decision)
    # Mutate a bound amount without re-signing -> digest no longer matches.
    chain.cart_mandate.total_paise += 100
    assert chain.verify() is False


def test_intent_mandate_carries_limits_from_delegation():
    _, d, cart, intent, res = _harness()
    chain = build_mandate_chain(delegation=d, cart=cart, intent=intent, decision=res.decision)
    im = chain.intent_mandate
    assert im.per_txn_paise == d.limits.per_txn_paise
    assert "GROCERY" in im.allowed_categories
    assert im.currency == "INR"


# --- Ed25519 signing ---------------------------------------------------------
def test_mandates_are_ed25519_signed():
    _, d, cart, intent, res = _harness()
    chain = build_mandate_chain(delegation=d, cart=cart, intent=intent, decision=res.decision)
    assert chain.intent_mandate.signature_alg == "Ed25519"
    assert len(chain.intent_mandate.signature) == 128  # 64-byte sig hex-encoded
    assert chain.intent_mandate.signature_valid() is True
    assert chain.cart_mandate.signature_valid() is True
    assert chain.payment_mandate.signature_valid() is True


def test_signature_breaks_when_amount_tampered():
    _, d, cart, intent, res = _harness()
    chain = build_mandate_chain(delegation=d, cart=cart, intent=intent, decision=res.decision)
    chain.cart_mandate.total_paise += 1
    assert chain.cart_mandate.signature_valid() is False
    assert chain.verify() is False


def test_verify_report_shape():
    _, d, cart, intent, res = _harness()
    chain = build_mandate_chain(delegation=d, cart=cart, intent=intent, decision=res.decision)
    rep = chain.verify_report()
    assert rep["chain_valid"] is True
    for key in ("intent_mandate", "cart_mandate", "payment_mandate"):
        assert rep[key]["digest_ok"] and rep[key]["link_ok"] and rep[key]["signature_ok"]


def test_verify_mandate_payload_accepts_good_chain_rejects_tampered():
    from syncore.ap2 import verify_mandate_payload

    _, d, cart, intent, res = _harness()
    chain = build_mandate_chain(delegation=d, cart=cart, intent=intent, decision=res.decision)
    good = chain.model_dump(mode="json")
    assert verify_mandate_payload(good)["ok"] is True

    bad = chain.model_dump(mode="json")
    bad["cart_mandate"]["total_paise"] += 500
    assert verify_mandate_payload(bad)["ok"] is False
