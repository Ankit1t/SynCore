"""Security-sensitive payment subsystem.

The LLM never receives raw payment credentials (card number, CVV, OTP, bank
password, keys). Payment flows are gated by a deterministic policy engine, a
final transaction guard, and idempotency so retries never double-charge.
"""
