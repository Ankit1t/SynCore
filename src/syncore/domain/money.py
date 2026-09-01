"""Integer minor-unit money (Phase 2 rule: money is NEVER floating point).

All Phase-2 financial values are integer paise (₹1 = 100 paise). Conversions
use Decimal with round-half-up so there is a single, deterministic rounding
policy across the control plane.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def to_paise(rupees: float | int | str | Decimal) -> int:
    """Convert a rupee amount to integer paise (deterministic rounding)."""
    d = Decimal(str(rupees))
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_paise(paise: int) -> Decimal:
    """Return rupees as a Decimal with 2 places (for display/serialization)."""
    return (Decimal(int(paise)) / 100).quantize(Decimal("0.01"))


def format_inr(paise: int) -> str:
    return f"₹{from_paise(paise):.2f}"


def line_total_paise(unit_price_paise: int, quantity: int) -> int:
    """Exact line total in paise. Quantity is an integer count of units/packs."""
    if unit_price_paise < 0 or quantity < 0:
        raise ValueError("negative money/quantity not allowed")
    return int(unit_price_paise) * int(quantity)


def sum_paise(values: list[int]) -> int:
    return int(sum(int(v) for v in values))
