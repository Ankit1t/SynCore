"""Protocol data models (FROZEN wire formats).

These pydantic models mirror the exact JSON shapes in the spec. The
`signing_payload()` helpers return the plain dict that gets canonicalized and
signed, so the "what exactly is signed" question has one answer.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from pydantic import BaseModel


SCHEME = "inr-x402"

# Protocol-wide timing constants.
INVOICE_TTL_SECONDS = 300      # 402 invoice validity
INTENT_TTL_SECONDS = 300       # stale signed intents are worthless (5 min)
REVERSAL_WINDOW_SECONDS = 600  # 10-minute reversal window


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    """ISO8601 with explicit Z-style UTC offset."""
    return dt.astimezone(timezone.utc).isoformat()


def parse_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class Invoice(BaseModel):
    scheme: str = SCHEME
    resource: str
    pricePaise: int
    payTo: str
    facilitatorUrl: str
    expiresAt: str

    @classmethod
    def create(cls, resource: str, price_paise: int, pay_to: str,
               facilitator_url: str, ttl: int = INVOICE_TTL_SECONDS) -> "Invoice":
        return cls(
            resource=resource,
            pricePaise=price_paise,
            payTo=pay_to,
            facilitatorUrl=facilitator_url,
            expiresAt=iso(now_utc() + timedelta(seconds=ttl)),
        )


class PaymentIntent(BaseModel):
    nonce: str
    resource: str
    amountPaise: int
    payTo: str
    mandateRef: str
    agentId: str
    issuedAt: str
    expiresAt: str

    def signing_payload(self) -> dict:
        """Exact dict that is canonicalized + signed by the agent."""
        return {
            "nonce": self.nonce,
            "resource": self.resource,
            "amountPaise": self.amountPaise,
            "payTo": self.payTo,
            "mandateRef": self.mandateRef,
            "agentId": self.agentId,
            "issuedAt": self.issuedAt,
            "expiresAt": self.expiresAt,
        }

    def is_expired(self, at: Optional[datetime] = None) -> bool:
        at = at or now_utc()
        return at > parse_iso(self.expiresAt)


class Receipt(BaseModel):
    nonce: str
    status: str  # settled | reversed | rejected
    amountPaise: int
    utrn: Optional[str] = None
    settledAt: Optional[str] = None
    facilitatorId: str

    def signing_payload(self) -> dict:
        """Exact dict the facilitator signs. Signature travels alongside."""
        return {
            "nonce": self.nonce,
            "status": self.status,
            "amountPaise": self.amountPaise,
            "utrn": self.utrn,
            "settledAt": self.settledAt,
            "facilitatorId": self.facilitatorId,
        }


class SettleRequest(BaseModel):
    """Body merchant forwards to facilitator POST /settle."""
    intent: PaymentIntent
    signature: str
    agentId: str


class SettleResponse(BaseModel):
    ok: bool
    receipt: Optional[Receipt] = None
    receiptSignature: Optional[str] = None
    reason: Optional[str] = None  # RejectCode value when ok is False
