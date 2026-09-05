"""Agent: autonomous CLI client.

Requests a resource, handles 402 by signing a PaymentIntent, retries with an
X-PAYMENT header, then persists the signed receipt. Zero human input per
transaction. Implements the reliability rules: retry-once on bank decline,
never retry on replay, and receipt-poll recovery after a post-submit timeout.
"""
