"""Enumerations shared across the domain."""

from __future__ import annotations

from enum import Enum


class Unit(str, Enum):
    """Canonical measurement units used after normalization."""

    KG = "kg"
    G = "g"
    L = "l"
    ML = "ml"
    PIECE = "piece"  # count-based items (e.g. "2 Maggi packs")


class ConstraintType(str, Enum):
    HARD = "HARD"
    SOFT = "SOFT"


class OptimizationObjective(str, Enum):
    CHEAPEST = "CHEAPEST"
    BEST_VALUE = "BEST_VALUE"
    FASTEST = "FASTEST"
    BEST_QUALITY = "BEST_QUALITY"
    BALANCED = "BALANCED"


class SubstitutionPolicy(str, Enum):
    NEVER_SUBSTITUTE = "NEVER_SUBSTITUTE"
    ASK_BEFORE_SUBSTITUTION = "ASK_BEFORE_SUBSTITUTION"
    AUTO_SUBSTITUTE_WITHIN_PRICE_LIMIT = "AUTO_SUBSTITUTE_WITHIN_PRICE_LIMIT"
    AUTO_SUBSTITUTE_BEST_VALUE = "AUTO_SUBSTITUTE_BEST_VALUE"


class AgentState(str, Enum):
    """Explicit orchestrator state machine (see docs/state_machine.md)."""

    REQUEST_RECEIVED = "REQUEST_RECEIVED"
    INTENT_PARSED = "INTENT_PARSED"
    PLAN_CREATED = "PLAN_CREATED"
    SEARCHING = "SEARCHING"
    DISCOVERING_PRODUCTS = "DISCOVERING_PRODUCTS"
    EXTRACTING_PRODUCTS = "EXTRACTING_PRODUCTS"
    NORMALIZING = "NORMALIZING"
    RANKING = "RANKING"
    OPTIMIZING = "OPTIMIZING"
    BASKET_READY = "BASKET_READY"
    USER_REVIEW_REQUIRED = "USER_REVIEW_REQUIRED"
    BROWSER_SESSION_STARTED = "BROWSER_SESSION_STARTED"
    SEARCH_EXECUTION = "SEARCH_EXECUTION"
    PRODUCT_SELECTED = "PRODUCT_SELECTED"
    CART_BUILDING = "CART_BUILDING"
    CART_VERIFIED = "CART_VERIFIED"
    CHECKOUT_READY = "CHECKOUT_READY"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_AUTH_REQUIRED = "PAYMENT_AUTH_REQUIRED"
    PAYMENT_PROCESSING = "PAYMENT_PROCESSING"
    ORDER_PLACED = "ORDER_PLACED"
    ORDER_VERIFICATION = "ORDER_VERIFICATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECOVERY = "RECOVERY"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, Enum):
    CREATED = "CREATED"
    AUTHORIZED = "AUTHORIZED"
    REQUIRES_USER_ACTION = "REQUIRES_USER_ACTION"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PLACED = "PLACED"
    PAYMENT_SUCCESS_ORDER_UNCONFIRMED = "PAYMENT_SUCCESS_ORDER_UNCONFIRMED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Availability(str, Enum):
    IN_STOCK = "IN_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    LIMITED = "LIMITED"


class HumanCheckpointReason(str, Enum):
    PAYMENT_AUTHENTICATION_REQUIRED = "PAYMENT_AUTHENTICATION_REQUIRED"
    UNKNOWN_VENDOR = "UNKNOWN_VENDOR"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    AMBIGUOUS_PRODUCT = "AMBIGUOUS_PRODUCT"
    HIGH_RISK_TRANSACTION = "HIGH_RISK_TRANSACTION"
    SUBSTITUTION_REQUIRES_APPROVAL = "SUBSTITUTION_REQUIRES_APPROVAL"


class Role(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"


# --------------------------------------------------------------------------- #
# Phase 2: delegated payment control plane
# --------------------------------------------------------------------------- #
class DelegationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class PolicyOutcome(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRES_USER_AUTHORIZATION = "REQUIRES_USER_AUTHORIZATION"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PaymentTxnState(str, Enum):
    """Phase-2 broker transaction lifecycle (integer-paise, UNKNOWN-first).

    Kept distinct from the Phase-1 PaymentStatus so existing flows are untouched.
    """

    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    SETTLED = "SETTLED"
    DROPPED = "DROPPED"
    REFUNDED = "REFUNDED"


class ProviderStatusCode(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    ACCESS_RESTRICTED = "PROVIDER_ACCESS_RESTRICTED"
    UNAVAILABLE = "UNAVAILABLE"
