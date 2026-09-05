"""Agent CLI entrypoint.

Usage:
  python -m agent.cli pay --resource /api/summarize
  python -m agent.cli pay --resource /api/search --times 3
  python -m agent.cli pay --resource /api/summarize --simulate-timeout
  python -m agent.cli balance
Config is read from data/agent_config.json (written by scripts/seed.py) unless
--config is supplied.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent.client import Agent, AgentConfig

DEFAULT_CONFIG = str(Path(__file__).resolve().parent.parent / "data" / "agent_config.json")


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(prog="inr-x402-agent")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    sub = parser.add_subparsers(dest="command", required=True)

    p_pay = sub.add_parser("pay", help="pay for and fetch a paywalled resource")
    p_pay.add_argument("--resource", required=True, help="e.g. /api/summarize")
    p_pay.add_argument("--times", type=int, default=1)
    p_pay.add_argument("--simulate-timeout", action="store_true",
                       help="drop the first response to exercise receipt recovery")

    sub.add_parser("balance", help="show remaining local budget")

    args = parser.parse_args()
    cfg = AgentConfig.load(args.config)
    agent = Agent(cfg)

    if args.command == "balance":
        _print({"agentId": cfg.agent_id, "budget_paise": cfg.budget_paise})
        return

    if args.command == "pay":
        for i in range(args.times):
            result = agent.pay(
                args.resource,
                simulate_timeout_once=(args.simulate_timeout and i == 0),
            )
            _print({
                "attempt_group": i + 1,
                "ok": result.ok,
                "status": result.status,
                "reason": result.reason,
                "nonce": result.nonce,
                "attempts": result.attempts,
                "receipt": result.receipt,
                "receipt_verified": result.receipt_verified,
                "data": result.data,
            })


if __name__ == "__main__":
    main()
