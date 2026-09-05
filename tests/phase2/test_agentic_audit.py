"""Agentic audit trail + merchant verify-mandate endpoints (HTTP level)."""

from __future__ import annotations

import copy

from fastapi.testclient import TestClient

from syncore.api.app import create_app

TEXT = "1kg aloo, 100g mirch aur 2 Maggi under 500"


def _client() -> TestClient:
    return TestClient(create_app())


def test_checkout_is_recorded_in_audit_trail():
    c = _client()
    r = c.post("/api/v1/agentic/checkout", json={"text": TEXT}).json()
    iid = r["intent_id"]

    rows = c.get("/api/v1/agentic/audit").json()
    assert any(row["intent_id"] == iid for row in rows)

    detail = c.get(f"/api/v1/agentic/audit/{iid}").json()
    assert detail["verify_report"]["chain_valid"] is True
    assert detail["ap2_mandates"]["intent_mandate"]["signature_alg"] == "Ed25519"


def test_audit_detail_404_for_unknown_intent():
    c = _client()
    assert c.get("/api/v1/agentic/audit/pi_does_not_exist").status_code == 404


def test_verify_mandate_endpoint_accepts_good_rejects_tampered():
    c = _client()
    r = c.post("/api/v1/agentic/checkout", json={"text": TEXT}).json()
    chain = r["ap2_mandates"]

    ok = c.post("/api/v1/agentic/verify-mandate", json=chain).json()
    assert ok["ok"] is True and ok["kind"] == "chain"

    bad = copy.deepcopy(chain)
    bad["cart_mandate"]["total_paise"] += 100
    rej = c.post("/api/v1/agentic/verify-mandate", json=bad).json()
    assert rej["ok"] is False


def test_me_endpoint_returns_user_id():
    c = _client()
    me = c.get("/api/v1/agentic/me").json()
    assert me["user_id"]
