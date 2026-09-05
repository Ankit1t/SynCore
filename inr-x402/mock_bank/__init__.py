"""Mock bank: mandates, double-entry ledger, idempotent debit, failure injection.

Simulates UPI Autopay e-mandates + a settlement bank. The ONE function that a
real integration would replace is `bank.debit()`.
"""
