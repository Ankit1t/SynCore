"""Ed25519 sign / verify helpers (PyNaCl).

Detached signatures over canonical JSON bytes. Keys are passed around as hex
strings so they can live in a SQLite row or a seed file with no binary fuss.
"""
from __future__ import annotations

from typing import Any, Tuple

from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError

from shared.canonical import canonical_bytes


def generate_keypair() -> Tuple[str, str]:
    """Return (signing_key_hex, verify_key_hex)."""
    sk = SigningKey.generate()
    return sk.encode().hex(), sk.verify_key.encode().hex()


def sign_bytes(signing_key_hex: str, message: bytes) -> str:
    """Return detached signature (hex) for raw bytes."""
    sk = SigningKey(bytes.fromhex(signing_key_hex))
    return sk.sign(message).signature.hex()


def verify_bytes(verify_key_hex: str, message: bytes, signature_hex: str) -> bool:
    """Verify a detached signature over raw bytes. Never raises."""
    try:
        vk = VerifyKey(bytes.fromhex(verify_key_hex))
        vk.verify(message, bytes.fromhex(signature_hex))
        return True
    except (BadSignatureError, ValueError):
        return False


def sign_obj(signing_key_hex: str, obj: Any) -> str:
    """Sign a JSON-serializable object using canonical encoding."""
    return sign_bytes(signing_key_hex, canonical_bytes(obj))


def verify_obj(verify_key_hex: str, obj: Any, signature_hex: str) -> bool:
    """Verify a signature over a JSON-serializable object (canonical)."""
    return verify_bytes(verify_key_hex, canonical_bytes(obj), signature_hex)
