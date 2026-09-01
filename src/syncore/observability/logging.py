"""Structured logging.

Emits either human-friendly lines (local dev) or single-line JSON (production),
controlled by Settings.log_json. A per-request/agent-run correlation id can be
bound so every log line is traceable to an agent execution.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def set_correlation_id(value: str | None) -> None:
    _correlation_id.set(value)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        cid = get_correlation_id()
        if cid:
            payload["correlation_id"] = cid
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Attach structured extras placed on the record via `extra=`.
        for key, value in getattr(record, "__dict__", {}).items():
            if key.startswith("syncore_"):
                payload[key[len("syncore_") :]] = value
        return json.dumps(payload, default=str)


class HumanFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        cid = get_correlation_id()
        prefix = f"[{cid[:8]}] " if cid else ""
        base = f"{self.formatTime(record, '%H:%M:%S')} {record.levelname:<7} {record.name}: {prefix}{record.getMessage()}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


_configured = False


def configure_logging(level: str = "INFO", json_output: bool = False) -> None:
    global _configured
    if _configured:
        return
    # Ensure non-ASCII (e.g. the ₹ symbol) prints cleanly on Windows consoles.
    # Two things are needed on Windows: (1) write UTF-8 bytes, and (2) tell the
    # console to interpret them as UTF-8 (code page 65001). Without (2) the ₹
    # glyph shows up as mojibake like "Γé╣".
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)  # type: ignore[attr-defined]
            ctypes.windll.kernel32.SetConsoleCP(65001)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - best effort, never fatal
            pass
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_output else HumanFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
