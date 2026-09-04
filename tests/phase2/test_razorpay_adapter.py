"""Razorpay adapter (TEST mode) — order creation, status, refund, fail-closed.

httpx is monkeypatched so no real network call happens; we assert the adapter
speaks the documented Razorpay Orders/Payments shapes and maps states correctly.
"""

from __future__ import annotations

from syncore.payments import pay_providers
from syncore.payments.pay_providers import RazorpayProvider


class _FakeResp:
    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self) -> dict:
        return self._payload


def _configured() -> RazorpayProvider:
    p = RazorpayProvider()
    p._key_id = "rzp_test_abc"       # noqa: SLF001 - test injection
    p._key_secret = "secret_xyz"     # noqa: SLF001
    return p


def test_unavailable_without_keys_fails_closed():
    p = RazorpayProvider()
    p._key_id = None                 # noqa: SLF001
    p._key_secret = None             # noqa: SLF001
    assert p.available() is False
    res = p.execute_payment(amount_paise=8800, currency="INR", merchant_id="zepto",
                            idempotency_key="ik-1")
    assert res.state == "FAILED"
    assert "PROVIDER_ACCESS_RESTRICTED" in res.detail


def test_execute_creates_order_and_parks_unknown(monkeypatch):
    captured = {}

    def fake_post(url, auth=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResp({"id": "order_test_123", "amount": json["amount"], "status": "created"})

    monkeypatch.setattr(pay_providers.httpx, "post", fake_post)
    p = _configured()
    res = p.execute_payment(amount_paise=8800, currency="INR", merchant_id="zepto",
                            idempotency_key="agentic:req_1")
    assert res.state == "UNKNOWN"                       # money not moved yet
    assert res.provider_ref == "order_test_123"
    assert captured["url"].endswith("/orders")
    assert captured["json"]["amount"] == 8800
    assert captured["json"]["payment_capture"] == 1
    assert len(captured["json"]["receipt"]) <= 40


def test_get_status_paid_maps_to_success(monkeypatch):
    def fake_get(url, auth=None, timeout=None):
        return _FakeResp({"id": "o1", "status": "paid"})

    monkeypatch.setattr(pay_providers.httpx, "get", fake_get)
    assert _configured().get_status("o1") == "SUCCESS"


def test_get_status_unpaid_maps_to_failed(monkeypatch):
    def fake_get(url, auth=None, timeout=None):
        return _FakeResp({"id": "o1", "status": "created"})

    monkeypatch.setattr(pay_providers.httpx, "get", fake_get)
    assert _configured().get_status("o1") == "FAILED"


def test_refund_finds_captured_payment(monkeypatch):
    def fake_get(url, auth=None, timeout=None):
        return _FakeResp({"items": [{"id": "pay_1", "status": "captured"}]})

    def fake_post(url, auth=None, json=None, timeout=None):
        return _FakeResp({"id": "rfnd_1", "status": "processed"})

    monkeypatch.setattr(pay_providers.httpx, "get", fake_get)
    monkeypatch.setattr(pay_providers.httpx, "post", fake_post)
    r = _configured().refund(provider_ref="order_test_123", amount_paise=8800)
    assert r.ok is True
    assert r.provider_ref == "rfnd_1"


def test_capabilities_report_hosted_checkout():
    caps = _configured().capabilities()
    assert caps["hosted_checkout"] is True
    assert caps["delegated_payment"] is False   # server-side AutoPay not enabled
