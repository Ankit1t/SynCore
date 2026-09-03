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
    # --- expanded catalog coverage ---
    # fruits & vegetables
    "ginger": "ginger", "adrak": "ginger",
    "garlic": "garlic", "lehsun": "garlic", "lasun": "garlic",
    "cucumber": "cucumber", "kheera": "cucumber", "kakdi": "cucumber",
    "carrot": "carrot", "gajar": "carrot",
    "capsicum": "capsicum", "shimla mirch": "capsicum", "bell pepper": "capsicum",
    "lemon": "lemon", "nimbu": "lemon", "lime": "lemon",
    "coriander": "coriander", "dhaniya": "coriander", "cilantro": "coriander",
    "spinach": "spinach", "palak": "spinach",
    "banana": "banana", "kela": "banana",
    "apple": "apple", "apples": "apple", "seb": "apple",
    "orange": "orange", "oranges": "orange", "santra": "orange",
    "mango": "mango", "mangoes": "mango", "aam": "mango",
    "grapes": "grapes", "angoor": "grapes",
    "pomegranate": "pomegranate", "anaar": "pomegranate",
    # dairy extras
    "cheese": "cheese", "amul cheese": "cheese",
    "fresh cream": "cream", "cream": "cream",
    # staples & spices
    "besan": "besan", "gram flour": "besan",
    "poha": "poha", "suji": "suji", "rava": "suji", "semolina": "suji",
    "maida": "maida", "refined flour": "maida",
    "moong dal": "moong dal", "moong": "moong dal",
    "chana dal": "chana dal", "chickpeas": "chickpeas", "chole": "chickpeas", "kabuli chana": "chickpeas",
    "rajma": "rajma", "kidney beans": "rajma",
    "turmeric": "turmeric", "haldi": "turmeric",
    "red chilli powder": "red chilli powder", "lal mirch": "red chilli powder", "chilli powder": "red chilli powder",
    "garam masala": "garam masala",
    "cumin": "cumin", "jeera": "cumin",
    "coriander powder": "coriander powder", "dhaniya powder": "coriander powder",
    # snacks & packaged
    "kurkure": "kurkure", "popcorn": "popcorn", "rusk": "rusk",
    "pasta": "pasta", "macaroni": "pasta",
    "ketchup": "ketchup", "tomato sauce": "ketchup",
    "jam": "jam", "honey": "honey", "shahad": "honey",
    "peanut butter": "peanut butter", "cornflakes": "cornflakes", "corn flakes": "cornflakes",
    "oats": "oats",
    # beverages
    "coffee": "coffee", "green tea": "green tea",
    "energy drink": "energy drink", "red bull": "energy drink",
    "water bottle": "water", "mineral water": "water", "bisleri": "water",
    # personal care
    "toothbrush": "toothbrush", "handwash": "handwash", "hand wash": "handwash",
    "face wash": "face wash", "facewash": "face wash",
    "deodorant": "deodorant", "deo": "deodorant",
    "sanitary pad": "sanitary pad", "sanitary napkin": "sanitary pad", "sanitary pads": "sanitary pad",
    "razor": "razor", "conditioner": "conditioner", "hair oil": "hair oil",
    # household
    "detergent": "detergent", "washing powder": "detergent", "surf": "detergent",
    "dishwash": "dishwash", "dish wash": "dishwash",
    "floor cleaner": "floor cleaner", "toilet cleaner": "toilet cleaner", "harpic": "toilet cleaner",
    "tissue": "tissue", "tissue paper": "tissue",
    "garbage bags": "garbage bags", "dustbin bags": "garbage bags",
    "mosquito repellent": "mosquito repellent",
    # baby
    "diapers": "diapers", "diaper": "diapers", "pampers": "diapers",
    "baby wipes": "baby wipes", "wet wipes": "baby wipes",
    # electronics extras
    "power bank": "power bank", "powerbank": "power bank",
    "usb cable": "usb cable", "charging cable": "usb cable", "data cable": "usb cable",
    "mouse": "mouse", "wireless mouse": "mouse",
    "keyboard": "keyboard",
    "pendrive": "pendrive", "pen drive": "pendrive", "usb drive": "pendrive",
    "memory card": "memory card", "sd card": "memory card",
    "phone case": "phone case", "mobile cover": "phone case", "phone cover": "phone case", "back cover": "phone case",
    "smartwatch": "smartwatch", "smart watch": "smartwatch",
    "led bulb": "led bulb", "light bulb": "led bulb",
    "extension board": "extension board", "extension cord": "extension board",
    # stationery
    "notebook": "notebook", "register": "notebook",
    "a4 paper": "a4 paper", "printer paper": "a4 paper",
    "marker": "marker", "sketch pen": "marker",
    # frozen
    "frozen peas": "frozen peas", "french fries": "french fries", "fries": "french fries",
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
    # expanded: staples/produce high, treats/electronics low
    "besan": 8, "poha": 8, "suji": 8, "maida": 8, "moong dal": 9, "chana dal": 9,
    "rajma": 8, "chickpeas": 8, "turmeric": 8, "red chilli powder": 8, "cumin": 7,
    "garam masala": 6, "coriander powder": 7, "cheese": 6, "cream": 5, "honey": 5,
    "oats": 6, "cornflakes": 5, "peanut butter": 5, "jam": 4, "ketchup": 4, "pasta": 5,
    "ginger": 7, "garlic": 7, "carrot": 6, "capsicum": 6, "cucumber": 6, "lemon": 6,
    "coriander": 6, "spinach": 6, "banana": 6, "apple": 5, "orange": 5, "mango": 4,
    "grapes": 4, "pomegranate": 4, "coffee": 5, "green tea": 4, "water": 7,
    "energy drink": 1, "kurkure": 1, "popcorn": 1, "rusk": 3,
    "toothbrush": 6, "handwash": 6, "face wash": 4, "deodorant": 3, "sanitary pad": 8,
    "razor": 4, "conditioner": 3, "hair oil": 4,
    "detergent": 7, "dishwash": 6, "floor cleaner": 5, "toilet cleaner": 5, "tissue": 4,
    "garbage bags": 5, "mosquito repellent": 5, "diapers": 8, "baby wipes": 6,
    "power bank": 3, "usb cable": 3, "mouse": 2, "keyboard": 2, "pendrive": 2,
    "memory card": 2, "phone case": 2, "smartwatch": 1, "led bulb": 4, "extension board": 3,
    "notebook": 4, "a4 paper": 3, "marker": 2, "frozen peas": 5, "french fries": 2,
}

# canonical unit if the user gives none
DEFAULT_UNIT: dict[str, str] = {c: u for c, (_, u) in EST_PRICE.items()}


def essentiality(canonical: str) -> int:
    return ESSENTIALITY.get(canonical, 5)
