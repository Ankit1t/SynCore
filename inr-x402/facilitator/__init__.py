"""Facilitator: the product.

Verifies signed PaymentIntents, runs the policy engine, guards against replay,
persists nonces before charging, settles via the bank, and issues signed
Receipts. Also exposes receipt recovery + a bounded reversal window.
"""
