"""Tests for lib.utils.cache (SimpleCache TTL logic, pure Python)."""

import time

from lib.utils.cache import SimpleCache


def test_set_get_round_trip():
    cache = SimpleCache()
    cache.set("k", {"a": 1}, ttl_seconds=60)
    assert cache.get("k") == {"a": 1}


def test_missing_key_returns_none():
    cache = SimpleCache()
    assert cache.get("nope") is None


def test_expired_key_returns_none_and_evicts():
    cache = SimpleCache()
    cache.set("k", "v", ttl_seconds=0)
    time.sleep(0.01)
    assert cache.get("k") is None
    # Expired entry should be removed from the internal store.
    assert "k" not in cache._cache


def test_clear_specific_key():
    cache = SimpleCache()
    cache.set("a", 1, ttl_seconds=60)
    cache.set("b", 2, ttl_seconds=60)
    cache.clear("a")
    assert cache.get("a") is None
    assert cache.get("b") == 2


def test_clear_all():
    cache = SimpleCache()
    cache.set("a", 1, ttl_seconds=60)
    cache.set("b", 2, ttl_seconds=60)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None
