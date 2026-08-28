"""
Shared pytest configuration for LibraryGenie off-Kodi tests.

This file installs the Kodi API stubs into ``sys.modules`` **before** any
``lib`` submodule is imported, adds the repository root to ``sys.path`` so
that ``import lib`` and ``import tests`` resolve, and provides fixtures that
give each test a clean, deterministic configuration slate.
"""

from __future__ import annotations

import os
import sys

import pytest

# --- path setup -----------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# --- install Kodi stubs before any lib import -----------------------------
from tests.kodimocks import install, reset_settings, seed_settings  # noqa: E402

install()

import lib.config.config_manager as _cm  # noqa: E402


@pytest.fixture
def fresh_config():
    """Reset the shared settings store and the config singleton.

    The addon caches configuration in two places:
      * ``lib.config.config_manager._CFG`` (the global ConfigManager)
      * the per-``ConfigManager`` ``_cache`` (rebuilt when ``_CFG`` is reset)
    Resetting both, plus clearing seeded settings, gives each test a clean
    slate.
    """
    reset_settings()
    _cm._CFG = None
    yield
    reset_settings()
    _cm._CFG = None


@pytest.fixture
def seed_config(fresh_config):
    """Yield a callable that seeds setting values *and* busts the cache.

    ``ConfigManager`` caches typed reads per key, so seeding the same key a
    second time within one test would otherwise keep returning the first
    value. This helper re-seeds and drops the singleton so the next read sees
    the freshly-seeded value. Use it for tests that exercise more than one
    value of the same setting::

        def test_foo(seed_config):
            seed_config(background_interval=1)
            assert SettingsManager().get_background_interval() == 5
            seed_config(background_interval=9999)
            assert SettingsManager().get_background_interval() == 720
    """

    def _set(**values):
        seed_settings(**values)
        _cm._CFG = None

    return _set
