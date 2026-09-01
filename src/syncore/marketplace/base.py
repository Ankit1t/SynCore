"""Abstract marketplace adapter and cart/checkout value objects.

Every marketplace/source implements this interface. This is what keeps the
system multi-marketplace ready and free of scattered site-specific code.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

from ..domain.models import Offer


@dataclass
class RemoteCartLine:
    sku: str
    title: str
    unit_price: float
    quantity: int


@dataclass
class RemoteCart:
    """The marketplace's own view of a cart (source of truth for checkout)."""

    cart_id: str
    marketplace: str
    lines: list[RemoteCartLine] = field(default_factory=list)
    delivery_fee: float = 0.0
    platform_fee: float = 0.0
    discount: float = 0.0
    currency: str = "INR"

    @property
    def items_subtotal(self) -> float:
        return round(sum(line.unit_price * line.quantity for line in self.lines), 2)

    @property
    def total(self) -> float:
        return round(self.items_subtotal + self.delivery_fee + self.platform_fee - self.discount, 2)


@dataclass
class RemoteCheckout:
    checkout_id: str
    cart_id: str
    marketplace: str
    vendor: str
    final_total: float
    currency: str = "INR"
    delivery_eta_minutes: int | None = None


@dataclass
class RemoteOrder:
    external_order_id: str
    marketplace: str
    vendor: str
    total: float
    currency: str = "INR"
    delivery_eta_minutes: int | None = None
    confirmed: bool = True


@dataclass
class Fees:
    """Basket-level fees estimated for a given items subtotal."""

    delivery_fee: float = 0.0
    platform_fee: float = 0.0
    discount: float = 0.0


class BaseMarketplaceAdapter(abc.ABC):
    """Interface implemented by every marketplace/source adapter."""

    name: str = "base"
    supports_live_execution: bool = False

    # ---- Discovery / extraction -------------------------------------------
    @abc.abstractmethod
    def search_products(self, query: str, *, limit: int = 20) -> list[Offer]:
        """Return offers matching a query (already normalized)."""

    @abc.abstractmethod
    def get_product(self, source_product_id: str) -> Offer | None:
        """Fetch a single offer by its marketplace product id."""

    # ---- Execution (cart / checkout / order) ------------------------------
    @abc.abstractmethod
    def create_cart(self, session_id: str) -> RemoteCart:
        ...

    @abc.abstractmethod
    def add_to_cart(self, cart_id: str, source_product_id: str, quantity: int) -> RemoteCart:
        ...

    @abc.abstractmethod
    def get_cart(self, cart_id: str) -> RemoteCart:
        ...

    @abc.abstractmethod
    def get_checkout(self, cart_id: str) -> RemoteCheckout:
        """Return the authoritative checkout total (may differ from search price)."""

    @abc.abstractmethod
    def place_order(self, checkout_id: str, *, payment_reference: str) -> RemoteOrder:
        """Finalize the order. Requires an already-authorized payment reference."""

    # ---- Economics --------------------------------------------------------
    def estimate_fees(self, items_subtotal: float) -> Fees:
        """Estimate basket-level fees for a subtotal (delivery, platform, coupon).

        Used by the optimizer to reason about basket-level economics before a
        cart exists. Adapters should mirror their real fee rules here.
        """
        return Fees()

    # ---- Health -----------------------------------------------------------
    def healthy(self) -> bool:
        return True
