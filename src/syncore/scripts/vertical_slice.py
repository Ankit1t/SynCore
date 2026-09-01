"""Run the first working vertical slice end-to-end from the command line.

    python -m syncore.scripts.vertical_slice
    python -m syncore.scripts.vertical_slice "500 ke andar 1kg aloo, 100g mirch aur 2 Maggi"

This exercises: intent -> plan -> search -> normalize -> rank -> optimize ->
budget -> browser cart build -> verify -> checkout -> budget guard -> payment
-> order verify -> summary, using the deterministic mock marketplace + mock
payment provider.
"""

from __future__ import annotations

import sys

from ..intent.parser import parse_request
from ..observability.logging import configure_logging
from ..orchestrator.orchestrator import build_default_orchestrator

DEFAULT_REQUEST = "₹500 ke andar 1kg aloo, 100g mirch aur 2 Maggi order kar."


def main() -> int:
    configure_logging(level="INFO", json_output=False)
    text = " ".join(sys.argv[1:]).strip() or DEFAULT_REQUEST

    print("=" * 70)
    print(f"USER: {text}")
    print("=" * 70)

    request = parse_request(text, user_id="demo-user")
    orchestrator = build_default_orchestrator()
    run = orchestrator.run(request, auto_execute=True)

    print("\n--- AGENT TIMELINE ---")
    for step in run.steps:
        print(f"  [{step.index:02d}] {step.state:<24} {step.message}")

    if run.basket:
        b = run.basket
        print("\n--- OPTIMIZED BASKET ---")
        print(f"  Marketplace: {b.marketplace} | Objective: {b.objective.value}")
        for bi in b.items:
            print(f"   - {bi.canonical_name:<14} {bi.offer.product.title:<42} "
                  f"x{bi.packs}  ₹{bi.line_total:g}")
        print(f"  Items subtotal: ₹{b.items_subtotal:g}")
        print(f"  Delivery:       ₹{b.delivery_fee:g}")
        print(f"  Platform fee:   ₹{b.platform_fee:g}")
        print(f"  Discount:      -₹{b.discount:g}")
        print(f"  TOTAL:          ₹{b.total:g}  (within budget: {b.within_budget})")

    if run.order:
        o = run.order
        print("\n--- ORDER ---")
        print(f"  Order ID: {o.external_order_id} | Status: {o.status.value}")
        print(f"  Total: ₹{o.total:g} | ETA: ~{o.delivery_eta_minutes} min")

    print(f"\nFinal state: {run.state}")
    if run.checkpoint_reason:
        print(f"Checkpoint:  {run.checkpoint_reason.value}")
    if run.error:
        print(f"Error:       {run.error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
