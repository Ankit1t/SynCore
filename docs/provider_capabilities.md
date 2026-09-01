# Provider Capabilities (Phase 2)

Capabilities are DECLARED per provider and checked before any operation
(STEP 32/45). Nothing is assumed; a missing capability yields a typed result,
never a fabricated one.

## Marketplace / data providers

| Provider | Status | search | product | price | cart | checkout | order | Requirement |
|---|---|---|---|---|---|---|---|---|
| openfoodfacts | REAL (no key) | yes* | yes | **no** | no | no | no | none — real open catalog metadata; no retail price |
| amazon | ACCESS_RESTRICTED | — | — | — | — | — | — | SP-API/PA-API partner credentials |
| flipkart | ACCESS_RESTRICTED | — | — | — | — | — | — | Marketplace/Affiliate API credentials |
| zepto | ACCESS_RESTRICTED | — | — | — | — | — | — | partner API agreement |
| bigbasket | ACCESS_RESTRICTED | — | — | — | — | — | — | partner API agreement |
| blinkit | ACCESS_RESTRICTED | — | — | — | — | — | — | partner API agreement |

\* OFF free-text search is aggressively rate-limited (HTTP 503); product-by-barcode
is reliable. Search failures surface as `PROVIDER_ACCESS_RESTRICTED`/`DEGRADED`,
never faked. Config: `config/providers/openfoodfacts.json`,
`config/providers/restricted.example.json` (placeholders only, no secrets).

## Payment providers

| Provider | delegated_payment | amount_binding | merchant_binding | refund | reconciliation | Requirement |
|---|---|---|---|---|---|---|
| mock | yes | yes | yes | yes | yes | none (sandbox, no real money) |
| razorpay | yes | yes | yes | yes | yes | `RAZORPAY_KEY_ID` + `RAZORPAY_KEY_SECRET` (not executed without them) |

The Razorpay adapter is structurally complete against documented Orders/Payments
behavior but refuses to execute without configured credentials (STEP 46/57). It
never handles UPI PIN/OTP/CVV; authentication is provider-hosted.
