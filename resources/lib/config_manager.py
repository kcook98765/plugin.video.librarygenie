import os
import xbmcaddon
import xbmcvfs
from . import utils

class Config:
    """ FIELDS should align with table list_items fields AND for use in listitem building """
    FIELDS = [
        "cast TEXT",
        "country TEXT",
        "dateadded TEXT",
        "director TEXT",
        "duration INTEGER",
        "fanart TEXT",
        "genre TEXT",
        "imdbnumber TEXT",
        "kodi_id INTEGER",
        "media_type TEXT",
        "mpaa TEXT",
        "path TEXT",
        "play TEXT",
        "plot TEXT",
        "premiered TEXT",
        "rating REAL",
        "source TEXT",
        "status TEXT",
        "stream_url TEXT",
        "studio TEXT",
        "tagline TEXT",
        "thumbnail TEXT",
        "poster TEXT",
        "art TEXT",
        "title TEXT", 
        "trailer TEXT",
        "uniqueid TEXT",
        "votes INTEGER",
        "writer TEXT",
        "year INTEGER"
    ]

    def __init__(self):
        """
        Initializes the Config with addon settings and paths.
        """
        utils.log("=== Initializing Config Manager ===", "DEBUG")
        
        try:
            utils.log("Attempting to get addon instance automatically", "DEBUG")
            self.addon = xbmcaddon.Addon()
            utils.log("Successfully got addon instance automatically", "DEBUG")
        except (RuntimeError, Exception) as e:
            # Fallback when addon ID cannot be automatically detected
            utils.log(f"Failed to get addon automatically, using explicit ID: {str(e)}", "DEBUG")
            try:
                self.addon = xbmcaddon.Addon(id='plugin.video.librarygenie')
                utils.log("Successfully got addon instance with explicit ID", "DEBUG")
            except Exception as e2:
                utils.log(f"CRITICAL: Failed to get addon with explicit ID: {str(e2)}", "ERROR")
                raise

        # Import here to avoid circular dependency
        utils.log("Initializing SettingsManager", "DEBUG")
        from .settings_manager import SettingsManager
        self.settings = SettingsManager()
        
        utils.log("Reading addon information", "DEBUG")
        self.addonid = self.addon.getAddonInfo('id')
        self.addonname = self.addon.getAddonInfo('name')
        self.addonversion = self.addon.getAddonInfo('version')
        self.addonpath = xbmcvfs.translatePath(self.addon.getAddonInfo('path'))
        self.profile = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        self._max_folder_depth = 5  # Set maximum folder depth

        utils.log(f"Addon details - ID: {self.addonid}, Name: {self.addonname}, Version: {self.addonversion}", "INFO")
        utils.log(f"Addon path: {self.addonpath}", "DEBUG")
        utils.log(f"Profile path: {self.profile}", "DEBUG")

        if not os.path.exists(self.profile):
            utils.log(f"Creating profile directory: {self.profile}", "DEBUG")
            os.makedirs(self.profile)
        else:
            utils.log("Profile directory already exists", "DEBUG")

        utils.log("=== Config Manager initialization complete ===", "DEBUG")

    def get_setting(self, setting_id):
        """Get addon setting by name"""
        value = self.addon.getSetting(setting_id)
        if setting_id == 'lgs_upload_key':
            utils.log(f"Config: Retrieved setting '{setting_id}': '{value[:10] if value else None}...'", "DEBUG")
        elif setting_id in ['remote_api_key', 'remote_api_url']:
            utils.log(f"Config: Retrieved setting '{setting_id}': '{value[:20] if value else None}...'", "DEBUG")
        return value

    def set_setting(self, setting_id, value):
        """Set addon setting value"""
        self.settings.set_setting(setting_id, value)

    @property
    def db_path(self):
        return os.path.join(self.profile, 'librarygenie.db')

    @property
    def max_folder_depth(self):
        return self._max_folder_depth

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