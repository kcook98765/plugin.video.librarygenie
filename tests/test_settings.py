"""Tests for lib.config.settings (typed settings + clamping logic).

These exercise the real ``SettingsManager`` / ``ConfigManager`` code against
the seeded Kodi stub settings store. The ``seed_config`` fixture (conftest)
seeds values *and* busts the ``ConfigManager`` cache, so each read sees the
value just seeded.

Only settings whose typed reads are exercised are tested here. Settings are
seeded through the shared ``xbmcaddon`` settings store, which the real
``ConfigManager`` reads via its typed getters.
"""

from lib.config.settings import SettingsManager


def test_get_search_page_size_default(seed_config):
    # No seed -> get_int falls back to default 200 (clamped to [50, 500]).
    assert SettingsManager().get_search_page_size() == 200


def test_get_background_interval_clamped_min(seed_config):
    seed_config(background_interval=1)
    assert SettingsManager().get_background_interval() == 5  # clamped to min 5


def test_get_background_interval_clamped_max(seed_config):
    seed_config(background_interval=9999)
    assert SettingsManager().get_background_interval() == 720  # clamped to max 720


def test_get_background_interval_in_range(seed_config):
    seed_config(background_interval=30)
    assert SettingsManager().get_background_interval() == 30


def test_get_favorites_scan_interval_clamped(seed_config):
    seed_config(favorites_scan_interval=1)
    assert SettingsManager().get_favorites_scan_interval() == 5  # min
    seed_config(favorites_scan_interval=9999)
    assert SettingsManager().get_favorites_scan_interval() == 1440  # max


def test_get_library_sync_interval_mapping(seed_config):
    seed_config(library_sync_interval=0)
    assert SettingsManager().get_library_sync_interval() == 0  # disabled
    seed_config(library_sync_interval=1)
    assert SettingsManager().get_library_sync_interval() == 5  # 5 min
    seed_config(library_sync_interval=2)
    assert SettingsManager().get_library_sync_interval() == 60  # hourly
    seed_config(library_sync_interval=3)
    assert SettingsManager().get_library_sync_interval() == 1440  # daily


def test_get_ai_search_sync_interval_mapping(seed_config):
    seed_config(ai_search_sync_interval=0)
    assert SettingsManager().get_ai_search_sync_interval() == 3600  # 1 hour
    seed_config(ai_search_sync_interval=1)
    assert SettingsManager().get_ai_search_sync_interval() == 43200  # 12 hours
    seed_config(ai_search_sync_interval=2)
    assert SettingsManager().get_ai_search_sync_interval() == 86400  # 24 hours


def test_get_default_list_id_empty_becomes_none(seed_config):
    assert SettingsManager().get_default_list_id() is None


def test_get_default_list_id_seeded(seed_config):
    seed_config(default_list_id="42")
    assert SettingsManager().get_default_list_id() == "42"


def test_get_remote_server_url_strip(seed_config):
    seed_config(remote_server_url="  https://example.com:5020  ")
    assert SettingsManager().get_remote_server_url() == "https://example.com:5020"


def test_get_remote_server_url_none_when_blank(seed_config):
    assert SettingsManager().get_remote_server_url() is None


def test_get_ai_search_api_key_strip(seed_config):
    seed_config(ai_search_api_key="  abc123  ")
    assert SettingsManager().get_ai_search_api_key() == "abc123"


def test_get_ai_search_api_key_none_when_blank(seed_config):
    assert SettingsManager().get_ai_search_api_key() is None


def test_get_backup_storage_location_default(seed_config):
    assert (
        SettingsManager().get_backup_storage_location()
        == "special://userdata/addon_data/plugin.video.librarygenie/backups/"
    )


def test_get_backup_storage_location_custom(seed_config):
    seed_config(backup_storage_location="/mnt/backups/")
    assert SettingsManager().get_backup_storage_location() == "/mnt/backups/"


def test_get_backup_retention_count_clamped(seed_config):
    seed_config(backup_retention_count=0)
    assert SettingsManager().get_backup_retention_count() == 1  # min 1
    seed_config(backup_retention_count=999)
    assert SettingsManager().get_backup_retention_count() == 50  # max 50


def test_get_folder_cache_fresh_ttl_seeded(seed_config):
    seed_config(folder_cache_fresh_ttl=24)
    assert SettingsManager().get_folder_cache_fresh_ttl() == 24


def test_get_search_page_size_clamped(seed_config):
    # ``search_page_size`` is an integer control (clamped to [50, 500]).
    seed_config(search_page_size=30)
    assert SettingsManager().get_search_page_size() == 50  # min
    seed_config(search_page_size=120)
    assert SettingsManager().get_search_page_size() == 120  # in range
    seed_config(search_page_size=999)
    assert SettingsManager().get_search_page_size() == 500  # max
