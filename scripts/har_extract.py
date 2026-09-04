"""Extract REAL products (title, price, image, rating) from captured HAR JSON
and write them into SynCore's catalog_seed.json schema.

Filtering: a kept product must have a real image URL (this alone removes promo/
review noise) and a sane price and a non-promo title. Amazon's
/tez/browse/category JSON yields clean grocery products with images.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
from pathlib import Path
from typing import Any

SEED_PATH = Path(__file__).resolve().parents[1] / "src" / "syncore" / "master_agent" / "catalog_seed.json"

IMG_RE = re.compile(r"https://(?:m\.media-amazon\.com/images/I/|rukminim\d\.flixcart\.com/image/)[^\s\"'\\]+", re.I)
PRICE_KEYS = re.compile(r"(price|amount|mrp|sellingprice|finalprice)", re.I)
TITLE_KEYS = re.compile(r"(title|name|productname|label)", re.I)
RATING_KEYS = re.compile(r"(rating|stars|avgrating|averagerating)", re.I)
NOISE_RE = re.compile(
    r"^(buy|free|save|savings|add|flat|get|upto|up to|extra|shop|explore|see|view|more|"
    r"\d+%|terrific|simply|great|good|awesome|nice|value|core electronics)\b",
    re.I,
)
STOPWORDS = {"the", "and", "with", "durum", "wheat", "pack", "of", "premium", "fresh"}


def _response_text(entry: dict) -> str:
    content = entry.get("response", {}).get("content", {}) or {}
    text = content.get("text") or ""
    if content.get("encoding") == "base64":
        try:
            return base64.b64decode(text).decode("utf-8", "replace")
        except Exception:
            return ""
    return text


def _find_price(node: Any) -> float | None:
    best = None
    def walk(n: Any, hint: str = "") -> None:
        nonlocal best
        if best is not None:
            return
        if isinstance(n, dict):
            for k, v in n.items():
                walk(v, k)
        elif isinstance(n, list):
            for v in n:
                walk(v, hint)
        elif isinstance(n, (int, float)) and PRICE_KEYS.search(hint) and 5 < n < 500000:
            best = float(n)
        elif isinstance(n, str):
            m = re.search(r"\u20b9\s?([\d,]{2,})", n)
            if m:
                try:
                    v = float(m.group(1).replace(",", ""))
                    if 5 < v < 500000:
                        best = v
                except ValueError:
                    pass
    walk(node)
    return best


def _find_image(node: Any) -> str | None:
    def walk(n: Any) -> str | None:
        if isinstance(n, dict):
            for v in n.values():
                if (r := walk(v)):
                    return r
        elif isinstance(n, list):
            for v in n:
                if (r := walk(v)):
                    return r
        elif isinstance(n, str):
            m = IMG_RE.search(n)
            if m and "{@" not in m.group(0):
                return m.group(0)
        return None
    return walk(node)


def _find_rating(node: Any) -> float:
    found = 0.0
    def walk(n: Any, hint: str = "") -> None:
        nonlocal found
        if found:
            return
        if isinstance(n, dict):
            for k, v in n.items():
                walk(v, k)
        elif isinstance(n, list):
            for v in n:
                walk(v, hint)
        elif isinstance(n, (int, float)) and RATING_KEYS.search(hint) and 0 < n <= 5:
            found = round(float(n), 1)
    walk(node)
    return found


def _find_title(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    for k, v in node.items():
        if isinstance(v, str) and TITLE_KEYS.search(k) and 8 <= len(v.strip()) <= 120:
            return v.strip()
    return None


def _canonical(title: str) -> str:
    for w in re.findall(r"[A-Za-z]+", title.lower()):
        if len(w) > 3 and w not in STOPWORDS:
            return w
    return "product"


def extract(path: str, limit: int) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    out: dict[str, dict] = {}
    idx = 0
    for e in data.get("log", {}).get("entries", []):
        if "json" not in (e.get("response", {}).get("content", {}) or {}).get("mimeType", ""):
            continue
        text = _response_text(e)
        if "\u20b9" not in text and "price" not in text.lower():
            continue
        try:
            root = json.loads(text)
        except ValueError:
            continue
        stack = [root]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                title = _find_title(node)
                if title and not NOISE_RE.match(title) and title not in out:
                    img = _find_image(node)
                    price = _find_price(node)
                    if img and price:
                        idx += 1
                        out[title] = {
                            "offer_id": f"har-{idx}",
                            "canonical": _canonical(title),
                            "product_name": title[:120],
                            "brand": title.split()[0][:40],
                            "variant": [],
                            "size_text": "",
                            "unit": "pack",
                            "pack_size": 1,
                            "unit_price": round(price, 2),
                            "mrp": None,
                            "rating": _find_rating(node),
                            "review_count": 0,
                            "seller_rating": 0.0,
                            "eta_minutes": 0,
                            "in_stock": True,
                            "category": "grocery",
                            "image": img,
                        }
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
        if len(out) >= limit:
            break
    return list(out.values())[:limit]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("hars", nargs="+")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--out", default=str(SEED_PATH))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    products: list[dict] = []
    for h in args.hars:
        got = extract(h, args.limit)
        print(f"{Path(h).name}: {len(got)} products with images")
        products.extend(got)

    if args.dry_run:
        for p in products[:15]:
            print(f"  Rs.{p['unit_price']:<8} [{p['canonical']:12}] {p['product_name'][:55]}")
        return 0

    if args.merge and Path(args.out).exists():
        existing = json.loads(Path(args.out).read_text(encoding="utf-8"))
        products = (existing.get("products") or []) + products
    meta = {"source": "curated + real products captured from Amazon (HAR)", "currency": "INR"}
    Path(args.out).write_text(
        json.dumps({"_meta": meta, "products": products}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(products)} products to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
