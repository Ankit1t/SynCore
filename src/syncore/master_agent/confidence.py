"""Autopilot confidence scorer for the master agent.

Runs after basket build, before any (hypothetical) autonomous checkout. It
scores a candidate against the parsed intent and applies HARD RULES that sit
*above* the score — variant mismatch, budget breach, auto-pay limit, brand
lock. These hard rules are the permanent guard against the "silent downgrade"
bug (asking for a mega pack and getting a regular pack ordered quietly).

Three outcomes:
  AUTO_EXECUTE   — high confidence, safe to act silently
  EXECUTE_NOTIFY — act but tell the user what happened
  ASK_USER       — stop and ask one clean question

Pure stdlib, no dependencies. Money math stays deterministic.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

AUTO_PAY_LIMIT = 500.0  # above this the agent always seeks confirmation
AUTO_EXECUTE_MIN = 85  # score >= 85 -> silent
EXECUTE_NOTIFY_MIN = 60  # score 60-84 -> act + inform


class Action(Enum):
    AUTO_EXECUTE = "AUTO_EXECUTE"
    EXECUTE_NOTIFY = "EXECUTE_NOTIFY"
    ASK_USER = "ASK_USER"


@dataclass
class OrderSpec:
    """Output of Phase-1 intent parsing."""

    item: str
    variant_keywords: list[str] = field(default_factory=list)
    quantity: int = 1
    budget: float | None = None
    brand_lock: str | None = None


@dataclass
class Candidate:
    """A normalized product (the best offer / built basket line)."""

    product_name: str
    brand: str = ""
    size_text: str = ""
    unit_price: float = 0.0
    quantity_available: int = 99
    seller_rating: float = 0.0
    product_rating: float = 0.0
    review_count: int = 0
    eta_minutes: int = 0
    in_stock: bool = True
    user_ordered_before: bool = False
    same_brand_before: bool = False


@dataclass
class Decision:
    action: Action
    score: int
    reasons: list[str]
    blockers: list[str]
    total_price: float
    audit_id: str
    user_question: str = ""


# ------------------------------------------------------------------ scorers
def score_variant(spec: OrderSpec, cand: Candidate) -> tuple[int, str]:
    name = f"{cand.product_name} {cand.size_text}".lower()
    kws = [k.lower() for k in spec.variant_keywords]
    if not kws:
        return 40, "no variant requested (free match)"
    hits = [k for k in kws if k in name]
    missing = [k for k in kws if k not in hits]
    if not missing:
        return 40, f"exact variant match: {hits}"
    if hits:
        return 20, f"partial variant match {hits}, missing {missing}"
    return 0, f"VARIANT MISMATCH: asked {kws}, product has none"


def score_price(spec: OrderSpec, cand: Candidate) -> tuple[int, str]:
    total = round(cand.unit_price * spec.quantity, 2)
    if spec.budget is None:
        return 20, f"no budget constraint (total Rs.{total})"
    if total <= spec.budget:
        return 20, f"total Rs.{total} within budget Rs.{spec.budget}"
    if total <= spec.budget * 1.1:
        return 10, f"total Rs.{total} slightly over budget Rs.{spec.budget}"
    return 0, f"total Rs.{total} EXCEEDS budget Rs.{spec.budget}"


def score_seller(cand: Candidate) -> tuple[int, str]:
    r = cand.seller_rating
    if r >= 4.5:
        return 15, f"seller rating {r} excellent"
    if r >= 4.0:
        return 12, f"seller rating {r} good"
    if r >= 3.5:
        return 8, f"seller rating {r} average"
    if r > 0:
        return 4, f"seller rating {r} low"
    return 8, "seller rating unknown (neutral)"


def score_reviews(cand: Candidate) -> tuple[int, str]:
    r, n = cand.product_rating, cand.review_count
    if r >= 4.3 and n >= 100:
        return 15, f"product {r}/5 on {n} reviews — trusted"
    if r >= 4.0:
        return 12, f"product {r}/5 good"
    if r >= 3.5:
        return 8, f"product {r}/5 average"
    if r > 0:
        return 4, f"product {r}/5 weak"
    return 8, "no reviews (neutral)"


def score_history(spec: OrderSpec, cand: Candidate) -> tuple[int, str]:
    if cand.user_ordered_before:
        return 10, "user ordered this product before"
    if cand.same_brand_before:
        return 6, "user has same-brand history"
    return 3, "new product/brand for user"


# ------------------------------------------------------------------- engine
def decide(spec: OrderSpec, cand: Candidate, auto_pay_limit: float = AUTO_PAY_LIMIT) -> Decision:
    s: dict[str, int] = {}
    s["variant"], vmsg = score_variant(spec, cand)
    s["price"], pmsg = score_price(spec, cand)
    s["seller"], smsg = score_seller(cand)
    s["reviews"], rmsg = score_reviews(cand)
    s["history"], hmsg = score_history(spec, cand)
    total = sum(s.values())
    reasons = [vmsg, pmsg, smsg, rmsg, hmsg]

    blockers: list[str] = []
    total_price = round(cand.unit_price * spec.quantity, 2)

    if not cand.in_stock:
        blockers.append("out of stock")
    if spec.variant_keywords and s["variant"] == 0:
        blockers.append("variant mismatch — silent downgrade forbidden")
    if spec.budget is not None and total_price > spec.budget:
        blockers.append(f"budget exceeded (Rs.{total_price} > Rs.{spec.budget})")
    if spec.quantity > cand.quantity_available:
        blockers.append(f"only {cand.quantity_available} in stock, asked {spec.quantity}")
    if cand.product_rating and cand.product_rating < 3.0:
        blockers.append(f"product rating {cand.product_rating} too low (<3.0)")
    if total_price > auto_pay_limit:
        blockers.append(f"above auto-pay limit Rs.{auto_pay_limit} — confirmation required")
    if spec.brand_lock and cand.brand and spec.brand_lock.lower() not in cand.brand.lower():
        blockers.append(f"brand lock violated: asked {spec.brand_lock}, found {cand.brand}")

    if blockers:
        action = Action.ASK_USER
    elif total >= AUTO_EXECUTE_MIN:
        action = Action.AUTO_EXECUTE
    elif total >= EXECUTE_NOTIFY_MIN:
        action = Action.EXECUTE_NOTIFY
    else:
        action = Action.ASK_USER

    q = ""
    if action == Action.ASK_USER:
        if any("variant mismatch" in b for b in blockers):
            q = (
                f"{spec.item} ka {' '.join(spec.variant_keywords)} nahi mila — "
                f"regular (Rs.{cand.unit_price}) le lun ya kuch aur dhoondhun?"
            )
        elif any("budget exceeded" in b for b in blockers):
            q = (
                f"{spec.quantity} x {cand.product_name} = Rs.{total_price}, budget "
                f"Rs.{spec.budget} se zyada — kam kar dun ya budget badha dein?"
            )
        elif any("auto-pay limit" in b for b in blockers):
            q = f"Order total Rs.{total_price} hai (bada amount) — confirm karke order karun?"
        else:
            q = f"{cand.product_name} (Rs.{total_price}) theek hai? Confirm karun."

    return Decision(
        action=action,
        score=total,
        reasons=reasons,
        blockers=blockers,
        total_price=total_price,
        audit_id=f"APX-{uuid.uuid4().hex[:8].upper()}",
        user_question=q,
    )
