"""Browser executor interface + deterministic mock implementation.

Golden rule: never blindly click. After every important action, verify the
resulting state before continuing (spec section 18).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

from ..domain.errors import CartVerificationError
from ..domain.models import Cart, CartItem, CheckoutSession, Offer, new_id
from ..marketplace.base import BaseMarketplaceAdapter, RemoteCart
from ..observability.logging import get_logger

logger = get_logger("syncore.browser")


@dataclass
class BrowserSession:
    id: str
    user_id: str
    marketplace: str
    cart_id: str | None = None
    events: list[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.events.append(msg)
        logger.debug("browser[%s] %s", self.id[:8], msg)


class BrowserExecutor(abc.ABC):
    """High-level browser automation surface (isolated per user)."""

    @abc.abstractmethod
    def start_session(self, user_id: str) -> BrowserSession: ...

    @abc.abstractmethod
    def search(self, query: str) -> list[Offer]: ...

    @abc.abstractmethod
    def add_to_cart(self, source_product_id: str, quantity: int) -> RemoteCart: ...

    @abc.abstractmethod
    def open_cart(self) -> Cart: ...

    @abc.abstractmethod
    def open_checkout(self) -> CheckoutSession: ...

    @abc.abstractmethod
    def close(self) -> None: ...


class MockBrowserExecutor(BrowserExecutor):
    """Simulates a browser by driving a marketplace adapter, with real state
    verification after each mutating action."""

    def __init__(self, adapter: BaseMarketplaceAdapter):
        self._adapter = adapter
        self._session: BrowserSession | None = None

    @property
    def session(self) -> BrowserSession:
        if self._session is None:
            raise CartVerificationError("browser session not started")
        return self._session

    def start_session(self, user_id: str) -> BrowserSession:
        session = BrowserSession(id=new_id(), user_id=user_id, marketplace=self._adapter.name)
        remote = self._adapter.create_cart(session.id)
        session.cart_id = remote.cart_id
        session.log(f"session started; cart={remote.cart_id}")
        self._session = session
        return session

    def search(self, query: str) -> list[Offer]:
        self.session.log(f"search '{query}'")
        return self._adapter.search_products(query)

    def add_to_cart(self, source_product_id: str, quantity: int) -> RemoteCart:
        assert self.session.cart_id
        before = self._adapter.get_cart(self.session.cart_id)
        before_qty = _sku_qty(before, source_product_id)

        remote = self._adapter.add_to_cart(self.session.cart_id, source_product_id, quantity)

        # Verify: the SKU exists and its quantity increased by exactly `quantity`.
        after_qty = _sku_qty(remote, source_product_id)
        if after_qty != before_qty + quantity:
            raise CartVerificationError(
                "add_to_cart did not update cart as expected",
                details={"sku": source_product_id, "before": before_qty,
                         "after": after_qty, "expected_delta": quantity},
            )
        self.session.log(f"added {quantity}x {source_product_id} (qty {before_qty}->{after_qty})")
        return remote

    def open_cart(self) -> Cart:
        assert self.session.cart_id
        remote = self._adapter.get_cart(self.session.cart_id)
        return _to_domain_cart(remote, self.session.id)

    def verify_cart(self, expected: dict[str, int]) -> tuple[bool, list[str]]:
        """Check the live cart against expected {sku: quantity}."""
        assert self.session.cart_id
        remote = self._adapter.get_cart(self.session.cart_id)
        issues: list[str] = []
        for sku, qty in expected.items():
            actual = _sku_qty(remote, sku)
            if actual != qty:
                issues.append(f"{sku}: expected {qty}, found {actual}")
        extra = {line.sku for line in remote.lines} - set(expected)
        if extra:
            issues.append(f"unexpected skus in cart: {sorted(extra)}")
        return (not issues), issues

    def open_checkout(self) -> CheckoutSession:
        assert self.session.cart_id
        remote = self._adapter.get_checkout(self.session.cart_id)
        self.session.log(f"checkout {remote.checkout_id} total ₹{remote.final_total:g}")
        return CheckoutSession(
            id=remote.checkout_id,
            cart_id=remote.cart_id,
            marketplace=remote.marketplace,
            vendor=remote.vendor,
            final_total=remote.final_total,
            currency=remote.currency,
            delivery_eta_minutes=remote.delivery_eta_minutes,
        )

    def close(self) -> None:
        if self._session:
            self._session.log("session closed")
        self._session = None


def _sku_qty(cart: RemoteCart, sku: str) -> int:
    return sum(line.quantity for line in cart.lines if line.sku == sku)


def _to_domain_cart(remote: RemoteCart, session_id: str) -> Cart:
    items = [
        CartItem(sku=line.sku, title=line.title, unit_price=line.unit_price,
                 quantity=line.quantity, line_total=round(line.unit_price * line.quantity, 2))
        for line in remote.lines
    ]
    return Cart(
        id=remote.cart_id,
        marketplace=remote.marketplace,
        session_id=session_id,
        items=items,
        items_subtotal=remote.items_subtotal,
        delivery_fee=remote.delivery_fee,
        platform_fee=remote.platform_fee,
        discount=remote.discount,
        total=remote.total,
        currency=remote.currency,
        verified=False,
    )


def get_browser_executor(adapter: BaseMarketplaceAdapter) -> BrowserExecutor:
    from ..config import get_settings

    settings = get_settings()
    if settings.browser_mode == "playwright":
        try:
            from .playwright_executor import PlaywrightExecutor

            return PlaywrightExecutor(adapter)
        except Exception as exc:  # pragma: no cover
            logger.warning("Playwright executor unavailable (%s); using mock", exc)
    return MockBrowserExecutor(adapter)
