"""INR-x402 shared protocol library.

Contains the ONLY things services are allowed to share in-process:
  - canonical JSON encoding (so signatures are reproducible everywhere)
  - Ed25519 sign/verify + key helpers
  - protocol data models (Invoice / PaymentIntent / Receipt)
  - machine-readable reject codes

Services must NOT import each other's internals. They talk over HTTP.
This package is protocol-level glue only.
"""

from shared.reject_codes import RejectCode
from shared.canonical import canonical_json, canonical_bytes

__all__ = ["RejectCode", "canonical_json", "canonical_bytes"]
