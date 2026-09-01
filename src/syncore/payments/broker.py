"""PaymentBroker — the single financial execution boundary (Blueprint STEP 16/44).

The AI agent NEVER calls execute directly. Only the broker runs risk -> policy
-> provider, enforces idempotency, and handles PAYMENT_UNKNOWN via reconciliation
(never blind retry). Executes only on a policy ALLOW (fail closed).
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..domain.enums import PaymentTxnState, PolicyOutcome
from ..observability.logging import get_logger
from .control_policy import PolicyEngine
from .delegation import DelegationService
from .ledger import SpendLedger
from .models import (
    Cart,
    Delegation,
    DelegatedPaymentIntent,
    PaymentTransaction,
    PolicyDecision,
    RiskDecision,
)
from .pay_providers import PaymentProvider2, get_delegated_provider
from .risk import RiskContext, RiskEngine

logger = get_logger("syncore.payments.broker")


class BrokerResult:
    def __init__(self, decision: PolicyDecision, txn: PaymentTransaction | None):
        self.decision = decision
        self.txn = txn

    @property
    def executed(self) -> bool:
        return self.txn is not None and self.txn.state in (
            PaymentTxnState.SUCCESS, PaymentTxnState.SETTLED
        )


class AuditSink:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, event: str, payload: dict) -> None:
        self.events.append({"event": event, **payload})
        logger.info("audit %s %s", event, {k: payload[k] for k in list(payload)[:3]})


class PaymentBroker:
    def __init__(
        self,
        *,
        delegations: DelegationService,
        provider: PaymentProvider2 | None = None,
        policy: PolicyEngine | None = None,
        risk: RiskEngine | None = None,
        spend: SpendLedger | None = None,
        audit: AuditSink | None = None,
    ) -> None:
        self.delegations = delegations
        self.provider = provider or get_delegated_provider()
        self.policy = policy or PolicyEngine()
        self.risk = risk or RiskEngine()
        self.spend = spend or SpendLedger()
        self.audit = audit or AuditSink()
        self._txns: dict[str, PaymentTransaction] = {}
        self._by_idem: dict[str, str] = {}  # idempotency_key -> txn_id

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def evaluate(
        self, *, intent: DelegatedPaymentIntent, cart: Cart, cart_changed: bool = False,
        price_changed: bool = False,
    ) -> tuple[PolicyDecision, Delegation]:
        delegation = self.delegations.get(intent.delegation_id)
        if delegation is None:
            raise KeyError("unknown delegation")
        now = self._now()
        ledger = self.spend.view(intent.delegation_id, now)
        ctx = RiskContext(
            recent_txns_60s=self.spend.recent_count(intent.delegation_id, now),
            avg_recent_amount_paise=0,
            delegation_age_seconds=(now - _aware(delegation.created_at)).total_seconds(),
            cart_changed=cart_changed, price_changed=price_changed,
        )
        risk = self.risk.score(intent, cart, ctx)
        decision = self.policy.can_pay(
            delegation=delegation,
            effective_status=self.delegations.effective_status(delegation, now),
            intent=intent, cart=cart, ledger=ledger, risk=risk, now=now,
        )
        self.audit.emit("CAN_PAY", {"intent_id": intent.id, "outcome": decision.outcome.value,
                                    "rule_fired": decision.rule_fired})
        return decision, delegation

    def authorize_and_execute(
        self, *, intent: DelegatedPaymentIntent, cart: Cart, cart_changed: bool = False,
        price_changed: bool = False,
    ) -> BrokerResult:
        # Idempotency: a repeated key never creates a second charge.
        if intent.idempotency_key in self._by_idem:
            txn = self._txns[self._by_idem[intent.idempotency_key]]
            self.audit.emit("IDEMPOTENT_REPLAY", {"idempotency_key": intent.idempotency_key,
                                                  "state": txn.state.value})
            decision, _ = self.evaluate(intent=intent, cart=cart)
            return BrokerResult(decision, txn)

        decision, delegation = self.evaluate(intent=intent, cart=cart,
                                             cart_changed=cart_changed, price_changed=price_changed)
        if decision.outcome != PolicyOutcome.ALLOW:
            # Fail closed: never execute on DENY / REQUIRES_USER_AUTHORIZATION.
            return BrokerResult(decision, None)

        if not self.provider.available():
            self.audit.emit("PROVIDER_UNAVAILABLE", {"provider": self.provider.name})
            return BrokerResult(decision, None)

        txn = PaymentTransaction(
            intent_id=intent.id, delegation_id=intent.delegation_id,
            provider=self.provider.name, amount_paise=intent.amount_paise,
            currency=intent.currency, idempotency_key=intent.idempotency_key,
            state=PaymentTxnState.EXECUTING,
        )
        self._txns[txn.id] = txn
        self._by_idem[intent.idempotency_key] = txn.id
        self.audit.emit("PAYMENT_EXECUTING", {"txn_id": txn.id, "amount_paise": txn.amount_paise})

        result = self.provider.execute_payment(
            amount_paise=intent.amount_paise, currency=intent.currency,
            merchant_id=intent.merchant_id, idempotency_key=intent.idempotency_key,
        )
        txn.provider_ref = result.provider_ref

        if result.state == "SUCCESS":
            txn.state = PaymentTxnState.SETTLED
            self.spend.record(intent.delegation_id, intent.amount_paise, self._now())
            self.audit.emit("PAYMENT_SETTLED", {"txn_id": txn.id, "provider_ref": txn.provider_ref})
        elif result.state == "FAILED":
            txn.state = PaymentTxnState.FAILED
            self.audit.emit("PAYMENT_FAILED", {"txn_id": txn.id, "detail": result.detail})
        else:  # UNKNOWN — park for reconciliation, never blindly retry
            txn.state = PaymentTxnState.UNKNOWN
            self.audit.emit("PAYMENT_UNKNOWN", {"txn_id": txn.id})

        return BrokerResult(decision, txn)

    def get_txn(self, txn_id: str) -> PaymentTransaction | None:
        return self._txns.get(txn_id)

    def reconcile(self, txn_id: str) -> PaymentTransaction:
        txn = self._txns.get(txn_id)
        if txn is None:
            raise KeyError("unknown txn")
        if txn.state != PaymentTxnState.UNKNOWN:
            return txn
        status = self.provider.get_status(txn.provider_ref or "")
        if status == "SUCCESS":
            txn.state = PaymentTxnState.SETTLED
            self.spend.record(txn.delegation_id, txn.amount_paise, self._now())
            self.audit.emit("RECONCILED_SETTLED", {"txn_id": txn.id})
        else:
            txn.state = PaymentTxnState.DROPPED
            self.audit.emit("RECONCILED_DROPPED", {"txn_id": txn.id, "provider_status": status})
        return txn

    def refund(self, txn_id: str) -> PaymentTransaction:
        txn = self._txns.get(txn_id)
        if txn is None:
            raise KeyError("unknown txn")
        if txn.state != PaymentTxnState.SETTLED:
            raise ValueError("only settled transactions can be refunded")
        res = self.provider.refund(provider_ref=txn.provider_ref or "", amount_paise=txn.amount_paise)
        if res.ok:
            txn.state = PaymentTxnState.REFUNDED
            self.audit.emit("REFUNDED", {"txn_id": txn.id, "refund_ref": res.provider_ref})
        return txn


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
