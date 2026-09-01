"""Deterministic mock marketplace.

Provides a fully working, repeatable marketplace (search, product details,
cart, checkout, order) so the entire agent workflow is testable without real
purchases. The live scraping/adapter architecture still exists (base.py); this
mock is ONLY for deterministic development and tests (spec sections 53-54).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.enums import Availability, Unit
from ..domain.errors import ProductNotFoundError
from ..domain.models import Offer, Product, Quantity, Seller, new_id
from ..normalization import lexicon
from .base import (
    BaseMarketplaceAdapter,
    Fees,
    RemoteCart,
    RemoteCartLine,
    RemoteCheckout,
    RemoteOrder,
)


@dataclass(frozen=True)
class ProductSeed:
    canonical: str
    title: str
    price: float
    qty_value: float
    qty_unit: Unit
    rating: float
    reviews: int
    seller: str
    reliability: float = 0.85
    brand: str | None = None
    mrp: float | None = None
    organic: bool = False
    delivery_eta: int = 120
    availability: Availability = Availability.IN_STOCK


# Shared canonical catalog. Prices are in INR and are the "mock-bazaar" base;
# other marketplaces apply a multiplier. Multiple offers per item let the
# ranking + optimizer make real trade-offs (cheap vs quality vs quantity).
CATALOG: list[ProductSeed] = [
    # potato / aloo
    ProductSeed("potato", "Fresh Potato 1kg", 38, 1, Unit.KG, 4.3, 1820, "GreenFarm", 0.9, mrp=45),
    ProductSeed("potato", "Farm Potatoes 500g", 22, 500, Unit.G, 4.1, 640, "GreenFarm", 0.9, mrp=26),
    ProductSeed("potato", "Premium Baby Potato 1kg", 60, 1, Unit.KG, 4.6, 410, "OrganicHub", 0.92, mrp=70, organic=True),
    # onion / pyaaz
    ProductSeed("onion", "Onion 1kg", 34, 1, Unit.KG, 4.2, 990, "GreenFarm", 0.9, mrp=40),
    ProductSeed("onion", "Onion 500g", 20, 500, Unit.G, 4.0, 300, "GreenFarm", 0.9, mrp=24),
    # tomato / tamatar
    ProductSeed("tomato", "Tomato 1kg", 30, 1, Unit.KG, 4.1, 720, "GreenFarm", 0.9, mrp=38),
    ProductSeed("tomato", "Tomato 500g", 18, 500, Unit.G, 4.0, 210, "GreenFarm", 0.9, mrp=22),
    # green chilli / mirch
    ProductSeed("green chilli", "Green Chilli 100g", 15, 100, Unit.G, 4.0, 260, "GreenFarm", 0.88, mrp=18),
    ProductSeed("green chilli", "Green Chilli 250g", 30, 250, Unit.G, 4.2, 180, "GreenFarm", 0.88, mrp=36),
    # maggi (count-based, brand matters)
    ProductSeed("maggi", "Nestle Maggi 2-Minute Masala Noodles 70g", 14, 1, Unit.PIECE, 4.5, 21000, "Nestle Store", 0.95, brand="Nestle", mrp=15),
    ProductSeed("maggi", "Maggi Masala Noodles Pack of 4 280g", 52, 4, Unit.PIECE, 4.5, 8800, "Nestle Store", 0.95, brand="Nestle", mrp=60),
    ProductSeed("maggi", "Maggi Masala Magic Seasoning 100g", 55, 100, Unit.G, 4.3, 1500, "Nestle Store", 0.95, brand="Nestle", mrp=60),
    # staples for breadth
    ProductSeed("rice", "Daawat Basmati Rice 1kg", 95, 1, Unit.KG, 4.4, 5400, "Daawat", 0.9, brand="Daawat", mrp=110),
    ProductSeed("wheat flour", "Aashirvaad Atta 1kg", 52, 1, Unit.KG, 4.5, 9100, "Aashirvaad", 0.92, brand="Aashirvaad", mrp=60),
    ProductSeed("milk", "Amul Toned Milk 1L", 54, 1, Unit.L, 4.4, 3300, "Amul", 0.93, brand="Amul", mrp=56),
    ProductSeed("sugar", "Sugar 1kg", 45, 1, Unit.KG, 4.2, 1200, "GreenFarm", 0.9, mrp=50),
    ProductSeed("salt", "Tata Salt 1kg", 28, 1, Unit.KG, 4.6, 7600, "Tata", 0.93, brand="Tata", mrp=30),
    ProductSeed("cooking oil", "Fortune Sunflower Oil 1L", 140, 1, Unit.L, 4.3, 4200, "Fortune", 0.9, brand="Fortune", mrp=160),
    ProductSeed("eggs", "Farm Eggs Pack of 6", 42, 6, Unit.PIECE, 4.2, 980, "GreenFarm", 0.88, mrp=48),
]


@dataclass
class MarketplaceProfile:
    """Per-marketplace economics so basket-level optimization is meaningful."""

    price_multiplier: float = 1.0
    delivery_fee: float = 20.0
    free_delivery_threshold: float | None = 199.0
    platform_fee: float = 0.0
    coupon_code: str | None = "SAVE10"
    coupon_min_subtotal: float = 100.0
    coupon_value: float = 10.0


PROFILES: dict[str, MarketplaceProfile] = {
    "mock-bazaar": MarketplaceProfile(
        price_multiplier=1.0, delivery_fee=20.0, free_delivery_threshold=199.0,
        platform_fee=0.0, coupon_code="SAVE10", coupon_min_subtotal=100.0, coupon_value=10.0,
    ),
    # Slightly pricier items but free delivery + no coupon: forces the optimizer
    # to reason at the basket level rather than per-item.
    "mock-fresh": MarketplaceProfile(
        price_multiplier=1.04, delivery_fee=0.0, free_delivery_threshold=None,
        platform_fee=5.0, coupon_code=None, coupon_min_subtotal=0.0, coupon_value=0.0,
    ),
}


class MockMarketplace(BaseMarketplaceAdapter):
    supports_live_execution = False

    def __init__(self, name: str = "mock-bazaar", profile: MarketplaceProfile | None = None):
        self.name = name
        self.profile = profile or PROFILES.get(name, MarketplaceProfile())
        self._offers: dict[str, Offer] = {}
        self._by_canonical: dict[str, list[str]] = {}
        self._carts: dict[str, RemoteCart] = {}
        self._checkouts: dict[str, RemoteCheckout] = {}
        self._build_catalog()

    # ---- catalog build ----------------------------------------------------
    def _build_catalog(self) -> None:
        for idx, seed in enumerate(CATALOG):
            price = round(seed.price * self.profile.price_multiplier, 2)
            mrp = round(seed.mrp * self.profile.price_multiplier, 2) if seed.mrp else None
            spid = f"{self.name}:{seed.canonical.replace(' ', '_')}:{idx}"
            product = Product(
                canonical_name=seed.canonical,
                title=seed.title,
                brand=seed.brand,
                category=lexicon.CATEGORY.get(seed.canonical, "grocery"),
                quantity=Quantity(value=seed.qty_value, unit=seed.qty_unit),
                rating=seed.rating,
                review_count=seed.reviews,
                organic=seed.organic,
                attributes={"seed_index": idx},
            )
            offer = Offer(
                product=product,
                seller=Seller(name=seed.seller, reliability=seed.reliability, marketplace=self.name),
                marketplace=self.name,
                source_product_id=spid,
                price=price,
                mrp=mrp,
                currency="INR",
                quantity=Quantity(value=seed.qty_value, unit=seed.qty_unit),
                shipping_fee=0.0,  # delivery is charged at basket level
                platform_fee=0.0,
                availability=seed.availability,
                delivery_eta_minutes=seed.delivery_eta,
                source=self.name,
            )
            self._offers[spid] = offer
            self._by_canonical.setdefault(seed.canonical, []).append(spid)

    # ---- discovery --------------------------------------------------------
    def search_products(self, query: str, *, limit: int = 20) -> list[Offer]:
        canonical = self._canonical_for_query(query)
        results: list[Offer] = []
        if canonical:
            for spid in self._by_canonical.get(canonical, []):
                results.append(self._offers[spid].model_copy(deep=True))
        else:
            tokens = [t for t in query.lower().split() if len(t) > 2]
            for offer in self._offers.values():
                title = offer.product.title.lower()
                if any(tok in title for tok in tokens):
                    results.append(offer.model_copy(deep=True))
        return results[:limit]

    def _canonical_for_query(self, query: str) -> str | None:
        lowered = query.lower()
        for alias in sorted(lexicon.alias_index(), key=len, reverse=True):
            if alias in lowered:
                return lexicon.alias_index()[alias]
        return None

    def get_product(self, source_product_id: str) -> Offer | None:
        offer = self._offers.get(source_product_id)
        return offer.model_copy(deep=True) if offer else None

    # ---- economics --------------------------------------------------------
    def estimate_fees(self, items_subtotal: float) -> Fees:
        p = self.profile
        if p.free_delivery_threshold is not None and items_subtotal >= p.free_delivery_threshold:
            delivery = 0.0
        else:
            delivery = p.delivery_fee
        discount = p.coupon_value if (p.coupon_code and items_subtotal >= p.coupon_min_subtotal) else 0.0
        return Fees(delivery_fee=delivery, platform_fee=p.platform_fee, discount=discount)

    # ---- cart / checkout --------------------------------------------------
    def create_cart(self, session_id: str) -> RemoteCart:
        cart = RemoteCart(cart_id=f"cart_{new_id()[:8]}", marketplace=self.name)
        self._carts[cart.cart_id] = cart
        return cart

    def add_to_cart(self, cart_id: str, source_product_id: str, quantity: int) -> RemoteCart:
        cart = self._carts.get(cart_id)
        if cart is None:
            raise ProductNotFoundError(f"cart not found: {cart_id}")
        offer = self._offers.get(source_product_id)
        if offer is None:
            raise ProductNotFoundError(f"product not found: {source_product_id}")

        existing = next((line for line in cart.lines if line.sku == source_product_id), None)
        if existing:
            existing.quantity += quantity
        else:
            cart.lines.append(
                RemoteCartLine(
                    sku=source_product_id,
                    title=offer.product.title,
                    unit_price=offer.price,
                    quantity=quantity,
                )
            )
        self._recompute_fees(cart)
        return cart

    def _recompute_fees(self, cart: RemoteCart) -> None:
        subtotal = cart.items_subtotal
        p = self.profile
        if p.free_delivery_threshold is not None and subtotal >= p.free_delivery_threshold:
            cart.delivery_fee = 0.0
        else:
            cart.delivery_fee = p.delivery_fee
        cart.platform_fee = p.platform_fee
        cart.discount = p.coupon_value if (p.coupon_code and subtotal >= p.coupon_min_subtotal) else 0.0

    def get_cart(self, cart_id: str) -> RemoteCart:
        cart = self._carts.get(cart_id)
        if cart is None:
            raise ProductNotFoundError(f"cart not found: {cart_id}")
        return cart

    def get_checkout(self, cart_id: str) -> RemoteCheckout:
        cart = self.get_cart(cart_id)
        self._recompute_fees(cart)  # authoritative recompute at checkout time
        vendor = cart.lines[0].sku.split(":")[0] if cart.lines else self.name
        eta = 120
        checkout = RemoteCheckout(
            checkout_id=f"chk_{new_id()[:8]}",
            cart_id=cart_id,
            marketplace=self.name,
            vendor=self.name,
            final_total=cart.total,
            currency=cart.currency,
            delivery_eta_minutes=eta,
        )
        self._checkouts[checkout.checkout_id] = checkout
        return checkout

    def place_order(self, checkout_id: str, *, payment_reference: str) -> RemoteOrder:
        checkout = self._checkouts.get(checkout_id)
        if checkout is None:
            raise ProductNotFoundError(f"checkout not found: {checkout_id}")
        return RemoteOrder(
            external_order_id=f"ORD-{new_id()[:10].upper()}",
            marketplace=self.name,
            vendor=checkout.vendor,
            total=checkout.final_total,
            currency=checkout.currency,
            delivery_eta_minutes=checkout.delivery_eta_minutes,
            confirmed=True,
        )

    def healthy(self) -> bool:
        return True


def build_default_registry() -> "list[MockMarketplace]":
    """Instantiate the default mock marketplaces."""
    return [MockMarketplace(name, profile) for name, profile in PROFILES.items()]
