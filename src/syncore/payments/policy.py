"""Payment policy engine (deterministic).

Decides whether a transaction may auto-execute, needs user approval, or must be
blocked, based on amount limits, vendor trust and category. This is a hard,
testable rule set - never an LLM decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..config import get_settings
from ..domain.enums import HumanCheckpointReason


class PaymentAction(str, Enum):
    AUTO = "AUTO"
    REQUIRE_USER = "REQUIRE_USER"
    BLOCK = "BLOCK"


@dataclass
class PaymentDecision:
    action: PaymentAction
    reason: str
    checkpoint_reason: HumanCheckpointReason | None = None


@dataclass
class PaymentPolicy:
    auto_limit: float
    daily_limit: float
    trusted_vendors: set[str] = field(default_factory=set)
    blocked_vendors: set[str] = field(default_factory=set)
    high_value_categories: set[str] = field(default_factory=lambda: {"electronics"})

    @classmethod
    def from_settings(cls) -> "PaymentPolicy":
        s = get_settings()
        return cls(
            auto_limit=s.payment_auto_limit,
            daily_limit=s.payment_daily_limit,
            trusted_vendors={"mock-bazaar", "mock-fresh"},
        )

    def decide(
        self, *, amount: float, vendor: str, currency: str, category: str = "grocery",
        daily_spent: float = 0.0, auto_pay_enabled: bool = True,
    ) -> PaymentDecision:
        if vendor in self.blocked_vendors:
            return PaymentDecision(PaymentAction.BLOCK, f"vendor {vendor} is blocked",
                                   HumanCheckpointReason.HIGH_RISK_TRANSACTION)
        if daily_spent + amount > self.daily_limit:
            return PaymentDecision(PaymentAction.REQUIRE_USER,
                                   "daily spending limit would be exceeded",
                                   HumanCheckpointReason.HIGH_RISK_TRANSACTION)
        if not auto_pay_enabled:
            return PaymentDecision(PaymentAction.REQUIRE_USER, "automatic payment disabled",
                                   HumanCheckpointReason.PAYMENT_AUTHENTICATION_REQUIRED)
        if category in self.high_value_categories:
            return PaymentDecision(PaymentAction.REQUIRE_USER,
                                   f"{category} always requires approval",
                                   HumanCheckpointReason.HIGH_RISK_TRANSACTION)
        if vendor not in self.trusted_vendors:
            return PaymentDecision(PaymentAction.REQUIRE_USER, f"vendor {vendor} is not trusted",
                                   HumanCheckpointReason.UNKNOWN_VENDOR)
        if amount > self.auto_limit:
            return PaymentDecision(PaymentAction.REQUIRE_USER,
                                   f"amount ₹{amount:g} exceeds auto-pay limit ₹{self.auto_limit:g}",
                                   HumanCheckpointReason.PAYMENT_AUTHENTICATION_REQUIRED)
        return PaymentDecision(PaymentAction.AUTO,
                               f"within auto-pay limit for trusted vendor {vendor}")
