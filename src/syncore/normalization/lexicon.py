"""Grocery lexicon: maps Hindi/Hinglish/variant terms to canonical names.

Kept as data (not code) so it can later be moved to a database or learned. This
is deterministic domain knowledge, not LLM output.
"""

from __future__ import annotations

# canonical_name -> set of synonyms/aliases (all lower case, no units)
SYNONYMS: dict[str, list[str]] = {
    "potato": ["potato", "potatoes", "aloo", "alu", "batata"],
    "onion": ["onion", "onions", "pyaz", "pyaaz", "kanda"],
    "tomato": ["tomato", "tomatoes", "tamatar"],
    "green chilli": ["green chilli", "green chili", "chilli", "chili", "mirch", "hari mirch", "mirchi"],
    "ginger": ["ginger", "adrak"],
    "garlic": ["garlic", "lehsun", "lahsun"],
    "maggi": ["maggi", "maggi noodles", "masala noodles", "instant noodles"],
    "rice": ["rice", "chawal", "chaawal"],
    "wheat flour": ["atta", "wheat flour", "gehun atta", "chakki atta"],
    "milk": ["milk", "doodh", "dudh"],
    "sugar": ["sugar", "cheeni", "chini"],
    "salt": ["salt", "namak"],
    "cooking oil": ["oil", "cooking oil", "tel", "refined oil", "sunflower oil"],
    "eggs": ["egg", "eggs", "anda", "ande"],
    "bread": ["bread", "double roti", "pav"],
    "butter": ["butter", "makhan"],
    "paneer": ["paneer", "cottage cheese"],
    "tea": ["tea", "chai", "chai patti"],
    "biscuits": ["biscuit", "biscuits", "cookies"],
}

# Category assignment for canonical names (grocery MVP; all grocery here).
CATEGORY: dict[str, str] = {name: "grocery" for name in SYNONYMS}

# Items that are inherently count-based rather than weight/volume based.
COUNT_BASED = {"maggi", "eggs", "bread", "biscuits"}

# Brand tokens we recognize (helps separate brand from product name).
KNOWN_BRANDS = {
    "maggi": "Nestle",
    "aashirvaad": "Aashirvaad",
    "amul": "Amul",
    "tata": "Tata",
    "fortune": "Fortune",
    "britannia": "Britannia",
    "nestle": "Nestle",
}

# Reverse index: alias -> canonical_name (built once).
_ALIAS_INDEX: dict[str, str] = {}
for _canonical, _aliases in SYNONYMS.items():
    for _alias in _aliases:
        _ALIAS_INDEX[_alias] = _canonical


def canonical_for(term: str) -> str | None:
    """Return the canonical name for a raw term, or None if unknown."""
    return _ALIAS_INDEX.get(term.strip().lower())


def alias_index() -> dict[str, str]:
    return dict(_ALIAS_INDEX)
