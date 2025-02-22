
import xbmcaddon
import xbmcvfs
import os
import json

class Config:
    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.addon_path = xbmcvfs.translatePath(self.addon.getAddonInfo('path'))
        self.db_path = os.path.join(self.addon_path, 'library.db')
        self.max_folder_depth = 5

    def get_setting(self, setting_id):
        """Get addon setting value"""
        return self.addon.getSetting(setting_id)

    def set_setting(self, setting_id, value):
        """Set addon setting value"""
        self.addon.setSetting(setting_id, str(value))


""" /resources/lib/config_manager.py """
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
        self.addon = xbmcaddon.Addon()
        self.addonpath = xbmcvfs.translatePath(self.addon.getAddonInfo('path'))
        self.profile = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        if not os.path.exists(self.profile):
            os.makedirs(self.profile)

        from resources.lib.settings_manager import SettingsManager
        self.settings = SettingsManager()
        self.addondir = self.settings.addon_data_path
        self._max_folder_depth = int(self.settings.get_setting('max_folder_depth') or '3')

        utils.log(f"Addon path - {self.addonpath}", "DEBUG")

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
