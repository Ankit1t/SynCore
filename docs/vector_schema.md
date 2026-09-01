# Vector Schema (semantic search)

## Purpose

Support semantic product matching without making vector search the source of
truth. Canonical product data stays relational.

## MVP state

The default `DeterministicProvider.embed` produces a 64-dim token-hash vector so
semantic-style ranking works offline and free. This is deliberately swappable
for a real embedding model + vector store.

## Planned schema

Backing options: PostgreSQL + `pgvector`, or Qdrant. Logical record:

| Field | Type | Notes |
|---|---|---|
| `product_id` | uuid | FK to canonical `products` |
| `embedding` | vector(N) | model-specific dimensionality |
| `model_version` | text | which embedding model produced it |
| `text_hash` | text | hash of the embedded text (dedupe / staleness) |
| `created_at` | timestamptz | |

## Rules

- Vector search **augments** lexical/quantity/brand signals in the ranking
  engine; it is never the sole decider.
- `model_version` + `text_hash` make embeddings reproducible and invalidatable.
- Canonical price/quantity/availability remain in the relational store.

## Integration point

Implement an `EmbeddingProvider` (mirroring `LLMProvider.embed`) and a vector
repository; the `RankingEngine` already consumes `provider.embed(...)`, so only
the provider + store change.
