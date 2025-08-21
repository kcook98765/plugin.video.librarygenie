import os
from functools import lru_cache
from .addon_ref import get_addon
import xbmcvfs
from resources.lib.utils import utils
from resources.lib.utils.utils import log_once

class Config:
    """ FIELDS should align with table list_items fields AND for use in listitem building """
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    FIELDS = [
        "cast TEXT", "country TEXT", "dateadded TEXT", "director TEXT", "duration INTEGER", "fanart TEXT", "file TEXT", "genre TEXT",
        "imdbnumber TEXT", "kodi_id INTEGER", "media_type TEXT", "mpaa TEXT", "path TEXT", "play TEXT", "plot TEXT",
        "premiered TEXT", "rating REAL", "search_score REAL", "source TEXT", "status TEXT", "stream_url TEXT", "studio TEXT",
        "tagline TEXT", "thumbnail TEXT", "poster TEXT", "art TEXT", "title TEXT", "trailer TEXT", "uniqueid TEXT",
        "votes INTEGER", "writer TEXT", "year INTEGER"
    ]

    def __init__(self):
        """
        Initializes the Config with addon settings and paths.
        """
        if Config._initialized:
            return

        log_once("config_init", "=== Initializing Config Manager ===", "DEBUG")
        log_once("addon_instance", "Getting addon instance", "DEBUG")
        self._addon = get_addon()
        log_once("addon_success", "Successfully got addon instance", "DEBUG")

        # Import here to avoid circular dependency
        log_once("settings_init", "Initializing SettingsManager", "DEBUG")
        from .settings_manager import SettingsManager
        self.settings = SettingsManager()

        utils.log("Reading addon information", "DEBUG")
        self.addonid = self._addon.getAddonInfo('id')
        self.addonname = self._addon.getAddonInfo('name')
        self.addonversion = self._addon.getAddonInfo('version')
        log_once("addon_details", f"Addon details - ID: {self.addonid}, Name: {self.addonname}, Version: {self.addonversion}", "INFO")

        self.addonpath = xbmcvfs.translatePath(self._addon.getAddonInfo('path'))
        log_once("addon_path", f"Addon path: {self.addonpath}", "DEBUG")

        self.profile = xbmcvfs.translatePath(self._addon.getAddonInfo('profile'))
        log_once("profile_path", f"Profile path: {self.profile}", "DEBUG")

        if not os.path.exists(self.profile):
            utils.log(f"Creating profile directory: {self.profile}", "DEBUG")
            os.makedirs(self.profile)
        else:
            log_once("profile_exists", "Profile directory already exists", "DEBUG")

        utils.log("=== Config Manager initialization complete ===", "DEBUG")
        Config._initialized = True

    def get_setting(self, setting_id, default=""):
        """Get addon setting by name with proper normalization"""
        value = self._addon.getSetting(setting_id)
        # Normalize None to empty string
        if value is None:
            value = default

        # Log with proper masking for sensitive settings
        if setting_id in ['lgs_upload_key', 'remote_api_key']:
            masked_value = (value[:4] + "..." + value[-2:]) if value else "(not set)"
            utils.log(f"Config: Retrieved setting '{setting_id}': '{masked_value}'", "DEBUG")
        else:
            utils.log(f"Config: Retrieved setting '{setting_id}': '{value or '(not set)'}'", "DEBUG")

        return value

    def set_setting(self, setting_id, value):
        """Set addon setting value"""
        self.settings.set_setting(setting_id, value)

    @property
    def db_path(self):
        return os.path.join(self.profile, 'librarygenie.db')

    @property
    def max_folder_depth(self):
        if self._max_folder_depth is None:
            try:
                self._max_folder_depth = int(self.get_setting('max_folder_depth', '2'))
            except (ValueError, TypeError):
                self._max_folder_depth = 2
        return self._max_folder_depth

    def refresh_max_folder_depth(self):
        """Refresh the cached max folder depth from settings"""
        self._max_folder_depth = None

    def _load_hint_file(self, filename):
        filepath = os.path.join(self.addonpath, "resources", "lib", filename)
        utils.log(f"Loading hint file from: {filepath}", "DEBUG")
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read()

    @property
    def hints_example(self):
        return (
            '"params": {\n'
            '  "filter": {\n'
            '    "or": [\n'
            '      {"field": "plot", "operator": "contains", "value": "horse"},\n'
            '      {"field": "plot", "operator": "contains", "value": "equine"}\n'
            '    ]\n'
            '  }\n'
            '}'
        )

    @property
    def hints_movies(self):
        return self._load_hint_file("hints_movies.txt")

    @property
    def hints_tv(self):
        return self._load_hint_file("hints_tv.txt")

    @property
    def query_manager(self):
        """Get the singleton QueryManager instance"""
        if self._query_manager is None:
            from resources.lib.data.query_manager import QueryManager
            self._query_manager = QueryManager(self.db_path)
        return self._query_manager

# Singleton accessor for Config
@lru_cache(maxsize=1)
def get_config():
    """Get the singleton Config instance"""
    return Config()