"""Typed domain errors.

API layers translate these into structured error responses. Internal stack
traces and secrets must never leak to end users.
"""

from __future__ import annotations


class SyncoreError(Exception):
    """Base class for all domain errors."""

    code: str = "syncore_error"
    http_status: int = 400

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class IntentParseError(SyncoreError):
    code = "intent_parse_error"


class ProductNotFoundError(SyncoreError):
    code = "product_not_found"
    http_status = 404


class MarketplaceUnavailableError(SyncoreError):
    code = "marketplace_unavailable"
    http_status = 503


class ScraperParseError(SyncoreError):
    code = "scraper_parse_error"


class NormalizationError(SyncoreError):
    code = "normalization_error"


class BudgetExceededError(SyncoreError):
    code = "budget_exceeded"


class NoViableBasketError(SyncoreError):
    code = "no_viable_basket"


class CartVerificationError(SyncoreError):
    code = "cart_verification_error"


class PaymentAuthorizationRequired(SyncoreError):
    """Not a failure: a legitimate human-in-the-loop checkpoint."""

    code = "payment_authorization_required"
    http_status = 202


class PaymentFailedError(SyncoreError):
    code = "payment_failed"


class TransactionGuardError(SyncoreError):
    """Raised when the final deterministic pre-payment guard rejects a charge."""

    code = "transaction_guard_failed"


class AgentLimitExceededError(SyncoreError):
    code = "agent_limit_exceeded"


class AuthorizationError(SyncoreError):
    code = "authorization_error"
    http_status = 403
