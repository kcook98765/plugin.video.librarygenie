"""Tests for lib.data.db_config (optimization params + PRAGMA application).

``DatabaseConfigCalculator`` depends only on the stdlib (os, sqlite3) and the
Kodi logger (stubbed), so it is fully testable off-Kodi. Uses real SQLite
connections / temp files.
"""

import sqlite3

import pytest

from lib.data.db_config import DatabaseConfigCalculator

_MB = 1024 * 1024


def _make_db(path, mb):
    with open(path, "wb") as fh:
        fh.truncate(int(mb * _MB))


def test_new_db_uses_defaults(tmp_path):
    calc = DatabaseConfigCalculator()
    config = calc.calculate_optimization_params(str(tmp_path / "does_not_exist.db"))
    assert config["db_size_mb"] == 0
    assert config["mmap_size"] == 33554432
    assert config["cache_pages"] == 500


def test_small_db_uses_defaults(tmp_path):
    db = tmp_path / "small.db"
    _make_db(str(db), 4)  # 4 MB < 16 MB threshold
    config = DatabaseConfigCalculator().calculate_optimization_params(str(db))
    assert config["db_size_mb"] == 4
    assert config["mmap_size"] == 33554432  # 32MB minimum
    assert config["cache_pages"] == 500


def test_medium_db_scales(tmp_path):
    db = tmp_path / "medium.db"
    _make_db(str(db), 32)  # 16 <= 32 MB < 64 MB
    config = DatabaseConfigCalculator().calculate_optimization_params(str(db))
    assert config["mmap_size"] == int(32 * _MB * 2)  # 2x size
    assert config["cache_pages"] == 1500  # min(1500, 32*75)


def test_large_db_caps_mmap(tmp_path):
    db = tmp_path / "large.db"
    _make_db(str(db), 200)  # > 64 MB
    config = DatabaseConfigCalculator().calculate_optimization_params(str(db))
    assert config["cache_pages"] == 2000
    # mmap capped at 128MB (1.5x would exceed the cap).
    assert config["mmap_size"] == 134217728


def test_apply_pragma_settings_on_real_connection(tmp_path):
    calc = DatabaseConfigCalculator()
    conn = sqlite3.connect(str(tmp_path / "pragma.db"))
    config = calc.calculate_optimization_params(str(tmp_path / "pragma.db"))
    calc.apply_pragma_settings(conn, config, busy_timeout_ms=5000)

    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    assert conn.execute("PRAGMA cache_size").fetchone()[0] == config["cache_pages"]
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.row_factory is sqlite3.Row
    conn.close()


def test_apply_pragma_settings_raises_on_closed_connection(tmp_path):
    calc = DatabaseConfigCalculator()
    config = calc.calculate_optimization_params(str(tmp_path / "x.db"))
    conn = sqlite3.connect(":memory:")
    conn.close()
    with pytest.raises(Exception):
        calc.apply_pragma_settings(conn, config, busy_timeout_ms=1000)


def test_validate_schema_version_match():
    calc = DatabaseConfigCalculator()
    from lib.data.migrations import TARGET_SCHEMA_VERSION

    metadata = {
        "schema_version": TARGET_SCHEMA_VERSION,
        "target_schema_version": TARGET_SCHEMA_VERSION,
    }
    assert calc.validate_schema_version(metadata) is True


def test_validate_schema_version_mismatch():
    calc = DatabaseConfigCalculator()
    assert calc.validate_schema_version({"schema_version": 1, "target_schema_version": 1}) is False
    assert calc.validate_schema_version({}) is False


def test_get_current_schema_version_from_db(tmp_path):
    calc = DatabaseConfigCalculator()
    conn = sqlite3.connect(str(tmp_path / "ver.db"))
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE schema_version (id INTEGER PRIMARY KEY, version INTEGER)")
    conn.execute("INSERT INTO schema_version (id, version) VALUES (1, 7)")
    conn.commit()
    assert calc.get_current_schema_version(conn) == 7
    conn.close()


def test_get_current_schema_version_empty_returns_zero(tmp_path):
    calc = DatabaseConfigCalculator()
    conn = sqlite3.connect(str(tmp_path / "empty.db"))
    assert calc.get_current_schema_version(conn) == 0
    conn.close()
