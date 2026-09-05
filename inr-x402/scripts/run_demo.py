"""One-command end-to-end demo.

Boots bank (8003) + facilitator (8002) + merchant (8001), seeds keys/mandate,
then drives the autonomous agent through the happy path and a few extras
(replay, recovery, reversal). Cross-platform so `make demo`, `./demo.sh`, and
`demo.ps1` all just call this.

Run:  python -m scripts.run_demo
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PORTS = {"bank": 8003, "facilitator": 8002, "merchant": 8001}

# Windows consoles default to cp1252 and can't print the rupee glyph (U+20B9).
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


def _wait_health(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(url, timeout=1.0).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError(f"{url} never became healthy")


def _spawn(module_app: str, port: int, env: dict) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", module_app, "--port", str(port),
         "--host", "127.0.0.1", "--log-level", "warning"],
        cwd=str(ROOT), env=env,
    )


def _hr(title: str) -> None:
    print("\n" + "=" * 70 + f"\n  {title}\n" + "=" * 70)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    # Fresh DBs for a clean demo run.
    for f in ["mock_bank.db", "facilitator.db"]:
        for suffix in ["", "-wal", "-shm"]:
            p = DATA / (f + suffix)
            if p.exists():
                p.unlink()

    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["MOCK_BANK_DB"] = str(DATA / "mock_bank.db")
    env["FACILITATOR_DB"] = str(DATA / "facilitator.db")
    env["FACILITATOR_CONFIG"] = str(DATA / "facilitator_config.json")
    # Pin IPv4 loopback (avoids Windows localhost->::1 connect delays).
    env["BANK_URL"] = "http://127.0.0.1:8003"
    env["FACILITATOR_URL"] = "http://127.0.0.1:8002"
    env["MERCHANT_PUBLIC_BASE"] = "http://127.0.0.1:8001"
    env["FAIL_RATE"] = os.environ.get("FAIL_RATE", "0.0")

    for p in PORTS.values():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex(("127.0.0.1", p)) == 0:
                raise RuntimeError(f"port {p} already in use; stop old services first")

    procs = []
    try:
        _hr("Starting services (mock-bank, facilitator, merchant)")
        procs.append(_spawn("mock_bank.app:app", 8003, env))
        procs.append(_spawn("facilitator.app:app", 8002, env))
        procs.append(_spawn("merchant.app:app", 8001, env))
        for name, port in PORTS.items():
            _wait_health(f"http://127.0.0.1:{port}/health")
            print(f"  [ok] {name} healthy on :{port}")

        _hr("Seeding: agent keypair, bank user, UPI-Autopay mandate")
        # seed talks to services over HTTP and writes data/agent_config.json.
        os.environ.update({
            "BANK_URL": env["BANK_URL"],
            "FACILITATOR_URL": env["FACILITATOR_URL"],
            "MERCHANT_PUBLIC_BASE": env["MERCHANT_PUBLIC_BASE"],
        })
        from scripts.seed import main as seed_main
        seed_main()

        from agent.client import Agent, AgentConfig
        cfg = AgentConfig.load(str(DATA / "agent_config.json"))
        agent = Agent(cfg)

        _hr("HAPPY PATH: agent pays ₹0.50 for /api/summarize")
        r = agent.pay("/api/summarize")
        print(json.dumps({"ok": r.ok, "status": r.status, "attempts": r.attempts,
                          "receipt": r.receipt, "receipt_verified": r.receipt_verified,
                          "data": r.data}, indent=2, default=str))

        _hr("HAPPY PATH #2: agent pays ₹0.10 for /api/search")
        r2 = agent.pay("/api/search")
        print(json.dumps({"ok": r2.ok, "status": r2.status,
                          "receipt": r2.receipt}, indent=2, default=str))

        _hr("RECOVERY: response dropped after debit -> recover via /receipt")
        r3 = agent.pay("/api/summarize", simulate_timeout_once=True)
        print(json.dumps({"ok": r3.ok, "status": r3.status, "nonce": r3.nonce,
                          "receipt_verified": r3.receipt_verified}, indent=2, default=str))

        _hr("REVERSAL: reverse the happy-path debit within the 10-min window")
        rev = httpx.post(f"{env['FACILITATOR_URL']}/reverse",
                         json={"nonce": r.nonce}, timeout=5.0).json()
        print(json.dumps(rev, indent=2, default=str))

        _hr("BANK LEDGER (double-entry)")
        entries = httpx.get(f"{env['BANK_URL']}/ledger", timeout=5.0).json()["entries"]
        for e in entries:
            print(f"  {e['type']:9s} {e['from_acct']:>24s} -> {e['to_acct']:<20s} "
                  f"{e['amount_paise']:>6d}p  utrn={e['utrn']}  nonce={e['nonce']}")

        _hr("Agent remaining local budget")
        print(json.dumps({"budget_paise": AgentConfig.load(str(DATA / 'agent_config.json')).budget_paise},
                         indent=2))

        _hr("DEMO COMPLETE")
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
