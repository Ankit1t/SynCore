"""
AutoPilot Confidence Scorer — ONDC Shopping Agent
==================================================
Plug-in module: Offer Ranking ke baad, ONDC SELECT se pehle use karo.

3 decisions deta hai:
  AUTO_EXECUTE   -> chupchap order (user ko sirf "Done" dikhega)
  EXECUTE_NOTIFY -> order + baad mein inform
  ASK_USER       -> ruk jao, ek clean sawaal poocho

Hard rules score se UPAR hote hain (variant mismatch, budget cross,
auto-pay limit) — yeh tumhare Maggi bug ka permanent guard hai.

Zero dependencies — pure stdlib. Kahin bhi drop karo.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import time
import uuid

AUTO_PAY_LIMIT = 500.0   # isse upar hamesha user confirm karega
AUTO_EXECUTE_MIN = 85    # score >= 85  -> silent order
EXECUTE_NOTIFY_MIN = 60  # score 60-84  -> order + inform


class Action(Enum):
    AUTO_EXECUTE = "AUTO_EXECUTE"
    EXECUTE_NOTIFY = "EXECUTE_NOTIFY"
    ASK_USER = "ASK_USER"


@dataclass
class OrderSpec:
    """Phase-1 Intent Parser ka output"""
    item: str                          # "Maggi noodles"
    variant_keywords: list = field(default_factory=list)  # ["mega pack"]
    quantity: int = 1
    budget: float = None               # total ceiling, e.g. 250
    brand_lock: str = None             # "Amul" ya None


@dataclass
class Candidate:
    """Normalized product (Offer Ranking ka best offer)"""
    product_name: str                  # "Maggi 2-Min Noodles Mega Pack 708g"
    brand: str = ""
    size_text: str = ""                # "708g" / "12 servings"
    unit_price: float = 0.0
    quantity_available: int = 99
    seller_rating: float = 0.0         # 0-5
    product_rating: float = 0.0        # 0-5
    review_count: int = 0
    eta_minutes: int = 0
    in_stock: bool = True
    user_ordered_before: bool = False  # history memory se aayega
    same_brand_before: bool = False


@dataclass
class Decision:
    action: Action
    score: int
    reasons: list
    blockers: list
    total_price: float
    audit_id: str                      # silent audit log ke liye
    user_question: str = ""            # sirf ASK_USER pe


# ---------------------------------------------------------------- scorers
def score_variant(spec: OrderSpec, cand: Candidate):
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
    return 0, f"VARIANT MISMATCH: asked {kws}, product name has none"


def score_price(spec: OrderSpec, cand: Candidate):
    total = round(cand.unit_price * spec.quantity, 2)
    if spec.budget is None:
        return 20, f"no budget constraint (total Rs.{total})"
    if total <= spec.budget:
        return 20, f"total Rs.{total} within budget Rs.{spec.budget}"
    if total <= spec.budget * 1.1:
        return 10, f"total Rs.{total} slightly over budget Rs.{spec.budget}"
    return 0, f"total Rs.{total} EXCEEDS budget Rs.{spec.budget}"


def score_seller(cand: Candidate):
    r = cand.seller_rating
    if r >= 4.5: return 15, f"seller rating {r} excellent"
    if r >= 4.0: return 12, f"seller rating {r} good"
    if r >= 3.5: return 8,  f"seller rating {r} average"
    if r > 0:    return 4,  f"seller rating {r} low"
    return 8, "seller rating unknown (neutral)"


def score_reviews(cand: Candidate):
    r, n = cand.product_rating, cand.review_count
    if r >= 4.3 and n >= 100: return 15, f"product {r}/5 on {n} reviews — trusted"
    if r >= 4.0: return 12, f"product {r}/5 good"
    if r >= 3.5: return 8,  f"product {r}/5 average"
    if r > 0:    return 4,  f"product {r}/5 weak"
    return 8, "no reviews (neutral)"


def score_history(spec: OrderSpec, cand: Candidate):
    if cand.user_ordered_before: return 10, "user ne yehi product pehle manga hai"
    if cand.same_brand_before:   return 6,  "user ka same-brand history hai"
    return 3, "new product/brand for user"


# ---------------------------------------------------------------- engine
def decide(spec: OrderSpec, cand: Candidate, auto_pay_limit=AUTO_PAY_LIMIT) -> Decision:
    s = {}
    s["variant_40"],  vmsg = score_variant(spec, cand)
    s["price_20"],    pmsg = score_price(spec, cand)
    s["seller_15"],   smsg = score_seller(cand)
    s["reviews_15"],  rmsg = score_reviews(cand)
    s["history_10"],  hmsg = score_history(spec, cand)
    total = sum(s.values())
    reasons = [vmsg, pmsg, smsg, rmsg, hmsg]

    # ---- HARD RULES (score se upar) ----
    blockers = []
    total_price = round(cand.unit_price * spec.quantity, 2)

    if not cand.in_stock:
        blockers.append("out of stock")
    if spec.variant_keywords and s["variant_40"] == 0:
        blockers.append("variant mismatch — silent downgrade FORBIDDEN")
    if spec.budget is not None and total_price > spec.budget:
        blockers.append(f"budget exceeded (Rs.{total_price} > Rs.{spec.budget})")
    if spec.quantity > cand.quantity_available:
        blockers.append(f"only {cand.quantity_available} units in stock, asked {spec.quantity}")
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

    # user-facing question (ASK_USER pe) — ek clean line, no tech jargon
    q = ""
    if action == Action.ASK_USER:
        if any("variant mismatch" in b for b in blockers):
            q = (f"{spec.item} ka {' '.join(spec.variant_keywords)} stock mein nahi mila. "
                 f"Regular pack (Rs.{cand.unit_price}) le lun, ya kuch aur dhoondhun?")
        elif any("budget exceeded" in b for b in blockers):
            q = (f"{spec.quantity} x {cand.product_name} = Rs.{total_price}, "
                 f"budget Rs.{spec.budget} se zyada hai. "
                 f"1 unit (Rs.{cand.unit_price}) kar dun ya budget badha dein?")
        elif any("auto-pay limit" in b for b in blockers):
            q = (f"Order total Rs.{total_price} hai (bada amount). "
                 f"Confirm karke order karun?")
        else:
            q = f"{cand.product_name} (Rs.{total_price}) theek hai? Confirm karun."

    audit_id = f"APX-{uuid.uuid4().hex[:8].upper()}"
    return Decision(action, total, reasons, blockers, total_price, audit_id, q)


# ---------------------------------------------------------------- audit log
def audit_log(spec: OrderSpec, cand: Candidate, d: Decision) -> dict:
    """Har auto-decision ka silent receipt — DB/JSON file mein append karo.
    Jab user bole 'maine yeh nahi manga tha' — yahi entry bachayegi."""
    return {
        "audit_id": d.audit_id,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "action": d.action.value,
        "score": d.score,
        "intent": asdict(spec),
        "candidate": asdict(cand),
        "score_reasons": d.reasons,
        "blockers": d.blockers,
        "total_price": d.total_price,
    }


# ---------------------------------------------------------------- UX screen
def render_result(spec: OrderSpec, cand: Candidate, d: Decision) -> str:
    """User ko SIRF yeh dikhega — bas itna hi."""
    eta = f" • ~{cand.eta_minutes} min delivery" if cand.eta_minutes else ""
    if d.action == Action.AUTO_EXECUTE:
        return (f"[OK] Ho gaya! {spec.quantity}x {cand.product_name} "
                f"Rs.{d.total_price}{eta} • Order ID {d.audit_id}")
    if d.action == Action.EXECUTE_NOTIFY:
        return (f"[OK] Done — {spec.quantity}x {cand.product_name} Rs.{d.total_price}{eta}. "
                f"(Note: {'; '.join(d.reasons[-2:])})")
    return f"[?] {d.user_question}"


# ---------------------------------------------------------------- DEMO
if __name__ == "__main__":
    spec = OrderSpec(item="Maggi noodles", variant_keywords=["mega pack"],
                     quantity=2, budget=250)

    print("=" * 64)
    print("CASE 1: Tumhara ORIGINAL BUG — agent regular pack utha raha tha")
    print("=" * 64)
    buggy = Candidate(product_name="Maggi (market est.) 2 pack", brand="Maggi",
                      unit_price=28, product_rating=4.1, review_count=320,
                      seller_rating=4.4, eta_minutes=12)
    d1 = decide(spec, buggy)
    print(render_result(spec, buggy, d1))
    print(f"   -> action={d1.action.value}, score={d1.score}")
    print(f"   -> blockers={d1.blockers}")
    print("   [FIXED] pehle yeh chupchap order ho jata. Ab ruk ke poochta hai.\n")

    print("=" * 64)
    print("CASE 2: Perfect mega pack — autopilot chupchap order karega")
    print("=" * 64)
    good = Candidate(product_name="Maggi 2-Min Noodles Mega Pack", brand="Maggi",
                     size_text="708g", unit_price=100, product_rating=4.3,
                     review_count=230, seller_rating=4.6, eta_minutes=30,
                     user_ordered_before=True)
    d2 = decide(spec, good)
    print(render_result(spec, good, d2))
    print(f"   -> action={d2.action.value}, score={d2.score}")
    print(f"   -> audit: {json.dumps(audit_log(spec, good, d2), ensure_ascii=False)[:120]}...\n")

    print("=" * 64)
    print("CASE 3: Budget cross — clean sawaal user ke paas jayega")
    print("=" * 64)
    costly = Candidate(product_name="Maggi 2-Min Noodles Mega Pack", brand="Maggi",
                       size_text="708g", unit_price=140, product_rating=4.3,
                       review_count=230, seller_rating=4.6, eta_minutes=30)
    d3 = decide(spec, costly)
    print(render_result(spec, costly, d3))
    print(f"   -> action={d3.action.value}, score={d3.score}")
    print(f"   -> blockers={d3.blockers}")
