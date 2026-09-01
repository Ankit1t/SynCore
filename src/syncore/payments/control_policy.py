"""Delegated-authorization Policy Engine — CAN_PAY (Blueprint STEP 14/19).

Pure, deterministic function of (delegation, intent, cart, ledger, risk). Twelve
checks in a fixed order; stops at the first non-pass; fails closed (any error =>
DENY). The LLM never implements this. Money is integer paise throughout.

Outcomes: ALLOW | DENY | REQUIRES_USER_AUTHORIZATION, each with machine-readable
reasons and per-check evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..domain.enums import DelegationStatus, PolicyOutcome, RiskLevel
from .models import (
    Cart,
    Delegation,
    DelegatedPaymentIntent,
    PolicyCheck,
    PolicyDecision,
    RiskDecision,
)
from .ledger import LedgerView


class PolicyEngine:
    def can_pay(
        self,
        *,
        delegation: Delegation,
        effective_status: DelegationStatus,
        intent: DelegatedPaymentIntent,
        cart: Cart,
        ledger: LedgerView,
        risk: RiskDecision,
        now: datetime | None = None,
    ) -> PolicyDecision:
        now = now or datetime.now(timezone.utc)
        checks: list[PolicyCheck] = []

        def run(name: str, ok: bool, outcome_if_fail: PolicyOutcome, detail: str) -> bool:
            checks.append(PolicyCheck(name=name, passed=ok,
                                      outcome=None if ok else outcome_if_fail, detail=detail))
            return ok

        try:
            D, DENY, ASK = PolicyOutcome, PolicyOutcome.DENY, PolicyOutcome.REQUIRES_USER_AUTHORIZATION

            order = [
                ("AGENT_IDENTITY", intent.agent_id == delegation.agent_id, DENY,
                 "agent does not match delegation"),
                ("DELEGATION_STATE", effective_status == DelegationStatus.ACTIVE, DENY,
                 f"delegation {effective_status.value}"),
                ("PURPOSE", intent.purpose == delegation.purpose, DENY,
                 f"purpose {intent.purpose} != {delegation.purpose}"),
                ("MERCHANT_SCOPE",
                 (not delegation.allowed_merchants) or (intent.merchant_id in delegation.allowed_merchants),
                 DENY, f"merchant {intent.merchant_id} not allowed"),
                ("CATEGORY_SCOPE", intent.merchant_category in delegation.allowed_categories, DENY,
                 f"category {intent.merchant_category} out of scope"),
                ("CURRENCY", intent.currency == delegation.currency, DENY,
                 f"currency {intent.currency} != {delegation.currency}"),
                ("CART_BINDING",
                 intent.cart_hash == cart.cart_hash and intent.amount_paise == cart.final_total_paise,
                 DENY, "cart_hash/amount not bound to the fresh cart"),
                ("PER_TXN_LIMIT", intent.amount_paise <= delegation.limits.per_txn_paise, DENY,
                 f"amount {intent.amount_paise} over per-txn {delegation.limits.per_txn_paise}"),
                ("DAILY_LIMIT",
                 ledger.spent_daily_paise + intent.amount_paise <= delegation.limits.daily_paise, DENY,
                 "daily limit exceeded"),
                ("MONTHLY_LIMIT",
                 ledger.spent_monthly_paise + intent.amount_paise <= delegation.limits.monthly_paise, DENY,
                 "monthly limit exceeded"),
            ]

            for name, ok, fail_outcome, detail in order:
                if not run(name, ok, fail_outcome, detail):
                    return PolicyDecision(outcome=fail_outcome, rule_fired=name, checks=checks,
                                          risk=risk, reasons=[detail])

            # Risk gate last: HIGH denies, MEDIUM requires user authorization.
            if risk.level == RiskLevel.HIGH:
                run("RISK_GATE", False, DENY, "; ".join(risk.reasons))
                return PolicyDecision(outcome=DENY, rule_fired="RISK_GATE", checks=checks,
                                      risk=risk, reasons=risk.reasons)
            if risk.level == RiskLevel.MEDIUM:
                run("RISK_GATE", False, ASK, "; ".join(risk.reasons))
                return PolicyDecision(outcome=ASK, rule_fired="RISK_GATE", checks=checks,
                                      risk=risk, reasons=risk.reasons)
            run("RISK_GATE", True, ASK, "risk low")

            return PolicyDecision(outcome=PolicyOutcome.ALLOW, rule_fired=None, checks=checks,
                                  risk=risk, reasons=["all checks passed"])
        except Exception as exc:  # noqa: BLE001 - fail closed
            checks.append(PolicyCheck(name="ENGINE_ERROR", passed=False,
                                      outcome=PolicyOutcome.DENY, detail=str(exc)))
            return PolicyDecision(outcome=PolicyOutcome.DENY, rule_fired="ENGINE_ERROR",
                                  checks=checks, risk=risk, reasons=[f"engine error: {exc}"])
