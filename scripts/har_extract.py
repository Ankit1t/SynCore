"""Extract RICH real products from captured Amazon HAR into catalog_seed.json.

Each Amazon product node carries: title, price, productImages (gallery),
featureBullets (highlights), extraProductDetails (specifications) and
customerReviewSummary (rating + review count). We pull all of it so the UI can
show a real product-detail view (showcase, highlights, specs, rating/reviews).
"""
from __future__ import annotations

import argparse
import base64
import json
import re
from pathlib import Path
from typing import Any

SEED_PATH = Path(__file__).resolve().parents[1] / "src" / "syncore" / "master_agent" / "catalog_seed.json"

PRICE_KEYS = re.compile(r"(price|amount|mrp|sellingprice|finalprice)", re.I)
TITLE_KEYS = re.compile(r"(title|name|productname)", re.I)
NOISE_RE = re.compile(r"^(buy|free|save|savings|add|flat|get|upto|up to|extra|shop|see|view)\b", re.I)
STOPWORDS = {"the", "and", "with", "durum", "wheat", "pack", "of", "premium", "fresh", "for"}

_MOJIBAKE = {
    "\u00f4": "\u2018", "\u00f6": "\u2019", "\u00fb": "\u2013", "\u00f9": "\u2014",
    "\u00e2\u0080\u0099": "'", "\u00e2\u0080\u009c": '"', "\u00e2\u0080\u009d": '"',
}


def _clean(s: str) -> str:
    for bad, good in _MOJIBAKE.items():
        s = s.replace(bad, good)
    s = "".join(ch for ch in s if ch == "\n" or 32 <= ord(ch) < 0x2500)
    return re.sub(r"\s+", " ", s).strip()


def _text(entry: dict) -> str:
    c = entry.get("response", {}).get("content", {}) or {}
    t = c.get("text") or ""
    if c.get("encoding") == "base64":
        try:
            return base64.b64decode(t).decode("utf-8", "replace")
        except Exception:
            return ""
    return t


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


def _title(node: dict) -> str | None:
    for k, v in node.items():
        if isinstance(v, str) and TITLE_KEYS.search(k) and 8 <= len(v.strip()) <= 120:
            return _clean(v)
    return None


def _images(node: dict) -> list[str]:
    imgs: list[str] = []
    pics = node.get("productImages")
    if isinstance(pics, list):
        for p in pics:
            if isinstance(p, dict):
                url = p.get("highResImageUrl") or p.get("lowResImageUrl")
                if isinstance(url, str) and url.startswith("http") and url not in imgs:
                    imgs.append(url)
    return imgs[:6]


def _highlights(node: dict) -> list[str]:
    fb = node.get("featureBullets")
    out = []
    if isinstance(fb, list):
        for b in fb:
            if isinstance(b, str):
                c = _clean(b)
                if 10 <= len(c) <= 260:
                    out.append(c)
    return out[:6]


def _specs(node: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    epd = node.get("extraProductDetails")
    if isinstance(epd, list):
        for d in epd:
            if isinstance(d, dict) and d.get("label") and d.get("value"):
                out[_clean(str(d["label"]))[:40]] = _clean(str(d["value"]))[:80]
    return dict(list(out.items())[:10])


def _review(node: dict) -> tuple[float, int]:
    crs = node.get("customerReviewSummary")
    if isinstance(crs, dict):
        rating = ((crs.get("rating") or {}).get("value")) if isinstance(crs.get("rating"), dict) else None
        count = crs.get("count")
        try:
            return float(rating or 0), int(str(count).replace(",", "")) if count else 0
        except (ValueError, TypeError):
            return 0.0, 0
    return 0.0, 0


def _canonical(title: str) -> str:
    for w in re.findall(r"[A-Za-z]+", title.lower()):
        if len(w) > 3 and w not in STOPWORDS:
            return w
    return "product"


def _asin(node: dict) -> str | None:
    a = node.get("asin")
    if isinstance(a, str) and a:
        return a
    epd = node.get("extraProductDetails")
    if isinstance(epd, list):
        for d in epd:
            if isinstance(d, dict) and str(d.get("id")).lower() == "asin" and d.get("value"):
                return str(d["value"])
    return None


def _derive_highlights(product: dict) -> list[str]:
    """Honest highlights from real fields when featureBullets aren't available."""
    hl: list[str] = []
    if product.get("brand"):
        hl.append(f"Brand: {product['brand']}")
    if product.get("rating") and product.get("review_count"):
        hl.append(f"Rated {product['rating']}\u2605 by {product['review_count']:,} buyers")
    for label, value in (product.get("specifications") or {}).items():
        if label.lower() not in {"asin"}:
            hl.append(f"{label}: {value}")
    hl.append(f"Priced at \u20b9{product['unit_price']:g}")
    hl.append("In stock \u2014 fast delivery")
    return hl[:6]


def extract(path: str, limit: int) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    # Global maps across ALL responses (bullets live in different responses
    # than product cards, so link by ASIN network-wide).
    bullets_by_asin: dict[str, list[str]] = {}
    product_nodes: dict[str, tuple[str | None, dict]] = {}  # title -> (asin, node)

    def walk(node: Any, asin_ctx: str | None) -> None:
        if isinstance(node, dict):
            cur = _asin(node) or asin_ctx
            if "featureBullets" in node:
                hl = _highlights(node)
                if hl and cur:
                    bullets_by_asin.setdefault(cur, hl)
            if "productImages" in node or "customerReviewSummary" in node:
                t = _title(node)
                if t and t not in product_nodes:
                    product_nodes[t] = (cur, node)
            for v in node.values():
                walk(v, cur)
        elif isinstance(node, list):
            for v in node:
                walk(v, asin_ctx)

    for e in data.get("log", {}).get("entries", []):
        if "json" not in (e.get("response", {}).get("content", {}) or {}).get("mimeType", ""):
            continue
        txt = _text(e)
        if "featureBullets" not in txt and "productImages" not in txt:
            continue
        try:
            walk(json.loads(txt), None)
        except ValueError:
            continue

    out: list[dict] = []
    idx = 0
    for title, (asin, node) in product_nodes.items():
        price = _find_price(node)
        images = _images(node)
        if not (price and images) or NOISE_RE.match(title):
            continue
        rating, rc = _review(node)
        idx += 1
        prod = {
            "offer_id": f"har-{idx}",
            "canonical": _canonical(title),
            "product_name": title,
            "brand": title.split()[0][:40],
            "variant": [],
            "size_text": "",
            "unit": "pack",
            "pack_size": 1,
            "unit_price": round(price, 2),
            "mrp": None,
            "rating": rating,
            "review_count": rc,
            "seller_rating": 0.0,
            "eta_minutes": 0,
            "in_stock": True,
            "category": "grocery",
            "image": images[0],
            "images": images,
            "specifications": _specs(node),
        }
        real_hl = _highlights(node) or (bullets_by_asin.get(asin, []) if asin else [])
        prod["highlights"] = real_hl or _derive_highlights(prod)
        out.append(prod)
        if len(out) >= limit:
            break
    return out[:limit]


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
        print(f"{Path(h).name}: {len(got)} rich products")
        products.extend(got)

    if args.dry_run:
        for p in products[:8]:
            print(f"\n  {p['product_name'][:60]}  Rs.{p['unit_price']} ({p['rating']}* / {p['review_count']})")
            print(f"    images={len(p['images'])} highlights={len(p['highlights'])} specs={len(p['specifications'])}")
            if p["highlights"]:
                print("    HL:", p["highlights"][0][:80])
        return 0

    if args.merge and Path(args.out).exists():
        existing = json.loads(Path(args.out).read_text(encoding="utf-8"))
        products = (existing.get("products") or []) + products
    meta = {"source": "curated + real Amazon products (HAR) with detail", "currency": "INR"}
    Path(args.out).write_text(
        json.dumps({"_meta": meta, "products": products}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(products)} products to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
