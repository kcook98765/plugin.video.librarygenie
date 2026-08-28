"""Regression tests for ``ConfigManager._get_setting_type`` (Issue 2).

These settings are declared ``type="integer"`` in ``resources/settings.xml``
but were missing from the integer classification list, so their *write* path
(``ConfigManager.set``) routed them through the wrong Kodi setter. The
regression asserts pin the corrected classification and verify the value is
persisted as an integer.

``_get_setting_type`` is the single mechanism the write path consults, so
asserting its return value is a precise before/after discriminator:

* before the fix these keys returned ``"string"`` (or, for
  ``library_sync_interval``, ``"bool"`` - it was mis-filed in ``bool_settings``)
* after the fix they return ``"int"``
"""

from lib.config.config_manager import ConfigManager


# The five settings that resources/settings.xml declares type="integer".
EXPECTED_INT_SETTINGS = [
    "ai_search_result_limit",
    "default_content_type",
    "default_fields",
    "default_match_mode",
    "library_sync_interval",
]


def _cm():
    return ConfigManager()


def test_all_five_settings_classify_as_int():
    cm = _cm()
    for key in EXPECTED_INT_SETTINGS:
        assert cm._get_setting_type(key) == "int", (
            f"{key} must classify as int"
        )


def test_library_sync_interval_no_longer_bool():
    """Regression: library_sync_interval was mis-filed in bool_settings."""
    cm = _cm()
    assert cm._get_setting_type("library_sync_interval") == "int"
    assert cm._get_setting_type("library_sync_interval") != "bool"


def test_set_persists_integer_values(fresh_config):
    """set() must route these settings through the int path.

    Before the fix, set() used setSettingString (4 keys) / setSettingBool
    (library_sync_interval) and stored a str/bool. After the fix the shared
    store holds a real int.
    """
    from tests.kodimocks import get_seed

    values = {
        "ai_search_result_limit": 20,
        "default_content_type": 0,
        "default_fields": 2,
        "default_match_mode": 1,
        "library_sync_interval": 2,
    }
    for key, value in values.items():
        instance = ConfigManager()
        result = instance.set(key, value)
        assert result is True, f"set({key}) should report success"
        stored = get_seed()[key]
        assert isinstance(stored, int), (
            f"{key} must be stored as int, got {type(stored).__name__}={stored!r}"
        )
        assert stored == value


def test_genuinely_bool_settings_unchanged():
    """Guard: real boolean settings still classify as bool (no over-broad fix)."""
    cm = _cm()
    assert cm._get_setting_type("sync_movies") == "bool"
    assert cm._get_setting_type("quick_add_enabled") == "bool"
    assert cm._get_setting_type("ai_search_activated") == "bool"


def test_genuinely_int_settings_unchanged():
    """Guard: previously-correct int settings still classify as int."""
    cm = _cm()
    assert cm._get_setting_type("search_page_size") == "int"
    assert cm._get_setting_type("jsonrpc_page_size") == "int"


def test_genuinely_string_settings_unchanged():
    """Guard: real string settings still classify as string."""
    cm = _cm()
    assert cm._get_setting_type("default_list_id") == "string"
    assert cm._get_setting_type("remote_server_url") == "string"
