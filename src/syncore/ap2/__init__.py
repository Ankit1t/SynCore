"""AP2 (Agent Payments Protocol) compatibility layer for Syncore.

This package expresses Syncore's delegated-payment artifacts in the shape of
Google's open **Agent Payments Protocol (AP2)** mandates, so the control plane
"speaks AP2" without taking a hard dependency on the reference SDK (which pulls
in ADK/Gemini). The three AP2 mandates map onto Syncore's existing objects:

    AP2 IntentMandate   <-  syncore Delegation        (authorization + rules)
    AP2 CartMandate     <-  syncore Cart + Intent     (exact items + price)
    AP2 PaymentMandate  <-  syncore PaymentTransaction (method + settlement)

Each mandate carries a deterministic ``content_digest`` (SHA-256 over a
canonical JSON payload). Downstream mandates reference the digest of the
mandate above them, forming AP2's non-repudiable **chain of evidence**:

    IntentMandate.digest  ->  CartMandate.intent_mandate_ref
    CartMandate.digest    ->  PaymentMandate.cart_mandate_ref

The digests are content hashes, not cryptographic signatures. Real signing
(Ed25519 / WebAuthn / SD-JWT) lives in the ``control-plane`` package; swapping
these digests for signed VCs is a drop-in later.
"""

from .mandates import (
    CartMandate,
    IntentMandate,
    MandateChain,
    PaymentMandate,
    build_mandate_chain,
    cart_mandate_from_cart,
    intent_mandate_from_delegation,
    payment_mandate_from_txn,
    verify_mandate_payload,
)
from .signing import get_key_manager, signing_alg

__all__ = [
    "IntentMandate",
    "CartMandate",
    "PaymentMandate",
    "MandateChain",
    "intent_mandate_from_delegation",
    "cart_mandate_from_cart",
    "payment_mandate_from_txn",
    "build_mandate_chain",
    "verify_mandate_payload",
    "get_key_manager",
    "signing_alg",
]
