"""Provider capability matrix (Blueprint STEP 32/45).

Capabilities are DECLARED, never assumed. The orchestrator checks them before
attempting an operation; a missing capability yields a typed result, never a
fabricated one.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ProviderCapabilities:
    search: bool = False
    product: bool = False
    price: bool = False
    availability: bool = False
    offers: bool = False
    delivery: bool = False
    cart: bool = False
    checkout: bool = False
    order: bool = False
    payment: bool = False
    requires_credentials: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
