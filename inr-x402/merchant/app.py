"""Merchant HTTP API + payment middleware (port 8001).

Flow per request to a priced route:
  no X-PAYMENT   -> 402 + Invoice JSON
  X-PAYMENT      -> decode intent+signature -> facilitator POST /settle
                    settled  -> 200 + data + X-PAYMENT-RESPONSE (the receipt)
                    rejected -> 402 + reject reason
"""
from __future__ import annotations

import base64
import json
import os

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.models import Invoice

app = FastAPI(title="INR-x402 Merchant")

MERCHANT_ID = os.environ.get("MERCHANT_ID", "merchant_demo")
FACILITATOR_URL = os.environ.get("FACILITATOR_URL", "http://localhost:8002")
PUBLIC_BASE = os.environ.get("MERCHANT_PUBLIC_BASE", "http://localhost:8001")

# Price config: path -> price in paise.
PRICES = {
    "/api/summarize": 50,   # ₹0.50
    "/api/search": 10,      # ₹0.10
}


def _invoice_for(path: str, price_paise: int) -> Invoice:
    return Invoice.create(
        resource=f"{PUBLIC_BASE}{path}",
        price_paise=price_paise,
        pay_to=MERCHANT_ID,
        facilitator_url=FACILITATOR_URL,
    )


def _decode_payment_header(header_value: str) -> dict:
    """X-PAYMENT is base64(json({intent, signature, agentId}))."""
    raw = base64.b64decode(header_value)
    return json.loads(raw)


@app.middleware("http")
async def payment_middleware(request: Request, call_next):
    path = request.url.path
    price = PRICES.get(path)
    if price is None:
        # Unpriced route (e.g. /health, docs) -> pass through untouched.
        return await call_next(request)

    payment = request.headers.get("X-PAYMENT")
    if not payment:
        # No payment presented -> 402 Payment Required + invoice.
        invoice = _invoice_for(path, price)
        return JSONResponse(status_code=402, content=invoice.model_dump())

    # Decode the presented payment payload.
    try:
        payload = _decode_payment_header(payment)
        intent = payload["intent"]
        signature = payload["signature"]
        agent_id = payload["agentId"]
    except Exception:
        invoice = _invoice_for(path, price)
        return JSONResponse(
            status_code=402,
            content={**invoice.model_dump(), "reason": "malformed_payment_header"},
        )

    # SETTLE FIRST. Forward to the facilitator over HTTP.
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{FACILITATOR_URL}/settle",
                json={"intent": intent, "signature": signature, "agentId": agent_id},
            )
            settle = resp.json()
    except Exception as e:
        invoice = _invoice_for(path, price)
        return JSONResponse(
            status_code=402,
            content={**invoice.model_dump(), "reason": f"facilitator_unreachable:{e}"},
        )

    if not settle.get("ok"):
        # Payment rejected -> 402 + machine-readable reason. No content delivered.
        invoice = _invoice_for(path, price)
        return JSONResponse(
            status_code=402,
            content={**invoice.model_dump(), "reason": settle.get("reason")},
        )

    # DELIVER SECOND. Stash the receipt so the route handler can attach it, then
    # let the request proceed to generate the actual content.
    request.state.receipt = settle.get("receipt")
    request.state.receipt_signature = settle.get("receiptSignature")
    response = await call_next(request)

    # Attach the signed receipt as X-PAYMENT-RESPONSE (base64 JSON).
    receipt_env = json.dumps({
        "receipt": settle.get("receipt"),
        "receiptSignature": settle.get("receiptSignature"),
    })
    response.headers["X-PAYMENT-RESPONSE"] = base64.b64encode(
        receipt_env.encode("utf-8")
    ).decode("ascii")
    return response


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "merchant", "merchantId": MERCHANT_ID}


@app.get("/api/summarize")
def summarize(request: Request) -> dict:
    # Reached only after successful settlement (middleware gate).
    return {
        "resource": "summarize",
        "summary": "INR-x402 lets autonomous agents pay per API call over HTTP "
                   "using signed intents and mandate-scoped bank debits.",
        "receipt": getattr(request.state, "receipt", None),
    }


@app.get("/api/search")
def search(request: Request) -> dict:
    return {
        "resource": "search",
        "results": ["result-1", "result-2", "result-3"],
        "receipt": getattr(request.state, "receipt", None),
    }
