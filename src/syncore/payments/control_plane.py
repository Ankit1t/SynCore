"""Phase-2 control-plane facade: wires delegation, broker, webhooks and
persistence behind one object the API and demo call. In-memory services are the
in-process source of truth; delegations and transactions are also persisted to
the database (best-effort, never fatal to the request).
"""

from __future__ import annotations

from datetime import datetime

from ..config import get_settings
from ..domain.enums import OrderStatus
from ..observability.logging import get_logger
from .binding import price_cart
from .broker import BrokerResult, PaymentBroker
from .delegation import DelegationService
from .ledger import SpendLedger
from .models import (
    Cart,
    CartLine,
    Delegation,
    DelegatedPaymentIntent,
    Receipt,
    SpendingLimits,
)
from .receipts import build_receipt, verify_order
from .webhooks import WebhookProcessor

logger = get_logger("syncore.payments.control_plane")


class Phase2ControlPlane:
    def __init__(self) -> None:
        s = get_settings()
        self.delegations = DelegationService()
        self.spend = SpendLedger()
        self.broker = PaymentBroker(delegations=self.delegations, spend=self.spend)
        self.webhooks = WebhookProcessor(secret=s.webhook_secret)
        self._intents: dict[str, tuple[DelegatedPaymentIntent, Cart]] = {}

    # --- delegations --------------------------------------------------------
    def create_delegation(self, **kwargs) -> Delegation:
        d = self.delegations.create(**kwargs)
        self._persist_delegation(d)
        return d

    def _persist_delegation(self, d: Delegation) -> None:
        try:
            from ..db.base import session_scope
            from ..db.tables import DelegationRow

            with session_scope() as sess:
                if sess.get(DelegationRow, d.id):
                    row = sess.get(DelegationRow, d.id)
                    row.status = d.status.value
                    row.version = d.version
                else:
                    sess.add(DelegationRow(
                        id=d.id, user_id=d.user_id, agent_id=d.agent_id, purpose=d.purpose,
                        status=d.status.value, version=d.version,
                        per_txn_paise=d.limits.per_txn_paise, daily_paise=d.limits.daily_paise,
                        monthly_paise=d.limits.monthly_paise, currency=d.currency,
                        artifact=d.model_dump(mode="json"), created_at=d.created_at,
                        expires_at=d.expires_at,
                    ))
        except Exception as exc:  # noqa: BLE001 - persistence never breaks the request
            logger.error("delegation persist failed: %s", exc)

    # --- payment intents ----------------------------------------------------
    def build_cart(self, *, merchant_id: str, lines: list[CartLine], **fees) -> Cart:
        return price_cart(merchant_id=merchant_id, merchant_category=fees.pop("merchant_category", "GROCERY"),
                          lines=lines, **fees)

    def create_payment_intent(
        self, *, user_id: str, agent_id: str, delegation_id: str, cart: Cart,
        idempotency_key: str, order_id: str | None = None,
    ) -> tuple[DelegatedPaymentIntent, BrokerResult]:
        intent = DelegatedPaymentIntent(
            user_id=user_id, agent_id=agent_id, delegation_id=delegation_id, order_id=order_id,
            merchant_id=cart.merchant_id, merchant_category=cart.merchant_category,
            amount_paise=cart.final_total_paise, currency=cart.currency, purpose="GROCERY",
            cart_hash=cart.cart_hash, idempotency_key=idempotency_key,
        )
        self._intents[intent.id] = (intent, cart)
        decision, _ = self.broker.evaluate(intent=intent, cart=cart)
        return intent, BrokerResult(decision, None)

    def execute(self, intent_id: str, *, cart_changed: bool = False, price_changed: bool = False) -> BrokerResult:
        intent, cart = self._require_intent(intent_id)
        result = self.broker.authorize_and_execute(
            intent=intent, cart=cart, cart_changed=cart_changed, price_changed=price_changed
        )
        if result.txn is not None:
            self._persist_txn(result)
        return result

    def _persist_txn(self, result: BrokerResult) -> None:
        txn = result.txn
        if txn is None:
            return
        try:
            from ..db.base import session_scope
            from ..db.tables import PaymentTransactionRow

            with session_scope() as sess:
                existing = sess.get(PaymentTransactionRow, txn.id)
                if existing:
                    existing.state = txn.state.value
                    existing.provider_ref = txn.provider_ref
                else:
                    sess.add(PaymentTransactionRow(
                        id=txn.id, intent_id=txn.intent_id, delegation_id=txn.delegation_id,
                        state=txn.state.value, provider=txn.provider, provider_ref=txn.provider_ref,
                        amount_paise=txn.amount_paise, currency=txn.currency,
                        idempotency_key=txn.idempotency_key, created_at=txn.created_at,
                    ))
        except Exception as exc:  # noqa: BLE001
            logger.error("txn persist failed: %s", exc)

    def receipt(self, intent_id: str, *, merchant_confirmed: bool = True) -> Receipt | None:
        pair = self._intents.get(intent_id)
        if not pair:
            return None
        intent, cart = pair
        # find the txn for this intent
        txn = next((t for t in self.broker._txns.values() if t.intent_id == intent_id), None)  # noqa: SLF001
        if txn is None:
            return None
        order_status = verify_order(cart=cart, txn=txn, merchant_confirmed=merchant_confirmed)
        return build_receipt(cart=cart, txn=txn, order_status=order_status, order_id=intent.order_id)

    def _require_intent(self, intent_id: str) -> tuple[DelegatedPaymentIntent, Cart]:
        pair = self._intents.get(intent_id)
        if not pair:
            raise KeyError("unknown payment intent")
        return pair


_cp: Phase2ControlPlane | None = None


def get_control_plane() -> Phase2ControlPlane:
    global _cp
    if _cp is None:
        _cp = Phase2ControlPlane()
    return _cp
