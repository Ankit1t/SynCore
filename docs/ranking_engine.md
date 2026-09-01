# Ranking Engine

## Purpose

Rank candidate offers for each requested item with an explainable, configurable
score so users understand *why* an offer was chosen.

## Scoring model

```
score = semantic*0.30 + lexical*0.20 + quantity*0.15
      + category*0.15 + brand*0.10 + quality*0.10
```

Weights come from `RankingWeights` (env `RANK_*`) and are normalized to sum 1.

Diagram: [`mermaid/07_product_ranking.mmd`](mermaid/07_product_ranking.mmd).

## Signals

- **semantic**: cosine of embeddings of the query vs the title. The default
  `DeterministicProvider` uses a token-hash bag-of-words vector (offline, free);
  swap in real embeddings via `EmbeddingProvider`.
- **lexical**: query/title token overlap.
- **quantity**: closeness after unit conversion; overshoot is penalized;
  incompatible measures (e.g. a weight-based "Maggi seasoning" for a count
  request) score low.
- **category**: canonical/category alignment.
- **brand**: match against `brand_preference` (neutral when none).
- **quality**: rating + review-count confidence + seller reliability.

## Explainability

Each `RankedOffer` carries `score_breakdown` and human-readable `reasons`
("unit price ~₹38/kg", "quantity matches request exactly", "rating 4.5 (21000
reviews)"). We expose concise decision reasons, never hidden chain-of-thought
(spec section 57).

## Example

For query "maggi", 2 pieces: the 70g noodles pack ranks above "Maggi Masala
Magic Seasoning 100g" because the seasoning's weight unit is incompatible with a
count request and its semantic/quantity signals are weaker.

## Failure modes

Empty candidate list → empty ranking (optimizer marks the item missing). A
provider embedding error falls back to lexical/quantity signals.

## Testing

`tests/unit/test_ranking.py` verifies matching-quantity preference, noodles vs
seasoning ordering, and the presence of the score breakdown.
