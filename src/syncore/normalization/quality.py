"""Data-quality validation for scraped/extracted offers.

Never blindly trust extracted values. Flags impossible prices, missing
quantities, invalid units, malformed ratings, impossible discounts, etc.
Returns a list of issues; callers decide whether to reject or downrank.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.models import Offer


@dataclass
class ValidationResult:
    ok: bool
    issues: list[str] = field(default_factory=list)
    confidence: float = 1.0


def validate_offer(offer: Offer) -> ValidationResult:
    issues: list[str] = []
    confidence = 1.0

    if offer.price <= 0:
        issues.append("non-positive price")
    if offer.price > 1_000_000:
        issues.append("implausibly high price")
    if offer.mrp is not None and offer.mrp > 0 and offer.price > offer.mrp * 1.05:
        # small tolerance for rounding; price should not exceed MRP
        issues.append("price exceeds MRP")
    if offer.quantity is None or offer.quantity.value <= 0:
        issues.append("missing or invalid quantity")
    if offer.product.rating is not None and not (0 <= offer.product.rating <= 5):
        issues.append("rating out of range")
    if offer.discount < 0:
        issues.append("negative discount")
    if offer.mrp and offer.discount > offer.mrp:
        issues.append("discount exceeds MRP")
    if offer.currency not in {"INR", "USD", "EUR", "GBP"}:
        issues.append(f"unexpected currency {offer.currency}")

    if issues:
        confidence = max(0.0, 1.0 - 0.25 * len(issues))

    # Hard-reject conditions (data unusable) vs soft flags.
    hard = {"non-positive price", "missing or invalid quantity"}
    ok = not (hard & set(issues))
    return ValidationResult(ok=ok, issues=issues, confidence=confidence)
