"""Phase 1 unit tests: canonical JSON + Ed25519 + models."""
from shared.canonical import canonical_json, canonical_bytes
from shared.crypto import generate_keypair, sign_obj, verify_obj, sign_bytes, verify_bytes
from shared.models import PaymentIntent, Invoice, Receipt, now_utc, iso
from shared.reject_codes import RejectCode


def test_canonical_sorts_keys_and_strips_whitespace():
    a = canonical_json({"b": 1, "a": 2})
    assert a == '{"a":2,"b":1}'


def test_canonical_is_order_independent():
    x = canonical_bytes({"nonce": "n1", "amountPaise": 50})
    y = canonical_bytes({"amountPaise": 50, "nonce": "n1"})
    assert x == y


def test_sign_and_verify_roundtrip():
    sk, vk = generate_keypair()
    msg = b"hello-inr-x402"
    sig = sign_bytes(sk, msg)
    assert verify_bytes(vk, msg, sig)


def test_verify_rejects_tampered_message():
    sk, vk = generate_keypair()
    sig = sign_bytes(sk, b"original")
    assert not verify_bytes(vk, b"tampered", sig)


def test_verify_rejects_wrong_key():
    sk, _ = generate_keypair()
    _, other_vk = generate_keypair()
    sig = sign_bytes(sk, b"data")
    assert not verify_bytes(other_vk, b"data", sig)


def test_verify_handles_garbage_signature_without_raising():
    _, vk = generate_keypair()
    assert not verify_bytes(vk, b"data", "notevenhex")


def test_intent_signing_payload_is_stable_and_verifiable():
    sk, vk = generate_keypair()
    intent = PaymentIntent(
        nonce="n-1", resource="http://x/api", amountPaise=50,
        payTo="merchant_demo", mandateRef="mdt_1", agentId="agent_001",
        issuedAt=iso(now_utc()), expiresAt=iso(now_utc()),
    )
    sig = sign_obj(sk, intent.signing_payload())
    assert verify_obj(vk, intent.signing_payload(), sig)


def test_invoice_factory_has_frozen_fields():
    inv = Invoice.create("http://x/api", 50, "merchant_demo", "http://localhost:8002")
    assert inv.scheme == "inr-x402"
    assert inv.pricePaise == 50
    assert inv.payTo == "merchant_demo"
    assert inv.expiresAt


def test_reject_code_serializes_to_bare_string():
    assert str(RejectCode.REPLAY_DETECTED) == "replay_detected"
    assert RejectCode.OVER_DAILY_CAP.value == "over_daily_cap"


def test_receipt_signing_payload_roundtrip():
    sk, vk = generate_keypair()
    r = Receipt(nonce="n", status="settled", amountPaise=50,
                utrn="BK012345678901", settledAt=iso(now_utc()),
                facilitatorId="facil_001")
    sig = sign_obj(sk, r.signing_payload())
    assert verify_obj(vk, r.signing_payload(), sig)
