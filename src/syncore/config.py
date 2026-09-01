"""Environment-driven configuration for Syncore.

All tunables live here so subsystems never read os.environ directly. Settings
are validated by pydantic-settings and can be overridden via environment
variables or a local .env file (see .env.example).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RankingWeights(BaseSettings):
    """Explainable ranking weights. Must be configurable per the spec."""

    model_config = SettingsConfigDict(env_prefix="RANK_")

    semantic: float = 0.30
    lexical: float = 0.20
    quantity: float = 0.15
    category: float = 0.15
    brand: float = 0.10
    quality: float = 0.10

    def normalized(self) -> "RankingWeights":
        total = self.semantic + self.lexical + self.quantity + self.category + self.brand + self.quality
        if total <= 0:
            return self
        return RankingWeights(
            semantic=self.semantic / total,
            lexical=self.lexical / total,
            quantity=self.quantity / total,
            category=self.category / total,
            brand=self.brand / total,
            quality=self.quality / total,
        )


class Settings(BaseSettings):
    """Top-level application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- General ---
    app_name: str = "Syncore"
    environment: Literal["local", "staging", "production"] = "local"
    log_level: str = "INFO"
    log_json: bool = False

    # --- Persistence ---
    # SQLite by default for zero-setup local runs. Set DATABASE_URL to a
    # postgresql+psycopg://... URL to use Postgres (see docker-compose.yml).
    database_url: str = Field(default="sqlite:///./syncore.db")

    # --- Cache / events (optional; in-memory fallback if unset) ---
    redis_url: str | None = None

    # --- LLM ---
    # "deterministic" uses the built-in rule-based provider (no API key needed).
    llm_provider: Literal["deterministic", "openai"] = "deterministic"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str | None = None
    max_agent_steps: int = 50
    max_agent_runtime_seconds: int = 120

    # --- Marketplace ---
    marketplace_mode: Literal["mock", "live"] = "mock"
    default_marketplace: str = "mock-bazaar"

    # --- Browser ---
    browser_mode: Literal["mock", "playwright"] = "mock"

    # --- Money / budget defaults ---
    default_currency: str = "INR"
    default_budget: float = 500.0

    # --- Payments ---
    payment_provider: Literal["mock", "stripe", "razorpay"] = "mock"
    # Phase 2 credential-gated integrations (empty = provider ACCESS_RESTRICTED).
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    webhook_secret: str = "dev-webhook-secret-change-me"
    # Transactions at or below this amount for trusted vendors may auto-execute.
    payment_auto_limit: float = 500.0
    payment_daily_limit: float = 5000.0

    # --- Optimizer ---
    default_objective: Literal["CHEAPEST", "BEST_VALUE", "FASTEST", "BEST_QUALITY", "BALANCED"] = (
        "BEST_VALUE"
    )
    default_min_rating: float = 3.5

    # --- Scraping robustness ---
    scraper_max_retries: int = 3
    scraper_timeout_seconds: float = 15.0
    scraper_rate_limit_per_min: int = 60

    # --- Feature flags (risky features default OFF) ---
    feature_automatic_payment: bool = True  # allowed only within policy limits
    feature_browser_execution: bool = True
    feature_multi_marketplace: bool = True
    feature_auto_substitution: bool = False

    ranking_weights: RankingWeights = Field(default_factory=RankingWeights)


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Import this everywhere instead of reading env."""
    return Settings()
