"""Pytest configuration and shared fixtures.

Uses a throwaway SQLite database so tests never touch a developer's dev DB.
DATABASE_URL is set before any syncore import triggers engine creation.
"""

from __future__ import annotations

import os
import tempfile

_tmp_db = os.path.join(tempfile.gettempdir(), "syncore_test.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp_db}")
os.environ.setdefault("KIRANA_ENV", "local")

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _init_db():
    from syncore.db.base import init_db

    if os.path.exists(_tmp_db):
        try:
            os.remove(_tmp_db)
        except OSError:
            pass
    init_db()
    yield


@pytest.fixture
def registry():
    from syncore.marketplace.mock import build_default_registry
    from syncore.marketplace.registry import get_registry

    reg = get_registry()
    if not reg.list():
        for adapter in build_default_registry():
            reg.register(adapter)
    return reg
