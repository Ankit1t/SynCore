"""Playwright-backed browser executor (integration boundary / Phase 2).

This is the real adapter that would drive a live, permitted site. It is
intentionally NOT implemented against any specific marketplace here: the safe,
legal, per-site page objects (search box, product card, cart, checkout) belong
to each marketplace's adapter and must respect that site's terms, robots and
rate limits.

Hard rules this executor must always follow when implemented:
  * Never bypass authentication, MFA, CAPTCHA or anti-bot controls.
  * Never scrape or log session cookies / secrets, and never expose them to an LLM.
  * Stop at a human-in-the-loop checkpoint whenever the site requires
    legitimate verification.
"""

from __future__ import annotations

from ..marketplace.base import BaseMarketplaceAdapter
from .executor import BrowserExecutor


class PlaywrightExecutor(BrowserExecutor):  # pragma: no cover - integration boundary
    def __init__(self, adapter: BaseMarketplaceAdapter):
        self._adapter = adapter
        raise NotImplementedError(
            "PlaywrightExecutor is the Phase-2 integration boundary. Implement per-site "
            "page objects inside the corresponding marketplace adapter, then wire them here. "
            "Use BROWSER_MODE=mock for the runnable vertical slice."
        )

    def start_session(self, user_id: str):  # noqa: D401
        raise NotImplementedError

    def search(self, query: str):
        raise NotImplementedError

    def add_to_cart(self, source_product_id: str, quantity: int):
        raise NotImplementedError

    def open_cart(self):
        raise NotImplementedError

    def open_checkout(self):
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
