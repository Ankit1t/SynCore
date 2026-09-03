"""Hinglish lexicon, Hindi numerals, unit defaults, estimated prices and
essentiality — the domain knowledge the Master Agent parses and builds against.

Prices are realistic Indian grocery estimates used only when AVAILABLE_OFFERS
has no match; every such line is flagged `estimated: true`.
"""

from __future__ import annotations

# alias -> canonical (spec JOB 1 map + english self-maps + common plurals/typos)
ALIASES: dict[str, str] = {
    # potato
    "aloo": "potato", "alu": "potato", "potato": "potato", "potatoes": "potato", "batata": "potato",
    # onion
    "pyaaz": "onion", "pyaz": "onion", "kanda": "onion", "onion": "onion", "onions": "onion",
    # tomato
    "tamatar": "tomato", "tomato": "tomato", "tomatoes": "tomato",
    # green chilli
    "mirch": "green chilli", "mirchi": "green chilli", "hari mirch": "green chilli",
    "chilli": "green chilli", "chili": "green chilli", "green chilli": "green chilli",
    # milk
    "doodh": "milk", "dudh": "milk", "milk": "milk",
    # flour
    "atta": "flour", "aata": "flour", "flour": "flour", "wheat flour": "flour",
    # rice
    "chawal": "rice", "chaawal": "rice", "rice": "rice",
    # sugar
    "cheeni": "sugar", "chini": "sugar", "sugar": "sugar",
    # salt
    "namak": "salt", "salt": "salt",
    # oil
    "tel": "oil", "oil": "oil", "cooking oil": "oil", "refined oil": "oil",
    # biscuits
    "biscuit": "biscuits", "biscuits": "biscuits", "cookies": "biscuits", "cookie": "biscuits",
    # chips
    "chips": "chips", "wafers": "chips",
    # maggi
    "maggi": "maggi", "noodles": "maggi",
    # eggs
    "anda": "eggs", "ande": "eggs", "egg": "eggs", "eggs": "eggs",
    # lentils
    "dal": "lentils", "daal": "lentils", "lentils": "lentils", "pulses": "lentils",
    # tea
    "chai": "tea", "tea": "tea", "chai patti": "tea",
    # curd
    "dahi": "curd", "curd": "curd", "yogurt": "curd",
    # bread
    "bread": "bread", "double roti": "bread", "pav": "bread",
    # ghee
    "ghee": "ghee", "clarified butter": "ghee",
    # a few more staples
    "butter": "butter", "makhan": "butter", "paneer": "paneer",
    # snacks / packaged
    "chocolate": "chocolate", "chocolates": "chocolate", "choco": "chocolate",
    "namkeen": "namkeen", "mixture": "namkeen", "sev": "namkeen",
    "cold drink": "cola", "cola": "cola", "coke": "cola", "pepsi": "cola", "soft drink": "cola",
    "juice": "juice", "fruit juice": "juice",
    "ice cream": "ice cream", "icecream": "ice cream", "ice-cream": "ice cream",
    # personal care
    "soap": "soap", "sabun": "soap", "shampoo": "shampoo", "toothpaste": "toothpaste",
    "manjan": "toothpaste", "paste": "toothpaste",
    # electronics
    "phone charger": "phone charger", "charger": "phone charger", "mobile charger": "phone charger",
    "bluetooth speaker": "bluetooth speaker", "speaker": "bluetooth speaker",
    "earphones": "earphones", "earphone": "earphones", "earbuds": "earphones", "headphones": "earphones",
}

HINDI_NUMBERS: dict[str, float] = {
    "aadha": 0.5, "adha": 0.5, "half": 0.5,
    "ek": 1, "dedh": 1.5, "do": 2, "dhai": 2.5, "teen": 3, "char": 4, "chaar": 4,
    "paanch": 5, "panch": 5, "che": 6, "cheh": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "dozen": 12, "darjan": 12,
}

# vague-quantity markers -> quantity null
VAGUE = {"thoda", "thodi", "kuch", "some", "bahut", "bhoot", "kaafi", "zyada", "jyada", "lots", "lot"}

# filler words to strip
FILLER = {
    "bro", "yaar", "yr", "mujhe", "muje", "please", "pls", "plz", "kar", "karde", "kardo",
    "karna", "chahiye", "chaiye", "dedo", "de", "do", "lelo", "order", "chahiye", "and",
    "aur", "bhi", "ka", "ke", "ki", "hai", "he", "jaldi", "jldi", "abhi", "na", "toh", "to",
}

# canonical -> (estimated unit_price INR, unit)
EST_PRICE: dict[str, tuple[float, str]] = {
    "potato": (40, "kg"), "onion": (35, "kg"), "tomato": (30, "kg"),
    "green chilli": (40, "kg"), "milk": (32, "l"), "flour": (45, "kg"),
    "rice": (60, "kg"), "sugar": (45, "kg"), "salt": (25, "kg"), "oil": (140, "l"),
    "biscuits": (20, "pack"), "chips": (15, "pack"), "maggi": (14, "pack"),
    "eggs": (7, "piece"), "lentils": (120, "kg"), "tea": (250, "kg"),
    "curd": (30, "pack"), "bread": (40, "loaf"), "ghee": (600, "kg"),
    "butter": (55, "pack"), "paneer": (90, "pack"),
    # A few stable packaged staples keep a fixed estimate. Items whose price
    # varies a lot (electronics, ice cream, chocolate) are intentionally NOT
    # here — they must be priced from the catalog or the LLM, never a guess.
    "namkeen": (50, "pack"), "soap": (35, "piece"),
    "toothpaste": (55, "piece"),
}

# higher = more essential (dropped last / never first)
ESSENTIALITY: dict[str, int] = {
    "milk": 10, "flour": 10, "rice": 10, "oil": 10, "salt": 10, "sugar": 9,
    "potato": 8, "onion": 8, "tomato": 7, "lentils": 8, "eggs": 7, "ghee": 6,
    "curd": 6, "bread": 6, "tea": 6, "green chilli": 5, "butter": 5, "paneer": 5,
    "maggi": 3, "biscuits": 2, "chips": 1,
    "soap": 5, "shampoo": 4, "toothpaste": 5, "juice": 3, "cola": 2,
    "namkeen": 2, "chocolate": 1, "ice cream": 1,
    "phone charger": 4, "earphones": 2, "bluetooth speaker": 1,
}

# canonical unit if the user gives none
DEFAULT_UNIT: dict[str, str] = {c: u for c, (_, u) in EST_PRICE.items()}


def essentiality(canonical: str) -> int:
    return ESSENTIALITY.get(canonical, 5)
