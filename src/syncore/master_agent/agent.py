"""KIRANA Master Agent — deterministic implementation of the v1 JSON contract.

decide(user_request, available_offers) -> dict

Jobs: UNDERSTAND -> MATCH -> BUILD -> BUDGET GUARD -> DECIDE -> TALK.
All money math is computed here (never by an LLM): line_total = quantity *
unit_price, total = sum(line_total), and the budget is a hard ceiling.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .catalog import (
    ALIASES,
    DEFAULT_UNIT,
    EST_PRICE,
    FILLER,
    HINDI_NUMBERS,
    VAGUE,
    essentiality,
)

_ALIASES_BY_LEN = sorted(ALIASES, key=len, reverse=True)
_WEIGHT_UNITS = {"kg", "l"}
_COUNT_UNITS = {"pack", "piece", "loaf", "dozen"}

# Large-pack qualifiers. When the user asks for a mega/family/jumbo pack we must
# price and name it as that variant — never silently downgrade to a regular
# pack (the "Maggi bug"). Multiplier is applied to a known base estimate.
_VARIANT_MULTIPLIERS: list[tuple[tuple[str, ...], float]] = [
    (("mega", "jumbo", "xxl", "bumper"), 7.0),
    (("family", "party", "value", "super saver", "combo", "bulk"), 5.0),
]
_VARIANT_SCAN = re.compile(
    r"\b(mega\s*pack|mega|jumbo|family\s*pack|family|party\s*pack|party|"
    r"value\s*pack|value|super\s*saver|combo\s*pack|combo|bulk|xxl|bumper)\b",
    re.I,
)


def _extract_variant(fragment: str) -> list[str]:
    """Pull pack/size qualifiers from a raw fragment (deterministic fallback)."""
    out: list[str] = []
    for m in _VARIANT_SCAN.finditer(fragment):
        v = re.sub(r"\s+", " ", m.group(0).strip().lower())
        if v not in out:
            out.append(v)
    return out[:5]


def _variant_multiplier(variants: list[str]) -> float:
    joined = " ".join(variants).lower()
    mult = 1.0
    for kws, factor in _VARIANT_MULTIPLIERS:
        if any(k in joined for k in kws):
            mult = max(mult, factor)
    return mult


def _display_name(item: dict[str, Any], base_title: str) -> str:
    """Compose an honest product name that reflects brand + variant."""
    brand = (item.get("brand") or "").strip()
    variants = item.get("variant_keywords") or []
    name = f"{brand} {base_title}".strip() if brand and brand.lower() not in base_title.lower() else base_title
    if variants:
        name = f"{name} — {', '.join(v.title() for v in variants)}"
    return name

# ---------------------------------------------------------------- budget ----
# A money number may carry thousands separators, e.g. "1,000" or the Indian
# "1,00,000". Capture the digits+commas, then strip commas before float().
_NUM = r"\d[\d,]*(?:\.\d+)?"
_BUDGET_PATTERNS = [
    re.compile(r"(?:₹|rs\.?|inr|rupees?)\s*(" + _NUM + r")", re.I),
    re.compile(r"(" + _NUM + r")\s*(?:rupees?|rs\.?|inr|₹)", re.I),
    re.compile(
        r"(?:under|below|within|max(?:imum)?|upto|up\s*to|budget(?:\s+of)?|less\s+than)\s*"
        r"(?:₹|rs\.?|inr)?\s*(" + _NUM + r")",
        re.I,
    ),
    re.compile(r"(" + _NUM + r")\s*(?:ke\s+andar|andar|tak|ka\b|ke\b)", re.I),
]


def _parse_money(raw: str) -> float | None:
    """'1,000' -> 1000.0, '1,00,000' -> 100000.0. None if not a number."""
    try:
        return float(raw.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def _extract_budget(text: str) -> tuple[float | None, str]:
    """Return (budget_inr, text_with_budget_removed)."""
    for pat in _BUDGET_PATTERNS:
        m = pat.search(text)
        if m:
            budget = _parse_money(m.group(1))
            if budget is None:
                continue
            cleaned = text[: m.start()] + " " + text[m.end() :]
            return budget, cleaned
    return None, text


# --------------------------------------------------------------- numbers ----
def _apply_hindi_numbers(fragment: str) -> str:
    def repl(m: re.Match[str]) -> str:
        word = m.group(0).lower()
        val = HINDI_NUMBERS.get(word)
        return str(int(val)) if val is not None and float(val).is_integer() else str(val)

    pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in HINDI_NUMBERS) + r")\b", re.I)
    return pattern.sub(repl, fragment)


_QTY_RE = re.compile(
    r"(?P<val>\d+(?:\.\d+)?)\s*(?P<unit>kg|kilograms?|kilo|g|grams?|gm|l|litres?|liters?|ltr|ml|"
    r"packets?|packs?|pcs?|pieces?|dozen|loaf|loaves)?",
    re.I,
)
_UNIT_MAP = {
    "kg": "kg", "kilo": "kg", "kilogram": "kg", "kilograms": "kg",
    "g": "g", "gram": "g", "grams": "g", "gm": "g",
    "l": "l", "litre": "l", "litres": "l", "liter": "l", "liters": "l", "ltr": "l",
    "ml": "ml",
    "packet": "pack", "packets": "pack", "pack": "pack", "packs": "pack",
    "pcs": "piece", "pc": "piece", "piece": "piece", "pieces": "piece",
    "dozen": "dozen", "loaf": "loaf", "loaves": "loaf",
}


def _parse_quantity(fragment: str, canonical: str) -> tuple[float | None, str, bool]:
    """Return (quantity_or_None, unit, explicit_flag), normalizing g->kg, ml->l."""
    if any(v in fragment for v in VAGUE):
        return None, DEFAULT_UNIT.get(canonical, "kg"), False

    for m in _QTY_RE.finditer(fragment):
        val = float(m.group("val"))
        raw_unit = (m.group("unit") or "").lower()
        if raw_unit:
            unit = _UNIT_MAP.get(raw_unit, raw_unit)
            if unit == "g":
                return round(val / 1000, 4), "kg", True
            if unit == "ml":
                return round(val / 1000, 4), "l", True
            if unit == "dozen":
                return val * 12, "piece", True
            return val, unit, True
        # bare number with no unit -> treat as count for count-items, else qty in default unit
        default = DEFAULT_UNIT.get(canonical, "kg")
        return val, default, True

    return None, DEFAULT_UNIT.get(canonical, "kg"), False


def _match_canonical(fragment: str) -> str | None:
    for alias in _ALIASES_BY_LEN:
        if re.search(rf"\b{re.escape(alias)}\b", fragment):
            return ALIASES[alias]
    return None


def _slug(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())[:40] or "item"


def _normalize_llm_unit(unit: str | None, quantity: float | None, canonical: str) -> tuple[float | None, str]:
    """Map an LLM unit to our canonical units, converting g->kg and ml->l."""
    u = _UNIT_MAP.get((unit or "").lower(), (unit or "").lower())
    if u == "g":
        return (round(quantity / 1000, 4) if quantity is not None else None), "kg"
    if u == "ml":
        return (round(quantity / 1000, 4) if quantity is not None else None), "l"
    if u == "dozen":
        return (quantity * 12 if quantity is not None else None), "piece"
    if u in {"kg", "l", "piece", "pack", "loaf"}:
        return quantity, u
    return quantity, DEFAULT_UNIT.get(canonical, "unit")


# --------------------------------------------------------------- understand -
_SPLIT_RE = re.compile(r"\s*(?:,|\+|&|\band\b|\baur\b|\bplus\b|\n)\s*", re.I)


def understand(text: str, provider: Any = None) -> tuple[float | None, list[dict[str, Any]]]:
    """LLM-first understanding (handles ANY item); deterministic fallback.

    When a real LLM is configured, items are not limited to the grocery lexicon
    — electronics, ice cream, anything gets parsed and priced. If the LLM is
    unavailable or returns nothing usable, we fall back to the deterministic
    grocery parser so the system always works.
    """
    from ..llm.provider import get_provider
    from .llm_extract import extract_intent

    provider = provider or get_provider()
    if getattr(provider, "name", "deterministic") != "deterministic":
        parsed = extract_intent(text, provider)
        if parsed and parsed.get("items"):
            items: list[dict[str, Any]] = []
            seen: set[str] = set()
            for it in parsed["items"]:
                name = it["name"]
                canonical = _match_canonical(name.lower()) or _slug(name)
                if canonical in seen:
                    continue
                seen.add(canonical)
                qty, unit = _normalize_llm_unit(it.get("unit"), it.get("quantity"), canonical)
                items.append({
                    "raw": name[:60],
                    "canonical": canonical,
                    "quantity": qty,
                    "unit": unit,
                    "confidence": 0.9,
                    "est_price_inr": it.get("unit_price_inr"),
                    "brand": it.get("brand"),
                    "variant_keywords": it.get("variant_keywords") or [],
                })
            if items:
                # Money is deterministic: trust our budget regex first (it
                # reliably catches "under 3000", "₹3000", "3000 ka", ...), and
                # only fall back to the LLM's budget if the regex found none.
                det_budget, _ = _extract_budget(text)
                budget = det_budget if det_budget is not None else parsed.get("budget_inr")
                return budget, items
    return _understand(text)


def _understand(text: str) -> tuple[float | None, list[dict[str, Any]]]:
    original = text.strip()
    budget, body = _extract_budget(original)
    body = _apply_hindi_numbers(body.lower())

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_frag in _SPLIT_RE.split(body):
        frag = raw_frag.strip()
        if not frag:
            continue
        canonical = _match_canonical(frag)
        if canonical is None or canonical in seen:
            continue
        qty, unit, explicit = _parse_quantity(frag, canonical)
        confidence = 0.95 if explicit else (0.6 if qty is None else 0.8)
        items.append({
            "raw": raw_frag.strip()[:60],
            "canonical": canonical,
            "quantity": qty,
            "unit": unit,
            "confidence": confidence,
            "brand": None,
            "variant_keywords": _extract_variant(raw_frag),
        })
        seen.add(canonical)
    return budget, items


# ------------------------------------------------------------------ offers --
def _normalize_offers(available: Any) -> list[dict[str, Any]]:
    if not isinstance(available, list):
        return []
    out: list[dict[str, Any]] = []
    for o in available:
        if not isinstance(o, dict):
            continue
        canon = o.get("canonical") or o.get("category")
        canon = ALIASES.get(str(canon).lower()) if canon else None
        if canon is None:
            name = str(o.get("product_name") or o.get("name") or o.get("title") or "").lower()
            for alias in _ALIASES_BY_LEN:
                if re.search(rf"\b{re.escape(alias)}\b", name):
                    canon = ALIASES[alias]
                    break
        price = o.get("unit_price", o.get("price"))
        if canon is None or price is None:
            continue
        out.append({
            "offer_id": str(o.get("offer_id") or o.get("id") or "offer"),
            "name": str(o.get("product_name") or o.get("name") or o.get("title") or canon),
            "canonical": canon,
            "unit_price": float(price),
            "unit": str(o.get("unit") or DEFAULT_UNIT.get(canon, "unit")),
            "in_stock": bool(o.get("in_stock", True)),
            "size": float(o.get("quantity") or o.get("pack_size") or 1),
        })
    return out


# ------------------------------------------------------------------ build ---
def _build_line(item: dict[str, Any], offers: list[dict[str, Any]], gen_counter: list[int]) -> dict[str, Any]:
    canonical = item["canonical"]
    need_qty = item["quantity"] if item["quantity"] is not None else 1.0
    unit = item["unit"] or DEFAULT_UNIT.get(canonical, "kg")

    candidates = [o for o in offers if o["canonical"] == canonical]
    in_stock = [o for o in candidates if o["in_stock"]] or candidates
    if in_stock:
        offer = min(in_stock, key=lambda o: o["unit_price"])
        o_unit = offer["unit"]
        if o_unit in _COUNT_UNITS or o_unit not in _WEIGHT_UNITS:
            qty = max(1, math.ceil(need_qty))
        else:
            qty = need_qty
        line_total = round(qty * offer["unit_price"], 2)
        return {
            "offer_id": offer["offer_id"], "product_name": offer["name"], "satisfies": canonical,
            "quantity": qty, "unit": o_unit, "unit_price": offer["unit_price"],
            "line_total": line_total, "estimated": False,
            "reason": "cheapest in-stock offer" if offer["in_stock"] else "only offer (out of stock)",
        }

    # No matching offer -> CREATE a realistic product (estimated).
    # Known grocery items use the built-in price table; anything else (from the
    # LLM: electronics, ice cream, ...) uses the LLM's estimated price.
    variants = item.get("variant_keywords") or []
    known = EST_PRICE.get(canonical)
    if known is not None:
        base_price, gunit = known
        # Known base prices are for a REGULAR pack; scale up for large variants
        # so the budget math reflects the actual mega/family pack the user asked.
        price = round(base_price * _variant_multiplier(variants), 2)
    else:
        # LLM already prices the exact variant it extracted.
        est = item.get("est_price_inr")
        price = float(est) if est else 30.0
        gunit = item.get("unit") or DEFAULT_UNIT.get(canonical, "unit")
    if gunit in _COUNT_UNITS:
        qty = max(1, math.ceil(need_qty))
    else:
        qty = need_qty
    gen_counter[0] += 1
    product_name = f"{_display_name(item, canonical.title())} (market est.)"
    return {
        "offer_id": f"generated-{gen_counter[0]}", "product_name": product_name,
        "satisfies": canonical, "quantity": qty, "unit": gunit, "unit_price": price,
        "line_total": round(qty * price, 2), "estimated": True,
        "reason": ("created; " + (", ".join(variants) if variants else "no offer available")),
    }


def _total(lines: list[dict[str, Any]]) -> float:
    return round(sum(line["line_total"] for line in lines), 2)


# --------------------------------------------------------------- decide -----
def decide(user_request: str, available_offers: Any = "NONE", *, provider: Any = None) -> dict[str, Any]:
    budget, items = understand(user_request or "", provider)

    # Rule 6: nothing identifiable.
    if not items:
        return {
            "understanding": {"budget_inr": budget, "items": [], "notes": "no item recognized"},
            "basket": {"lines": [], "total": 0},
            "budget_check": {"within_budget": True, "remaining_inr": budget, "over_by_inr": None},
            "decisions": {"substitutions": [], "quantity_changes": [], "dropped_items": [], "created_products": []},
            "next_action": "ASK_USER",
            "options_for_user": [],
            "review": None,
            "message_to_user": (
                "I couldn't identify anything to order. Try naming items, e.g. "
                "\"1 kg potatoes, 2 packs of Maggi, 1 L milk\". Tip: connect a real LLM "
                "(Gemini/Groq/Ollama) to order any product, not just groceries."
            ),
        }

    offers = _normalize_offers(available_offers)
    gen_counter = [0]
    lines = [_build_line(it, offers, gen_counter) for it in items]

    substitutions: list[str] = []
    quantity_changes: list[str] = []
    dropped_items: list[str] = []
    created = [f"{ln['offer_id']}: {ln['product_name']} @ ₹{ln['unit_price']:g}/{ln['unit']}"
               for ln in lines if ln["estimated"]]

    total = _total(lines)

    # ----- BUDGET GUARD (hard ceiling) -----
    if budget is not None and total > budget:
        # (b) reduce quantities > 1 down to 1, largest line first.
        for ln in sorted(lines, key=lambda x: -x["line_total"]):
            if total <= budget:
                break
            if ln["quantity"] and ln["quantity"] > 1:
                old = ln["quantity"]
                ln["quantity"] = 1
                ln["line_total"] = round(ln["unit_price"], 2)
                quantity_changes.append(f"{ln['satisfies']}: {old}->1 to fit budget")
                total = _total(lines)

        # (c) drop least-essential items (snacks first) until within budget.
        while total > budget and lines:
            victim = min(lines, key=lambda x: (essentiality(x["satisfies"]), -x["line_total"]))
            # only auto-drop clearly non-essential items (snacks); stop otherwise.
            if essentiality(victim["satisfies"]) > 3:
                break
            lines.remove(victim)
            dropped_items.append(f"{victim['satisfies']}: dropped (least essential, over budget)")
            total = _total(lines)

    total = _total(lines)
    within = budget is None or total <= budget
    remaining = round(budget - total, 2) if (budget is not None and within) else None
    over_by = round(total - budget, 2) if (budget is not None and not within) else None

    # ----- DECIDE -----
    options: list[dict[str, Any]] = []
    if not within:
        next_action = "ASK_USER"
        options = _build_options(lines, budget)
    else:
        next_action = "PROCEED_TO_CHECKOUT"

    message = _message(items, lines, total, budget, within, over_by, created, dropped_items, next_action)
    review = _build_review(items, lines, total, budget, within)

    return {
        "understanding": {
            "budget_inr": budget,
            "items": items,
            "notes": _notes(items, offers, available_offers),
        },
        "basket": {"lines": lines, "total": total},
        "budget_check": {"within_budget": within, "remaining_inr": remaining, "over_by_inr": over_by},
        "decisions": {
            "substitutions": substitutions,
            "quantity_changes": quantity_changes,
            "dropped_items": dropped_items,
            "created_products": created,
        },
        "next_action": next_action,
        "options_for_user": options,
        "review": review,
        "message_to_user": message,
    }


def _build_review(
    items: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    total: float,
    budget: float | None,
    within: bool,
) -> dict[str, Any]:
    """Self-review + confidence pass over the built basket.

    Reuses the confidence scorer's hard rules (variant mismatch, budget breach,
    auto-pay limit, brand lock) to produce an autonomy verdict. This is purely
    informational — it never overrides the pipeline's next_action.
    """
    from .confidence import Action, Candidate, OrderSpec
    from .confidence import decide as score_candidate

    req_variants: list[str] = []
    brand_lock: str | None = None
    for it in items:
        req_variants += it.get("variant_keywords") or []
        if not brand_lock and it.get("brand"):
            brand_lock = it["brand"]

    combined_name = " | ".join(ln["product_name"] for ln in lines)
    spec = OrderSpec(
        item=", ".join(dict.fromkeys(ln["satisfies"] for ln in lines)) or "order",
        variant_keywords=req_variants,
        quantity=1,
        budget=budget,
        brand_lock=brand_lock,
    )
    # cand.brand carries the full basket name so the brand-lock substring check
    # verifies the locked brand is actually reflected in what we're ordering.
    cand = Candidate(
        product_name=combined_name,
        brand=combined_name,
        unit_price=float(total),
        quantity_available=99,
        in_stock=bool(lines),
    )
    d = score_candidate(spec, cand)

    if not within or any(("variant mismatch" in b or "brand lock" in b) for b in d.blockers):
        verdict = "FAIL"
    elif d.blockers or d.action is not Action.AUTO_EXECUTE:
        verdict = "PASS_WITH_NOTES"
    else:
        verdict = "PASS"

    return {
        "verdict": verdict,
        "confidence": d.score,
        "autopilot": d.action.value,
        "reasons": d.reasons,
        "concerns": d.blockers,
        "audit_id": d.audit_id,
        "question": d.user_question,
    }


def _build_options(lines: list[dict[str, Any]], budget: float) -> list[dict[str, Any]]:
    opts: list[dict[str, Any]] = []
    if not lines:
        return opts
    # Option 1: drop the most expensive line.
    priciest = max(lines, key=lambda x: x["line_total"])
    opts.append({
        "option": f"Drop {priciest['satisfies']}", "action": "drop",
        "resulting_total": round(_total(lines) - priciest["line_total"], 2),
    })
    # Option 2: reduce the largest-quantity line to 1.
    reducible = [ln for ln in lines if ln["quantity"] and ln["quantity"] > 1]
    if reducible:
        big = max(reducible, key=lambda x: x["line_total"])
        delta = round(big["line_total"] - big["unit_price"], 2)
        opts.append({
            "option": f"Reduce {big['satisfies']} to 1 {big['unit']}", "action": "reduce",
            "resulting_total": round(_total(lines) - delta, 2),
        })
    # Option 3: keep everything, raise budget.
    opts.append({
        "option": f"Keep all (need ₹{_total(lines):g})", "action": "increase_budget",
        "resulting_total": _total(lines),
    })
    return opts[:3]


def _notes(items: list[dict[str, Any]], offers: list[dict[str, Any]], available: Any) -> str:
    if available == "NONE" or not offers:
        return f"{len(items)} item(s) understood; no live offers, using market estimates"
    return f"{len(items)} item(s) understood; matched against {len(offers)} offer(s)"


def _message(items, lines, total, budget, within, over_by, created, dropped, next_action) -> str:
    if budget is None:
        head = f"Basket ready — total ₹{total:g}."
    elif within:
        head = f"Done — total ₹{total:g}, within your ₹{budget:g} budget."
    else:
        head = f"Total ₹{total:g} is ₹{over_by:g} over your ₹{budget:g} budget — see the options below."
    extras = []
    if created:
        extras.append("used market estimates for some items")
    if dropped:
        extras.append(f"removed {len(dropped)} item(s) to fit the budget")
    if next_action == "PROCEED_TO_CHECKOUT":
        extras.append("ready to build your cart")
    tail = ("; " + ", ".join(extras)) if extras else ""
    return (head + tail)[:240]


# ------------------------------------------------------------------ CLI -----
def _main() -> int:  # pragma: no cover
    import json
    import sys

    req = " ".join(sys.argv[1:]) or "500 ke andar 1kg aloo, 100g mirch aur 2 maggi"
    print(json.dumps(decide(req, "NONE"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
