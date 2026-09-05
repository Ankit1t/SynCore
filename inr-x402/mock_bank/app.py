"""Mock bank HTTP API (port 8003)."""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from mock_bank import bank, db

app = FastAPI(title="INR-x402 Mock Bank")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


class OnboardRequest(BaseModel):
    user_id: Optional[str] = None
    balance_paise: int = bank.OPENING_BALANCE_PAISE


class MandateRequest(BaseModel):
    user_id: str
    per_txn_max_paise: int
    daily_max_paise: int
    categories: list[str]
    expires_at: str


class DebitRequest(BaseModel):
    mandate_token: str
    amount_paise: int
    idempotency_key: str


class ReverseRequest(BaseModel):
    nonce: str
    reversal_key: str


class FailRateRequest(BaseModel):
    rate: float
    seed: Optional[int] = None


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "mock-bank", "fail_rate": bank.get_fail_rate()}


@app.post("/onboard")
def onboard(req: OnboardRequest) -> dict:
    return bank.onboard(req.user_id, req.balance_paise)


@app.post("/mandates")
def create_mandate(req: MandateRequest) -> dict:
    return bank.create_mandate(
        req.user_id, req.per_txn_max_paise, req.daily_max_paise,
        req.categories, req.expires_at,
    )


@app.get("/mandates/{mandate_token}")
def get_mandate(mandate_token: str) -> dict:
    m = bank.get_mandate(mandate_token)
    if not m:
        raise HTTPException(status_code=404, detail="mandate_not_found")
    return m


@app.post("/debit")
def debit(req: DebitRequest) -> dict:
    return bank.debit(req.mandate_token, req.amount_paise, req.idempotency_key)


@app.post("/reverse")
def reverse(req: ReverseRequest) -> dict:
    return bank.reverse(req.nonce, req.reversal_key)


@app.get("/balance/{user_id}")
def balance(user_id: str) -> dict:
    bal = bank.get_balance(user_id)
    if bal is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    return {"user_id": user_id, "balance_paise": bal}


@app.get("/ledger")
def ledger(nonce: Optional[str] = None) -> dict:
    return {"entries": bank.get_ledger(nonce)}


@app.post("/admin/failrate")
def set_failrate(req: FailRateRequest) -> dict:
    """Test/demo hook: adjust decline probability at runtime."""
    bank.set_fail_rate(req.rate, req.seed)
    return {"fail_rate": bank.get_fail_rate()}
