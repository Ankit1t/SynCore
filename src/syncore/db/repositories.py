"""Repositories: translate domain models <-> ORM rows.

Kept as thin functions over a Session so the rest of the app stays free of ORM
details. All writes are user/tenant-scoped by carrying user_id on every row.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.models import AgentRun, AuditEvent, Order, ShoppingRequest, User
from .tables import (
    AgentDecisionRow,
    AgentRunRow,
    AgentStepRow,
    AuditEventRow,
    OrderRow,
    ShoppingRequestRow,
    UserRow,
)


def _json(model) -> dict:
    return model.model_dump(mode="json")


# --- Users -------------------------------------------------------------------
def upsert_user(session: Session, user: User) -> None:
    row = session.get(UserRow, user.id)
    if row is None:
        # dedupe by email for the demo user
        existing = session.scalar(select(UserRow).where(UserRow.email == user.email))
        if existing:
            return
        session.add(UserRow(id=user.id, email=user.email, display_name=user.display_name,
                            role=user.role.value, created_at=user.created_at))


def get_or_create_demo_user(session: Session, email: str = "demo@syncore.local") -> User:
    row = session.scalar(select(UserRow).where(UserRow.email == email))
    if row:
        from ..domain.enums import Role

        return User(id=row.id, email=row.email, display_name=row.display_name, role=Role(row.role))
    user = User(email=email, display_name="Demo User")
    upsert_user(session, user)
    session.flush()
    return user


# --- Shopping requests -------------------------------------------------------
def save_request(session: Session, request: ShoppingRequest) -> None:
    if session.get(ShoppingRequestRow, request.id):
        return
    session.add(
        ShoppingRequestRow(
            id=request.id, user_id=request.user_id, raw_text=request.raw_text,
            budget_limit=request.budget.limit, currency=request.budget.currency,
            data=_json(request), created_at=request.created_at,
        )
    )


# --- Agent runs --------------------------------------------------------------
def save_run(session: Session, run: AgentRun) -> None:
    row = session.get(AgentRunRow, run.id)
    basket_json = _json(run.basket) if run.basket else None
    checkpoint = run.checkpoint_reason.value if run.checkpoint_reason else None
    if row is None:
        row = AgentRunRow(
            id=run.id, request_id=run.request_id, user_id=run.user_id, state=run.state,
            checkpoint_reason=checkpoint, error=run.error, basket=basket_json,
            started_at=run.started_at, finished_at=run.finished_at,
        )
        session.add(row)
    else:
        row.state = run.state
        row.checkpoint_reason = checkpoint
        row.error = run.error
        row.basket = basket_json
        row.finished_at = run.finished_at

    existing_steps = {s.id for s in row.steps}
    for step in run.steps:
        if step.id in existing_steps:
            continue
        row.steps.append(
            AgentStepRow(id=step.id, run_id=run.id, idx=step.index, state=step.state,
                         message=step.message, data=step.data, created_at=step.created_at)
        )
    existing_decisions = {d.id for d in row.decisions}
    for dec in run.decisions:
        if dec.id in existing_decisions:
            continue
        row.decisions.append(
            AgentDecisionRow(id=dec.id, run_id=run.id, kind=dec.kind, summary=dec.summary,
                             evidence=dec.evidence, created_at=dec.created_at)
        )

    if run.order:
        save_order(session, run.order)


def save_order(session: Session, order: Order) -> None:
    if session.get(OrderRow, order.id):
        return
    session.add(
        OrderRow(
            id=order.id, user_id=order.user_id, request_id=order.request_id,
            marketplace=order.marketplace, vendor=order.vendor, total=order.total,
            currency=order.currency, status=order.status.value,
            external_order_id=order.external_order_id, payment_intent_id=order.payment_intent_id,
            delivery_eta_minutes=order.delivery_eta_minutes,
            items=[i.model_dump(mode="json") for i in order.items], created_at=order.created_at,
        )
    )


def save_audit_events(session: Session, events: list[AuditEvent]) -> None:
    for ev in events:
        if session.get(AuditEventRow, ev.id):
            continue
        session.add(
            AuditEventRow(id=ev.id, event=ev.event, user_id=ev.user_id, run_id=ev.run_id,
                          payload=ev.payload, created_at=ev.created_at)
        )


# --- Queries -----------------------------------------------------------------
def get_run_row(session: Session, run_id: str) -> AgentRunRow | None:
    return session.get(AgentRunRow, run_id)


def list_runs(session: Session, user_id: str | None = None, limit: int = 50) -> list[AgentRunRow]:
    stmt = select(AgentRunRow).order_by(AgentRunRow.started_at.desc()).limit(limit)
    if user_id:
        stmt = stmt.where(AgentRunRow.user_id == user_id)
    return list(session.scalars(stmt))


def list_orders(session: Session, user_id: str | None = None, limit: int = 50) -> list[OrderRow]:
    stmt = select(OrderRow).order_by(OrderRow.created_at.desc()).limit(limit)
    if user_id:
        stmt = stmt.where(OrderRow.user_id == user_id)
    return list(session.scalars(stmt))


def get_order_row(session: Session, order_id: str) -> OrderRow | None:
    return session.get(OrderRow, order_id)


def get_request_model(session: Session, request_id: str) -> ShoppingRequest | None:
    row = session.get(ShoppingRequestRow, request_id)
    if row is None:
        return None
    return ShoppingRequest.model_validate(row.data)
