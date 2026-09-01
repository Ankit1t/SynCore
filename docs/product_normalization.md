# Product Normalization

## Purpose

Make heterogeneous marketplace titles comparable by mapping them to canonical
names, units and quantities, and by computing a per-base-unit price.

## The problem

```
"Potato 1 kg" | "Fresh Potato - 1000g" | "Potatoes 1kg" | "Fresh Aloo 1 Kilogram"
```
All must normalize to `canonical_name="potato"`, `quantity=1kg`.

Diagram: [`mermaid/06_product_normalization.mmd`](mermaid/06_product_normalization.mmd).

## Components

- `normalization.lexicon`: canonical name ↔ synonyms (incl. Hindi/Hinglish:
  aloo→potato, mirch→green chilli, pyaaz→onion), known brands, count-based set.
- `normalization.normalizer`:
  - `canonicalize_name(title)` — longest-alias-wins matching.
  - `parse_quantity(text, count_based)` — regex for `kg/g/l/ml` and pack/count
    (`pack of 4`, `x2`, `2 pcs`).
  - `detect_brand(title)`.
  - `normalize_title(...) -> Product`.
- `units.conversion`: base units (kg, l, piece); `unit_price = price /
  quantity_in_base_units`; `packs_required` (ceil).

## Unit price examples

`₹60 / 1kg = ₹60/kg`; `₹35 / 500g = ₹70/kg` → the ₹60 offer is cheaper per unit,
which is what ranking and optimization compare on (not sticker price).

## Versioning & lineage

`normalization_version` is stamped on offers so results are reproducible and
debuggable when rules change.

## Failure modes

Unknown title → `NormalizationError` (caller can fall back to a provided
canonical). Missing quantity → count fallback or a sensible default in intent
(1 piece for count items, 1kg otherwise).

## Testing

`tests/unit/test_normalization.py` and `test_units.py` cover variants,
conversions, unit price ordering, and packs.
