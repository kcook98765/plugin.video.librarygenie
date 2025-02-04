""" /resources/lib/config_manager.py """
import os
import xbmcaddon
import xbmcvfs
from resources.lib import utils

class Config:
    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.addonpath = xbmcvfs.translatePath(self.addon.getAddonInfo('path'))
        self.profile = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        if not os.path.exists(self.profile):
            os.makedirs(self.profile)
        self.db_path = os.path.join(self.profile, 'librarygenie.db')
        self.max_folder_depth = 5

    FIELDS = [
        'title TEXT',
        'kodi_id INTEGER',
        'play TEXT',
        'plot TEXT',
        'genre TEXT',
        'director TEXT',
        'writer TEXT',
        'cast TEXT',
        'rating REAL',
        'votes INTEGER',
        'duration INTEGER',
        'year INTEGER',
        'country TEXT',
        'studio TEXT',
        'trailer TEXT',
        'tagline TEXT',
        'source TEXT',
        'premiered TEXT',
        'thumbnail TEXT',
        'fanart TEXT',
        'mpaa TEXT'
    ]

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
        from resources.lib.settings_manager import SettingsManager
        self.settings = SettingsManager()
        self.addondir = self.settings.addon_data_path
        self.addonpath = self.settings.addon_path
        self._openai_api_key = self.settings.get_setting('openai_api_key')
        self._base_url = self.settings.get_setting('base_url')
        self._api_temperature = float(self.settings.get_setting('api_temperature', '0.7'))
        self._api_max_tokens = int(self.settings.get_setting('api_max_tokens', '2048'))
        self._max_folder_depth = int(self.settings.get_setting('max_folder_depth', '3'))

        utils.log(f"Addon path - {self.addonpath}", "DEBUG")

    @property
    def openai_api_key(self):
        return self._openai_api_key or ""

    @property
    def base_url(self):
        return self._base_url or "https://api.openai.com/v1/completions"

    @property
    def db_path(self):
        db_path = os.path.join(self.addondir, "librarygenie.db")
        utils.log(f"Database path: {db_path}", "DEBUG")
        return db_path

    @property
    def api_temperature(self):
        return self._api_temperature

    @property
    def api_max_tokens(self):
        return self._api_max_tokens

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