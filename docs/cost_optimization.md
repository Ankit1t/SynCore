# Cost Optimization

## Purpose

Keep the platform cheap to operate by not sending every action to an expensive
LLM.

## Principles (spec section 32)

- **Deterministic first**: intent parsing, unit math, budget, ranking signals,
  optimization, and payment logic are plain code — \$0 per call.
- **Model routing**: simple classification → small model; complex reasoning →
  larger model; arithmetic → never a model. Configure via `LLM_PROVIDER` /
  `LLM_MODEL`.
- **Offline default**: `DeterministicProvider` runs the whole platform with zero
  API cost, ideal for dev and CI.
- **Caching / reuse**: search results, product pages, short-lived availability,
  and agent state can be cached (Redis) with TTLs; embeddings keyed by
  `text_hash` avoid recompute.
- **Structured outputs + token budgets**: schema-validated responses, prompt
  compression, and `MAX_AGENT_STEPS` cap runaway spend.

## Cost tracker

`COST_TRACKER` aggregates tokens, latency and USD cost per process, surfaced at
`/api/v1/admin/metrics` (`llm_cost_usd_this_process`). Per-order cost is a
planned metric (`LLM_cost_per_order`).

## Real pricing

`llm/openai_provider.py` includes reference per-1K-token prices for cost
accounting; extend the table when adding models/providers.

## Result

For the default request the LLM cost is **\$0.0000** because every decision is
deterministic — the ideal outcome for a budget-conscious SaaS.
