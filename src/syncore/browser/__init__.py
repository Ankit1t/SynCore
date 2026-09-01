"""Browser execution layer.

High-level, verifiable browser actions (search, add_to_cart, verify_cart,
checkout) sit behind the BrowserExecutor interface. Raw selectors never leak
into business logic. The MockBrowserExecutor drives the mock marketplace so the
full execution path is testable; a Playwright executor is the real adapter and
the integration boundary.
"""
