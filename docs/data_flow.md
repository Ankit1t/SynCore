# Data Flow

## Purpose

Trace a request's data from words to a persisted order, highlighting where
prices are advisory vs authoritative.

## End-to-end flow

```
raw text
  └─▶ IntentParser ─▶ ShoppingRequest{items[], budget}
        └─▶ ShoppingPlan{SearchQuery per item}
              └─▶ MarketplaceAdapters.search_products() ─▶ Offer[] (advisory prices)
                    └─▶ quality.validate_offer() ─▶ clean Offer[]
                          └─▶ RankingEngine.rank() ─▶ RankedOffer[] per item
                                └─▶ BasketOptimizer.optimize() ─▶ Basket (advisory total)
                                      └─▶ budget.check_budget()  [gate #1: search estimate]
                                            └─▶ BrowserExecutor cart build + verify ─▶ Cart
                                                  └─▶ adapter.get_checkout() ─▶ CheckoutSession (AUTHORITATIVE total)
                                                        └─▶ budget.check_budget()  [gate #2: real total]
                                                              └─▶ transaction guard ─▶ PaymentService ─▶ PaymentIntent
                                                                    └─▶ OrderManager.place_and_verify() ─▶ Order
                                                                          └─▶ repositories.save_run/save_order
```

See [`mermaid/04_product_discovery.mmd`](mermaid/04_product_discovery.mmd) and
[`mermaid/22_data_lifecycle.mmd`](mermaid/22_data_lifecycle.mmd).

## Advisory vs authoritative prices

The price seen during search may differ from checkout. Syncore treats search
prices as **advisory** and always re-extracts the **authoritative** checkout
total from the (mock) cart, then re-runs the hard budget check before any
payment (spec sections 55–56). The mock marketplace currently returns a stable
total (drift ₹0); the guard still runs so real adapters get the same protection.

## Data lineage

Every `Offer` carries `source`, `source_product_id`, `extracted_at`,
`parser_version`, `normalization_version`, and `confidence`, so any price or
decision can be traced back to where and when it came from (spec section 68).

## Persistence points

`ShoppingRequest`, `AgentRun` (+ steps, decisions), `Order`, and `AuditEvent`
are persisted after a run. Payment intents/attempts are represented on the run
and order; the schema includes dedicated tables for future direct persistence.
