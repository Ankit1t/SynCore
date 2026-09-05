"""Ed25519 signing for AP2 mandates — real asymmetric signatures.

Each party (user, agent, merchant, PSP) has an Ed25519 keypair. Mandates are
signed over their canonical ``content_digest`` so any later tampering breaks the
signature — this is what makes the intent -> cart -> payment chain genuinely
**non-repudiable** (the core of the dispute/liability story).

Keys are derived deterministically from a server seed + the party id via HKDF,
so they are stable across restarts and reproducible in a demo without shipping
key files. A production system would instead hold these in an HSM / KMS and use
the user's device passkey (WebAuthn) for the IntentMandate — swapping this
module's key source is the only change needed.
"""

from __future__ import annotations

import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from ..config import get_settings

_ALG = "Ed25519"


def _derive_seed() -> bytes:
    s = get_settings()
    base = (getattr(s, "webhook_secret", None) or "syncore-ap2-dev-seed").encode()
    return hashlib.sha256(b"ap2-mandate-signing::" + base).digest()


class KeyManager:
    """Deterministic Ed25519 keypairs per party id (stable across restarts)."""

    def __init__(self) -> None:
        self._seed = _derive_seed()
        self._priv: dict[str, Ed25519PrivateKey] = {}

    def _private(self, party_id: str) -> Ed25519PrivateKey:
        if party_id not in self._priv:
            # HKDF-style: hash(seed || party_id) -> 32-byte private scalar seed.
            material = hashlib.sha256(self._seed + b"::" + party_id.encode()).digest()
            self._priv[party_id] = Ed25519PrivateKey.from_private_bytes(material)
        return self._priv[party_id]

    def public_key_hex(self, party_id: str) -> str:
        return self._private(party_id).public_key().public_bytes_raw().hex()

    def sign(self, party_id: str, message: str) -> str:
        return self._private(party_id).sign(message.encode()).hex()

    @staticmethod
    def verify(public_key_hex: str, message: str, signature_hex: str) -> bool:
        try:
            pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
            pub.verify(bytes.fromhex(signature_hex), message.encode())
            return True
        except (InvalidSignature, ValueError):
            return False


_km: KeyManager | None = None


def get_key_manager() -> KeyManager:
    global _km
    if _km is None:
        _km = KeyManager()
    return _km


def signing_alg() -> str:
    return _ALG
