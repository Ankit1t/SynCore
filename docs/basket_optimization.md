# Basket Optimization

## Purpose

Choose the best *combination* of offers for a request, reasoning at the basket
level (delivery, coupons, platform fees), and enforce hard budgets.

## Inputs / output

In: request items, `ranked_by_item` (per-item ranked offers across
marketplaces), the registry (for fee estimates), objective, min rating.
Out: a `Basket` (chosen marketplace, line items, economics, `within_budget`,
`missing_items`, `explanation`).

Diagram: [`mermaid/08_basket_optimization.mmd`](mermaid/08_basket_optimization.mmd).

## Objectives

`CHEAPEST`, `BEST_VALUE` (default), `FASTEST`, `BEST_QUALITY`, `BALANCED`.
The per-item selector and the cross-marketplace chooser both switch on the
objective (e.g. cheapest → min line total; fastest → min ETA; best-value →
ranking score).

## Why basket-level matters

```
mock-bazaar: items ₹280 + delivery ₹50            = ₹330
mock-fresh : items ₹295 + delivery ₹0             = ₹295   ← chosen
```

Optimizing items independently would miss this. Syncore builds a candidate basket
per marketplace, prices it with `adapter.estimate_fees(subtotal)`, then picks
the best per objective. Real example from the slice: `mock-fresh` wins the
default request because free delivery beats `mock-bazaar`'s ₹20 delivery despite
slightly higher item prices.

## Budget enforcement (never exceed a hard budget)

1. If the objective basket is over a hard budget, re-optimize **all**
   marketplaces for `CHEAPEST` and pick the min total.
2. If still over, drop optional items.
3. If still over, return the cheapest achievable basket with
   `within_budget=False` → the orchestrator routes to `USER_REVIEW_REQUIRED`
   and places **no** order.

## Substitution

`missing_items` are surfaced; substitution policy
(`NEVER`/`ASK`/`AUTO_WITHIN_PRICE`/`AUTO_BEST_VALUE`) governs replacements
(feature-flagged `FEATURE_AUTO_SUBSTITUTION`, default off).

## Testing

`tests/unit/test_optimizer.py`: all-items-in-budget, basket-level economics
identity (total = items + delivery + platform − discount), and the hard-budget
block. Property test asserts `within_budget` ⇒ `total ≤ limit`.
