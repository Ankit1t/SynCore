"""Merchant: demo paywalled API + x402 payment middleware.

Owns its price config, returns 402 + Invoice when payment is missing, and
forwards X-PAYMENT to the facilitator over HTTP. It never imports facilitator
internals. Settle FIRST, deliver content SECOND (bank debits are fallible).
"""
