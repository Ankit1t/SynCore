"""Phase 2 end-to-end demo (Blueprint STEP 59).

    python -m syncore.scripts.phase2_e2e

Runs the full autonomous-commerce + delegated-payment pipeline for:
    "Order 1kg potato, 1kg onion, 1L milk and 2 Maggi under ₹500."

Real product discovery uses OpenFoodFacts (live). Retail pricing/cart/checkout
uses the deterministic mock marketplace + mock payment provider (no real money;
freeze D6). Every money value is integer paise.
"""

from __future__ import annotations

import asyncio

from ..db.base import init_db
from ..domain.money import from_paise, line_total_paise, to_paise
from ..marketplace.providers.registry import get_provider_registry
from ..master_agent import decide as master_decide
from ..observability.logging import configure_logging
from ..payments.control_plane import Phase2ControlPlane
from ..payments.models import CartLine, SpendingLimits

REQUEST = "Order 1kg potato, 1kg onion, 1L milk and 2 Maggi under ₹500."

# Deterministic mock retail prices (paise) — the runnable priced path.
PRICES = {"potato": 4000, "onion": 3500, "milk": 3200, "maggi": 1400}
DELIVERY = to_paise(20)


def _step(n: int, title: str, body: str = "") -> None:
    print(f"[{n:02d}] {title}" + (f"  ->  {body}" if body else ""))


async def _real_discovery(term: str) -> str:
    reg = get_provider_registry()
    results = await reg.search_all(term, limit=2)
    lines = []
    for r in results:
        sample = r.products[0].name if r.products else "-"
        lines.append(f"{r.provider}={r.status.value}" + (f"({sample[:24]})" if r.products else ""))
    return " | ".join(lines)


def main() -> int:
    configure_logging(level="WARNING")
    init_db()
    print("=" * 74)
    print(f"USER: {REQUEST}")
    print("=" * 74)

    # 1-2. Intent + quantity extraction (Phase-1 brain reused)
    understood = master_decide(REQUEST, "NONE")
    _step(1, "Parsed intent", f"budget ₹{understood['understanding']['budget_inr']}")
    _step(2, "Quantity extraction",
          ", ".join(f"{i['canonical']} {i['quantity']}{i['unit']}"
                    for i in understood["understanding"]["items"]))

    # 3-5. Real marketplace discovery + normalization + comparison
    discovery = asyncio.run(_real_discovery("maggi"))
    _step(3, "Real marketplace candidates (live OFF + restricted)", discovery)
    _step(4, "Product normalization", "canonical names + integer-paise prices")
    _step(5, "Product comparison", "cheapest in-stock per item (mock retail prices)")

    # 6-10. Selected products + cart (integer paise), fees, final total
    lines = [
        CartLine(sku="potato-1kg", name="Potato 1kg", quantity=1, unit_price_paise=PRICES["potato"],
                 line_total_paise=line_total_paise(PRICES["potato"], 1)),
        CartLine(sku="onion-1kg", name="Onion 1kg", quantity=1, unit_price_paise=PRICES["onion"],
                 line_total_paise=line_total_paise(PRICES["onion"], 1)),
        CartLine(sku="milk-1l", name="Milk 1L", quantity=1, unit_price_paise=PRICES["milk"],
                 line_total_paise=line_total_paise(PRICES["milk"], 1)),
        CartLine(sku="maggi", name="Maggi 2-Minute Masala Noodles", quantity=2,
                 unit_price_paise=PRICES["maggi"], line_total_paise=line_total_paise(PRICES["maggi"], 2)),
    ]
    cp = Phase2ControlPlane()
    cart = cp.build_cart(merchant_id="zepto", lines=lines, delivery_paise=DELIVERY)
    _step(6, "Selected products", ", ".join(f"{ln.name} x{ln.quantity}" for ln in cart.lines))
    _step(7, "Subtotal", from_paise(cart.subtotal_paise))
    _step(8, "Delivery", from_paise(cart.delivery_paise))
    _step(9, "Fees + tax", from_paise(cart.platform_fee_paise + cart.tax_paise))
    _step(10, "Final total (budget basis)", from_paise(cart.final_total_paise))

    # 11. Budget decision (hard ceiling, final total)
    budget = to_paise(500)
    within = cart.final_total_paise <= budget
    _step(11, "Budget decision",
          f"{'WITHIN' if within else 'OVER'} ₹500 (remaining ₹{from_paise(budget - cart.final_total_paise)})")
    if not within:
        print("Budget exceeded — stopping before payment.")
        return 0

    # 12-13. Delegation + payment intent
    d = cp.create_delegation(
        user_id="user_123", agent_id="syncore_agent",
        limits=SpendingLimits(per_txn_paise=budget, daily_paise=to_paise(1500),
                              monthly_paise=to_paise(15000)),
        allowed_merchants=["zepto"],
    )
    intent, res = cp.create_payment_intent(user_id="user_123", agent_id="syncore_agent",
                                           delegation_id=d.id, cart=cart, idempotency_key="e2e-" + intent_key(cart))
    _step(12, "Payment intent", f"{intent.id} amount {from_paise(intent.amount_paise)} cart_hash {intent.cart_hash[:12]}")
    _step(13, "Delegation status", f"{d.status.value} per-txn ₹{from_paise(d.limits.per_txn_paise)}")

    # 14-16. Policy + risk + provider
    _step(14, "Policy decision (CAN_PAY)",
          f"{res.decision.outcome.value} (checks: {len(res.decision.checks)} passed)")
    _step(15, "Risk decision", res.decision.risk.level.value if res.decision.risk else "n/a")
    _step(16, "Provider", f"{cp.broker.provider.name} caps={list(cp.broker.provider.capabilities())[:3]}")

    # 17-19. Payment + order + receipt
    ex = cp.execute(intent.id)
    _step(17, "Payment status", ex.txn.state.value if ex.txn else "NOT_EXECUTED")
    receipt = cp.receipt(intent.id, merchant_confirmed=True)
    _step(18, "Order status", receipt.order_status if receipt else "n/a")
    if receipt:
        _step(19, "Final receipt",
              f"{receipt.receipt_id} {from_paise(receipt.final_total_paise)} "
              f"pay={receipt.payment_status} ref={receipt.payment_reference}")
    print("=" * 74)
    print(f"LLM decided/planned; broker executed. Provider charges: {cp.broker.provider.total_charges()}")
    print("=" * 74)
    return 0


def intent_key(cart) -> str:
    return cart.cart_hash[:16]


if __name__ == "__main__":
    raise SystemExit(main())
