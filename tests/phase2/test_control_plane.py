"""Phase 2 — money, binding, policy, broker, reconciliation, webhooks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from syncore.domain.enums import PaymentTxnState, PolicyOutcome
from syncore.domain.money import from_paise, line_total_paise, to_paise
from syncore.payments.binding import compute_cart_hash, price_cart
from syncore.payments.control_plane import Phase2ControlPlane
from syncore.payments.models import CartLine, SpendingLimits
from syncore.payments.webhooks import WebhookProcessor, sign_payload


def _limits():
    return SpendingLimits(per_txn_paise=to_paise(500), daily_paise=to_paise(1500),
                          monthly_paise=to_paise(15000))


def _lines():
    return [
        CartLine(sku="potato", name="Potato 1kg", quantity=1, unit_price_paise=to_paise(40),
                 line_total_paise=to_paise(40)),
        CartLine(sku="maggi", name="Maggi 2-pack", quantity=2, unit_price_paise=to_paise(14),
                 line_total_paise=to_paise(28)),
    ]


def _harness(idem="ik-1", merchants=("zepto",)):
    cp = Phase2ControlPlane()
    d = cp.create_delegation(user_id="u", agent_id="syncore_agent", limits=_limits(),
                             allowed_merchants=list(merchants))
    cart = cp.build_cart(merchant_id="zepto", lines=_lines(), delivery_paise=to_paise(20))
    intent, res = cp.create_payment_intent(user_id="u", agent_id="syncore_agent",
                                           delegation_id=d.id, cart=cart, idempotency_key=idem)
    return cp, d, cart, intent, res


# --- money -------------------------------------------------------------------
def test_money_is_integer_paise():
    assert to_paise(427) == 42700
    assert to_paise("4.27") == 427
    assert line_total_paise(to_paise(14), 2) == 2800
    assert str(from_paise(42700)) == "427.00"


# --- binding -----------------------------------------------------------------
def test_cart_hash_changes_on_amount_qty_merchant():
    c1 = price_cart(merchant_id="zepto", merchant_category="GROCERY", lines=_lines(),
                    delivery_paise=to_paise(20))
    # quantity change
    lines2 = _lines()
    lines2[0].quantity = 2
    lines2[0].line_total_paise = line_total_paise(lines2[0].unit_price_paise, 2)
    c2 = price_cart(merchant_id="zepto", merchant_category="GROCERY", lines=lines2,
                    delivery_paise=to_paise(20))
    assert c1.cart_hash != c2.cart_hash
    # merchant change
    c3 = price_cart(merchant_id="amazon", merchant_category="GROCERY", lines=_lines(),
                    delivery_paise=to_paise(20))
    assert c1.cart_hash != c3.cart_hash


def test_budget_uses_final_total_not_subtotal():
    c = price_cart(merchant_id="zepto", merchant_category="GROCERY", lines=_lines(),
                   delivery_paise=to_paise(20))
    assert c.subtotal_paise == to_paise(68)          # 40 + 28
    assert c.final_total_paise == to_paise(88)         # + delivery 20
    assert c.cart_hash == compute_cart_hash(c)


# --- policy + broker ---------------------------------------------------------
def test_allow_then_execute_settles_once():
    cp, d, cart, intent, res = _harness()
    assert res.decision.outcome == PolicyOutcome.ALLOW
    ex = cp.execute(intent.id)
    assert ex.txn.state == PaymentTxnState.SETTLED
    assert cp.broker.provider.total_charges() == 1


def test_idempotent_execute_no_double_charge():
    cp, d, cart, intent, res = _harness(idem="ik-dup")
    first = cp.execute(intent.id)
    second = cp.execute(intent.id)
    assert first.txn.state == PaymentTxnState.SETTLED
    assert second.txn.id == first.txn.id
    assert cp.broker.provider.total_charges() == 1


def test_over_per_txn_limit_denied_not_executed():
    cp = Phase2ControlPlane()
    d = cp.create_delegation(user_id="u", agent_id="syncore_agent", limits=_limits(),
                             allowed_merchants=["zepto"])
    big = [CartLine(sku="tv", name="TV", quantity=1, unit_price_paise=to_paise(60000),
                    line_total_paise=to_paise(60000))]
    cart = cp.build_cart(merchant_id="zepto", lines=big)
    intent, res = cp.create_payment_intent(user_id="u", agent_id="syncore_agent",
                                           delegation_id=d.id, cart=cart, idempotency_key="ik-big")
    assert res.decision.outcome == PolicyOutcome.DENY
    assert res.decision.rule_fired == "PER_TXN_LIMIT"
    ex = cp.execute(intent.id)
    assert ex.executed is False
    assert cp.broker.provider.total_charges() == 0


def test_timeout_unknown_then_reconcile_settles():
    cp, d, cart, intent, res = _harness(idem="ik-unk")
    cp.broker.provider.script("UNKNOWN")
    ex = cp.execute(intent.id)
    assert ex.txn.state == PaymentTxnState.UNKNOWN
    txn = cp.broker.reconcile(ex.txn.id)
    assert txn.state == PaymentTxnState.SETTLED
    assert cp.broker.provider.total_charges() == 1


def test_failed_payment_no_charge_and_terminal():
    cp, d, cart, intent, res = _harness(idem="ik-fail")
    cp.broker.provider.script("FAILED")
    ex = cp.execute(intent.id)
    assert ex.txn.state == PaymentTxnState.FAILED
    assert cp.broker.provider.total_charges() == 0


def test_refund_only_after_settled():
    cp, d, cart, intent, res = _harness(idem="ik-refund")
    ex = cp.execute(intent.id)
    txn = cp.broker.refund(ex.txn.id)
    assert txn.state == PaymentTxnState.REFUNDED


# --- webhooks ----------------------------------------------------------------
def test_webhook_valid_then_replay_rejected():
    wp = WebhookProcessor(secret="s3cr3t")
    payload = b'{"event":"PaymentSucceeded"}'
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    sig = sign_payload("s3cr3t", ts, payload)
    ok, _ = wp.process(payload=payload, signature=sig, timestamp=ts, event_id="evt_1", event_type="PaymentSucceeded")
    assert ok
    dup, reason = wp.process(payload=payload, signature=sig, timestamp=ts, event_id="evt_1", event_type="PaymentSucceeded")
    assert not dup and "duplicate" in reason


def test_webhook_bad_signature_rejected():
    wp = WebhookProcessor(secret="s3cr3t")
    payload = b'{"event":"x"}'
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    ok, reason = wp.process(payload=payload, signature="deadbeef", timestamp=ts, event_id="e2", event_type="x")
    assert not ok and "signature" in reason


def test_webhook_stale_timestamp_rejected():
    wp = WebhookProcessor(secret="s3cr3t")
    payload = b'{"event":"x"}'
    old = str(int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()))
    sig = sign_payload("s3cr3t", old, payload)
    ok, reason = wp.process(payload=payload, signature=sig, timestamp=old, event_id="e3", event_type="x")
    assert not ok and "timestamp" in reason
