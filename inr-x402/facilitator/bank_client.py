"""HTTP client to the mock bank.

The facilitator talks to the bank ONLY over HTTP (no imports of bank internals).
A network timeout here surfaces distinctly so the pipeline can return
bank_timeout rather than bank_declined.
"""
from __future__ import annotations

from typing import Optional

import httpx


class BankTimeout(Exception):
    pass


class BankClient:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_mandate(self, mandate_token: str) -> Optional[dict]:
        try:
            r = httpx.get(f"{self.base_url}/mandates/{mandate_token}", timeout=self.timeout)
        except httpx.TimeoutException as e:
            raise BankTimeout(str(e))
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def debit(self, mandate_token: str, amount_paise: int, idempotency_key: str) -> dict:
        try:
            r = httpx.post(
                f"{self.base_url}/debit",
                json={
                    "mandate_token": mandate_token,
                    "amount_paise": amount_paise,
                    "idempotency_key": idempotency_key,
                },
                timeout=self.timeout,
            )
        except httpx.TimeoutException as e:
            raise BankTimeout(str(e))
        r.raise_for_status()
        return r.json()

    def reverse(self, nonce: str, reversal_key: str) -> dict:
        try:
            r = httpx.post(
                f"{self.base_url}/reverse",
                json={"nonce": nonce, "reversal_key": reversal_key},
                timeout=self.timeout,
            )
        except httpx.TimeoutException as e:
            raise BankTimeout(str(e))
        r.raise_for_status()
        return r.json()
