"""Deterministic Risk Engine v0 (Blueprint STEP 15).

Baseline rules over agentic-spend signals -> LOW / MEDIUM / HIGH. Designed so an
ML model can later score into the same interface, but ML must never directly
execute payments. HIGH blocks; MEDIUM needs user authorization; LOW proceeds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..domain.enums import RiskLevel
from .models import Cart, DelegatedPaymentIntent, RiskDecision

_INJECTION = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"\b(buy|purchase|order)\b.*\b\d{2,}\b\s*(units|pieces|qty)", re.I),
    re.compile(r"override\s+(policy|limit|budget)", re.I),
    re.compile(r"\b(transfer|wire|send)\b.*\b(otp|pin|cvv|password)\b", re.I),
    re.compile(r"<script|drop\s+table|;--", re.I),
]

_VELOCITY_SPIKE = 5
_AMOUNT_SPIKE_RATIO = 10


@dataclass
class RiskContext:
    recent_txns_60s: int = 0
    avg_recent_amount_paise: int = 0
    delegation_age_seconds: float = 3600.0
    cart_changed: bool = False
    price_changed: bool = False


class RiskEngine:
    def score(self, intent: DelegatedPaymentIntent, cart: Cart, ctx: RiskContext) -> RiskDecision:
        names = " ".join(ln.name for ln in cart.lines)
        injection = any(p.search(names) for p in _INJECTION)
        velocity_spike = ctx.recent_txns_60s >= _VELOCITY_SPIKE
        amount_spike = (
            ctx.avg_recent_amount_paise > 0
            and intent.amount_paise >= ctx.avg_recent_amount_paise * _AMOUNT_SPIKE_RATIO
        )
        signals = {
            "injection_shape": injection,
            "recent_txns_60s": ctx.recent_txns_60s,
            "velocity_spike": velocity_spike,
            "amount_spike": amount_spike,
            "cart_changed": ctx.cart_changed,
            "price_changed": ctx.price_changed,
            "delegation_age_seconds": round(ctx.delegation_age_seconds),
        }
        if injection or ctx.cart_changed or ctx.price_changed:
            reason = ("injected instructions in product content" if injection
                      else "cart/price changed after binding")
            return RiskDecision(level=RiskLevel.HIGH, reasons=[reason], signals=signals)
        if velocity_spike or amount_spike:
            reason = "velocity spike" if velocity_spike else "amount anomaly vs history"
            return RiskDecision(level=RiskLevel.MEDIUM, reasons=[reason], signals=signals)
        return RiskDecision(level=RiskLevel.LOW, reasons=["no elevated risk"], signals=signals)
