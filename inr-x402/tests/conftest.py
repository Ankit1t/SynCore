"""Integration harness: boot bank + facilitator + merchant as real subprocesses.

Faithful to "services talk ONLY over HTTP" — every test drives the stack the
same way the agent CLI does. Uses temp DB files + default facilitator config
(so resource->category map + limits come from config.DEFAULTS) for hermetic runs.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
BANK_PORT = 8003
FACILITATOR_PORT = 8002
MERCHANT_PORT = 8001


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _wait_health(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=1.0)
            if r.status_code == 200:
                return
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(0.25)
    raise RuntimeError(f"service at {url} never became healthy: {last}")


def _spawn(module_app: str, port: int, env: dict) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", module_app, "--port", str(port),
         "--host", "127.0.0.1", "--log-level", "warning"],
        cwd=str(ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


@dataclass
class Stack:
    bank_url: str
    facilitator_url: str
    merchant_base: str

    def set_fail_rate(self, rate: float, seed: Optional[int] = None) -> None:
        body = {"rate": rate}
        if seed is not None:
            body["seed"] = seed
        httpx.post(f"{self.bank_url}/admin/failrate", json=body, timeout=5.0).raise_for_status()

    def onboard(self, user_id: Optional[str] = None) -> dict:
        return httpx.post(f"{self.bank_url}/onboard",
                          json={"user_id": user_id} if user_id else {},
                          timeout=5.0).json()

    def create_mandate(self, user_id: str, per_txn: int, daily: int,
                       categories: list[str], expires_at: str) -> str:
        r = httpx.post(f"{self.bank_url}/mandates", json={
            "user_id": user_id, "per_txn_max_paise": per_txn,
            "daily_max_paise": daily, "categories": categories,
            "expires_at": expires_at,
        }, timeout=5.0).json()
        return r["mandate_token"]

    def register_agent(self, agent_id: str, pubkey_hex: str) -> None:
        httpx.post(f"{self.facilitator_url}/admin/agents",
                   json={"agent_id": agent_id, "pubkey_hex": pubkey_hex},
                   timeout=5.0).raise_for_status()

    def ledger(self, nonce: Optional[str] = None) -> list[dict]:
        params = {"nonce": nonce} if nonce else {}
        return httpx.get(f"{self.bank_url}/ledger", params=params, timeout=5.0).json()["entries"]


@pytest.fixture(scope="session")
def stack(tmp_path_factory):
    for p in (BANK_PORT, FACILITATOR_PORT, MERCHANT_PORT):
        if _port_open(p):
            raise RuntimeError(
                f"port {p} already in use; stop any running INR-x402 services first")

    data_dir = tmp_path_factory.mktemp("inrx402_it")
    base_env = dict(os.environ)
    base_env["PYTHONPATH"] = str(ROOT)
    base_env["MOCK_BANK_DB"] = str(data_dir / "bank.db")
    base_env["FACILITATOR_DB"] = str(data_dir / "facilitator.db")
    # Point at a nonexistent config file so the facilitator uses config.DEFAULTS.
    base_env["FACILITATOR_CONFIG"] = str(data_dir / "no_such_config.json")
    base_env["FAIL_RATE"] = "0.0"
    # Force 127.0.0.1 for all inter-service URLs. On Windows, 'localhost' can
    # resolve to ::1 first while uvicorn binds 127.0.0.1, adding multi-second
    # connect delays. Pin the loopback IPv4 address to avoid that.
    base_env["BANK_URL"] = f"http://127.0.0.1:{BANK_PORT}"
    base_env["FACILITATOR_URL"] = f"http://127.0.0.1:{FACILITATOR_PORT}"
    base_env["MERCHANT_PUBLIC_BASE"] = f"http://127.0.0.1:{MERCHANT_PORT}"

    procs = []
    try:
        procs.append(_spawn("mock_bank.app:app", BANK_PORT, base_env))
        procs.append(_spawn("facilitator.app:app", FACILITATOR_PORT, base_env))
        procs.append(_spawn("merchant.app:app", MERCHANT_PORT, base_env))

        _wait_health(f"http://127.0.0.1:{BANK_PORT}/health")
        _wait_health(f"http://127.0.0.1:{FACILITATOR_PORT}/health")
        _wait_health(f"http://127.0.0.1:{MERCHANT_PORT}/health")

        yield Stack(
            bank_url=f"http://127.0.0.1:{BANK_PORT}",
            facilitator_url=f"http://127.0.0.1:{FACILITATOR_PORT}",
            merchant_base=f"http://127.0.0.1:{MERCHANT_PORT}",
        )
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


@pytest.fixture()
def new_agent(stack, tmp_path):
    """Factory: fresh agent identity + user + mandate wired end-to-end."""
    from datetime import timedelta
    from shared.crypto import generate_keypair
    from shared.models import now_utc, iso
    from agent.client import Agent, AgentConfig

    created = {"n": 0}

    def _make(per_txn: int = 100, daily: int = 5000,
              categories=("content", "search"), budget: int = 5000,
              expires_days: int = 30) -> tuple[Agent, str, str]:
        created["n"] += 1
        agent_id = f"agent_test_{uuid.uuid4().hex[:8]}"
        sk, vk = generate_keypair()
        user = stack.onboard(f"user_{agent_id}")
        expires_at = iso(now_utc() + timedelta(days=expires_days))
        mandate = stack.create_mandate(user["user_id"], per_txn, daily,
                                       list(categories), expires_at)
        stack.register_agent(agent_id, vk)
        cfg = AgentConfig(
            agent_id=agent_id, signing_key_hex=sk, mandate_ref=mandate,
            merchant_base=stack.merchant_base, budget_paise=budget,
            receipts_path=str(tmp_path / f"{agent_id}.jsonl"),
        )
        return Agent(cfg), agent_id, mandate

    return _make
