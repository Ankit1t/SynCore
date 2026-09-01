"""Management CLI: database migration and demo seeding.

    python -m syncore.scripts.manage migrate   # create tables
    python -m syncore.scripts.manage seed       # seed demo user + a sample run
"""

from __future__ import annotations

import sys

from ..db.base import init_db, session_scope
from ..db import repositories as repo
from ..intent.parser import parse_request
from ..observability.logging import configure_logging, get_logger
from ..orchestrator.orchestrator import build_default_orchestrator

logger = get_logger("syncore.manage")


def migrate() -> None:
    init_db()
    logger.info("database tables created")


def seed() -> None:
    init_db()
    with session_scope() as s:
        user = repo.get_or_create_demo_user(s)
    logger.info("demo user: %s (%s)", user.email, user.id)

    # Seed one completed run so dashboards/orders are non-empty on first boot.
    request = parse_request("₹500 ke andar 1kg aloo, 100g mirch aur 2 Maggi order kar.",
                            user_id=user.id)
    orch = build_default_orchestrator()
    run = orch.run(request, auto_execute=True)
    with session_scope() as s:
        repo.save_request(s, request)
        repo.save_run(s, run)
        repo.save_audit_events(s, [e for e in orch.audit if e.run_id == run.id])
    logger.info("seeded run %s -> state=%s", run.id, run.state)


def main() -> int:
    configure_logging()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "migrate"
    if cmd == "migrate":
        migrate()
    elif cmd == "seed":
        seed()
    else:
        print(f"unknown command: {cmd}. Use 'migrate' or 'seed'.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
