"""API integration tests using FastAPI's TestClient."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from syncore.api.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_and_execute_flow(client):
    r = client.post("/api/v1/shopping-requests",
                    json={"text": "₹500 ke andar 1kg aloo, 100g mirch aur 2 Maggi order kar."})
    assert r.status_code == 200
    body = r.json()
    assert body["budget_limit"] == 500.0
    assert len(body["items"]) == 3

    rid = body["id"]
    ex = client.post(f"/api/v1/shopping-requests/{rid}/execute")
    assert ex.status_code == 200
    run = ex.json()
    assert run["state"] == "COMPLETED"
    assert run["basket"]["total"] <= 500.0
    assert run["order"]["status"] == "CONFIRMED"


def test_optimize_only(client):
    r = client.post("/api/v1/baskets/optimize",
                    json={"text": "1kg aloo, 100g mirch aur 2 maggi under 500"})
    assert r.status_code == 200
    basket = r.json()
    assert basket["within_budget"]
    assert len(basket["items"]) == 3


def test_product_search(client):
    r = client.get("/api/v1/products/search", params={"q": "aloo"})
    assert r.status_code == 200
    assert len(r.json()) > 0


def test_orders_and_runs_listed(client):
    # ensure at least one run exists
    client.post("/api/v1/shopping-requests",
                json={"text": "₹500 ke andar 1kg aloo aur 2 maggi"})
    assert client.get("/api/v1/orders").status_code == 200
    assert client.get("/api/v1/agent-runs").status_code == 200
    assert client.get("/api/v1/admin/metrics").status_code == 200


def test_over_budget_returns_review_state(client):
    r = client.post("/api/v1/shopping-requests",
                    json={"text": "order 2 maggi and 1kg rice under 100"})
    rid = r.json()["id"]
    ex = client.post(f"/api/v1/shopping-requests/{rid}/execute").json()
    assert ex["state"] == "USER_REVIEW_REQUIRED"
    assert ex["order"] is None
