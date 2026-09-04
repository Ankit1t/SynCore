#!/usr/bin/env python
"""Convert a Kaggle (or any) products CSV into SynCore's catalog_seed.json.

This lets you make the catalog "heavy" with a real dataset. The agent matches
items by product NAME tokens too (see agent._build_line), so a coarse
`canonical`/category is fine — realistic titles + prices are what matter.

Usage (PowerShell):
  .\.venv\Scripts\python.exe scripts/ingest_kaggle_catalog.py `
      --csv path\to\dataset.csv `
      --name-col product_name --price-col discounted_price `
      --mrp-col actual_price --rating-col rating --reviews-col rating_count `
      --category-col category --brand-col brand `
      --limit 1500 --merge

Notes:
- --merge keeps the existing curated catalog and appends the dataset.
- Prices/MRP are cleaned of Rs., commas, currency symbols.
- Rows without a name or a positive price are skipped.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

SEED_PATH = Path(__file__).resolve().parents[1] / "src" / "syncore" / "master_agent" / "catalog_seed.json"

_NUM_RE = re.compile(r"[-+]?\d*\.?\d+")


def _num(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = str(value).replace(",", "").replace("\u20b9", "").strip()
    m = _NUM_RE.search(cleaned)
    return float(m.group()) if m else None


def _slug(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip().lower())[:40] or "product"


def _canonical_from(category: str | None, name: str) -> str:
    if category:
        # last segment of a "A|B|C" or "A > B" category path, lowercased
        seg = re.split(r"[|>/,]", category)[-1].strip()
        if seg:
            return _slug(seg)
    return _slug(name.split()[0] if name.split() else name)


def convert(args: argparse.Namespace) -> list[dict]:
    rows: list[dict] = []
    with open(args.csv, encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader):
            if args.limit and len(rows) >= args.limit:
                break
            name = (row.get(args.name_col) or "").strip()
            price = _num(row.get(args.price_col)) if args.price_col else None
            if not name or not price or price <= 0:
                continue
            mrp = _num(row.get(args.mrp_col)) if args.mrp_col else None
            rating = _num(row.get(args.rating_col)) if args.rating_col else None
            reviews = _num(row.get(args.reviews_col)) if args.reviews_col else None
            category = (row.get(args.category_col) or "").strip() if args.category_col else ""
            brand = (row.get(args.brand_col) or "").strip() if args.brand_col else ""

            rows.append({
                "offer_id": f"kaggle-{i}",
                "canonical": _canonical_from(category, name),
                "product_name": name[:120],
                "brand": brand[:40],
                "variant": [],
                "size_text": "",
                "unit": "piece",
                "pack_size": 1,
                "unit_price": round(price, 2),
                "mrp": round(mrp, 2) if mrp and mrp >= price else None,
                "rating": round(rating, 2) if rating and rating <= 5 else 0.0,
                "review_count": int(reviews) if reviews else 0,
                "seller_rating": 0.0,
                "eta_minutes": 0,
                "in_stock": True,
                "category": _slug(category) if category else "general",
            })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Kaggle CSV -> catalog_seed.json")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--name-col", required=True)
    ap.add_argument("--price-col", required=True)
    ap.add_argument("--mrp-col")
    ap.add_argument("--rating-col")
    ap.add_argument("--reviews-col")
    ap.add_argument("--category-col")
    ap.add_argument("--brand-col")
    ap.add_argument("--limit", type=int, default=1500)
    ap.add_argument("--merge", action="store_true", help="append to the existing curated catalog")
    ap.add_argument("--out", default=str(SEED_PATH))
    args = ap.parse_args()

    products = convert(args)
    if not products:
        print("No valid rows found — check your --*-col names.", file=sys.stderr)
        return 1

    meta = {
        "source": f"imported from {Path(args.csv).name} (+ curated)" if args.merge else f"imported from {Path(args.csv).name}",
        "currency": "INR",
        "note": "Representative dataset for the demo; pluggable with a live ONDC/retail feed.",
    }

    if args.merge and Path(args.out).exists():
        existing = json.loads(Path(args.out).read_text(encoding="utf-8"))
        products = (existing.get("products") or []) + products

    Path(args.out).write_text(
        json.dumps({"_meta": meta, "products": products}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(products)} products to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
