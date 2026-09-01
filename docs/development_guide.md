# Development Guide

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```
(macOS/Linux: `python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`)

## Everyday commands

| Task | Command |
|---|---|
| Run the CLI slice | `python -m syncore.scripts.vertical_slice ["your request"]` |
| Run the API | `uvicorn syncore.api.app:app --reload` |
| Migrate / seed | `python -m syncore.scripts.manage migrate` / `seed` |
| Tests | `pytest -p no:warnings` |
| Lint / format | `ruff check src tests` / `ruff format src tests` |
| Frontend | `cd web && npm install && npm run dev` |

`make <target>` wraps these where `make` is available.

## Project layout

See [system_design](system_design.md) for the module map. Rule of thumb: put new
business logic in a deterministic service package with its own tests; expose it
through the orchestrator, not by cross-calling services.

## Adding things

- **Marketplace**: implement `BaseMarketplaceAdapter`, register it, add contract
  tests. See [scraping_adapters](scraping_adapters.md).
- **Grocery term / synonym**: extend `normalization/lexicon.py`.
- **LLM/payment/browser vendor**: implement the provider interface; select via
  env.
- **Optimization objective**: extend `OptimizationObjective` + comparators in
  `optimizer/basket.py`.

## Conventions

- Python 3.11+, full type hints, small pure functions, typed domain errors.
- Ruff for lint/format (`line-length = 100`).
- Never put critical financial/business rules only inside prompts — they live in
  deterministic code (spec section 64, 72).
- Don't leak secrets or stack traces to clients.

## Configuration

Everything is env-driven via `syncore.config.Settings` (`.env` supported). Import
`get_settings()`; never read `os.environ` directly elsewhere.
