"""Deterministic, Hinglish-aware intent parser.

Turns requests like:
    "₹500 ke andar 1kg aloo, 100g mirch aur 2 Maggi order kar."
into a structured ShoppingRequest.

Design choice: parsing budgets and quantities is deterministic (regex + the
grocery lexicon), because arithmetic and money must never depend on an LLM.
An LLM can be layered on top later for ambiguity resolution via LLMProvider,
but the numeric extraction stays here.
"""

from __future__ import annotations

import re

from ..config import get_settings
from ..domain.enums import ConstraintType, Unit
from ..domain.errors import IntentParseError
from ..domain.models import (
    BudgetPolicy,
    Quantity,
    ShoppingItem,
    ShoppingPolicy,
    ShoppingRequest,
)
from ..normalization import lexicon
from ..normalization.normalizer import parse_quantity

# Budget patterns, tried in order. A budget may be currency-anchored (₹500,
# rs 500, 500 rupees), a bare amount followed by a Hindi postposition
# ("500 ke andar", "500 tak"), or a bare amount after an English hint word
# ("under 100", "below 250", "budget of 300"). Bare quantities like "1kg" or
# "2 maggi" never match because they lack a budget marker.
_BUDGET_PATTERNS = [
    re.compile(r"(?:₹|rs\.?|inr|rupees?)\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:rupees?|rs\.?|inr|₹)", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:ke\s+andar|andar|tak|se\s+kam|se\s+neeche)", re.IGNORECASE),
    re.compile(
        r"(?:under|below|within|max(?:imum)?|budget(?:\s+of)?|upto|up\s*to|less\s+than)\s*"
        r"(?:₹|rs\.?|inr|rupees?)?\s*(\d+(?:\.\d+)?)",
        re.IGNORECASE,
    ),
]

_HARD_BUDGET_HINTS = re.compile(
    r"\b(under|below|within|max|ke\s+andar|andar|tak|budget|se\s+kam|kam\s+se|se\s+neeche)\b",
    re.IGNORECASE,
)

# Separators between items: commas, "and", Hindi "aur"/"or", "plus", "&".
_ITEM_SPLIT_RE = re.compile(r"\s*(?:,|\band\b|\baur\b|\bor\b|\bplus\b|&|\+)\s*", re.IGNORECASE)

# Noise words/phrases to strip from the request before item extraction.
_NOISE = [
    r"order\s+kar(?:na|o)?\s+hai", r"order\s+kar(?:na|o)?", r"order\s+me", r"mangwa\s*lo",
    r"chahiye", r"chaahiye", r"please", r"pls", r"i\s+want\s+to\s+buy", r"i\s+want",
    r"buy\s+me", r"get\s+me", r"order\s+me", r"dinner\s+ke\s+liye", r"lunch\s+ke\s+liye",
    r"ke\s+liye", r"mujhe", r"order", r"kar\b", r"karo\b", r"karna\b", r"lena\s+hai", r"le\s+lo",
]
_NOISE_RE = re.compile("|".join(_NOISE), re.IGNORECASE)


def _extract_budget(text: str) -> BudgetPolicy:
    settings = get_settings()
    for pattern in _BUDGET_PATTERNS:
        m = pattern.search(text)
        if m:
            # An explicitly stated budget is a HARD constraint by default.
            return BudgetPolicy(limit=float(m.group(1)), currency=settings.default_currency,
                                constraint_type=ConstraintType.HARD)
    return BudgetPolicy(limit=None, currency=settings.default_currency,
                        constraint_type=ConstraintType.HARD)


def _strip_budget(text: str) -> str:
    for pattern in _BUDGET_PATTERNS:
        text = pattern.sub(" ", text)
    text = _HARD_BUDGET_HINTS.sub(" ", text)
    return text


def _match_canonical(fragment: str) -> str | None:
    """Find a canonical grocery name inside a fragment (longest alias wins)."""
    lowered = fragment.lower()
    for alias in sorted(lexicon.alias_index(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            return lexicon.alias_index()[alias]
    return None


def _parse_item(fragment: str) -> ShoppingItem | None:
    fragment = _NOISE_RE.sub(" ", fragment).strip()
    fragment = re.sub(r"\s+", " ", fragment)
    if not fragment:
        return None

    canonical = _match_canonical(fragment)
    if canonical is None:
        return None

    count_based = canonical in lexicon.COUNT_BASED
    quantity = parse_quantity(fragment, count_based=count_based)
    if quantity is None:
        # default sensible quantity when the user omitted it
        quantity = (
            Quantity(value=1, unit=Unit.PIECE)
            if count_based
            else Quantity(value=1, unit=Unit.KG)
        )

    return ShoppingItem(
        raw_text=fragment,
        canonical_name=canonical,
        requested_quantity=quantity,
    )


def parse_request(text: str, *, user_id: str) -> ShoppingRequest:
    """Parse a natural-language request into a structured ShoppingRequest."""
    if not text or not text.strip():
        raise IntentParseError("empty request")

    original = text.strip()
    budget = _extract_budget(original)

    body = _strip_budget(original)
    fragments = _ITEM_SPLIT_RE.split(body)

    items: list[ShoppingItem] = []
    seen: set[str] = set()
    for frag in fragments:
        item = _parse_item(frag)
        if item and item.canonical_name not in seen:
            items.append(item)
            seen.add(item.canonical_name)

    if not items:
        supported = ", ".join(sorted(lexicon.SYNONYMS))
        raise IntentParseError(
            "Couldn't find any grocery items I recognize in that request. This MVP is "
            f"grocery-only. Try items like: {supported}.",
            details={"request": original, "supported_items": sorted(lexicon.SYNONYMS)},
        )

    settings = get_settings()
    return ShoppingRequest(
        user_id=user_id,
        raw_text=original,
        items=items,
        budget=budget,
        policy=ShoppingPolicy(
            objective=settings.default_objective,  # type: ignore[arg-type]
            minimum_rating=0.0,
        ),
    )
