"""Facilitator HTTP API (port 8002)."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.models import SettleRequest
from facilitator import db, keys
from facilitator.engine import Facilitator

app = FastAPI(title="INR-x402 Facilitator")

_facilitator: Facilitator | None = None


def get_facilitator() -> Facilitator:
    global _facilitator
    if _facilitator is None:
        _facilitator = Facilitator()
    return _facilitator


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    get_facilitator()  # generate/load keypair up front


class RegisterAgentRequest(BaseModel):
    agent_id: str
    pubkey_hex: str


class ReverseRequest(BaseModel):
    nonce: str


@app.get("/health")
def health() -> dict:
    f = get_facilitator()
    return {"ok": True, "service": "facilitator", "facilitatorId": f.facilitator_id}


@app.get("/facilitator/pubkey")
def facilitator_pubkey() -> dict:
    f = get_facilitator()
    return {"facilitatorId": f.facilitator_id, "verify_key_hex": f.key["verify_key_hex"]}


@app.post("/admin/agents")
def register_agent(req: RegisterAgentRequest) -> dict:
    return keys.register_agent(req.agent_id, req.pubkey_hex)


@app.post("/settle")
def settle(req: SettleRequest) -> dict:
    f = get_facilitator()
    return f.settle(req.intent, req.signature, req.agentId)


@app.get("/receipt/{nonce}")
def get_receipt(nonce: str) -> dict:
    f = get_facilitator()
    res = f.get_receipt(nonce)
    if res is None:
        raise HTTPException(status_code=404, detail="receipt_not_found")
    return res


@app.post("/reverse")
def reverse(req: ReverseRequest) -> dict:
    f = get_facilitator()
    return f.reverse(req.nonce)
