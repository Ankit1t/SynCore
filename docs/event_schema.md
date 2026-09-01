# Event Schema

## Purpose

Decouple producers/consumers and enable real-time UI + future async processing.

## Bus

`syncore.events.bus.EventBus` with an in-memory implementation for the MVP. The
interface (`publish`, `subscribe`) is intentionally tiny so it can be backed by
Redis Streams or Kafka later without touching producers.

Diagram: [`mermaid/18_event_driven.mmd`](mermaid/18_event_driven.mmd).

## Event shape

```python
Event{ name: str, payload: dict, correlation_id: str|None, ts: datetime }
```
`correlation_id` is the `AgentRun.id`, so every event is traceable to a run.

## Well-known events (`Events`)

`ShoppingRequestCreated, IntentParsed, PlanCreated, SearchStarted,
ProductsDiscovered, ProductsNormalized, ProductsRanked, BasketOptimized,
BudgetVerified, CartBuildStarted, CartVerified, CheckoutStarted,
PaymentAuthorizationRequired, PaymentSucceeded, PaymentFailed, OrderPlaced,
OrderVerificationCompleted, AgentStateChanged, AgentFailed`.

## Consumers

- The SSE endpoint subscribes indirectly (via the orchestrator's `on_step`
  callback) to stream `AgentStateChanged`/step data to the browser.
- Audit logging records security- and money-relevant events.
- Future: analytics/metrics consumers, notification service, reconciliation.

## Delivery semantics

In-memory bus is synchronous, at-most-once within a process. A durable backend
(Streams/Kafka) would add at-least-once + consumer groups; idempotent handlers
(keyed by event id) are required there — the payment/order paths are already
idempotent.

## Webhooks (Phase 2)

Inbound payment/order webhooks must verify signatures, persist event ids, reject
duplicates, and process idempotently (spec section 46).
