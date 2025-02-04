""" /resources/lib/config_manager.py """
import os
import xbmc
import xbmcaddon
import xbmcvfs

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
        self.addon = xbmcaddon.Addon(id='plugin.video.listgenius')
        self.addondir = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        self.addonpath = xbmcvfs.translatePath(self.addon.getAddonInfo('path'))
        self._openai_api_key = self.addon.getSetting('openai_api_key')
        self._base_url = self.addon.getSetting('base_url')
        self._api_temperature = float(self.addon.getSetting('api_temperature'))
        self._api_max_tokens = int(self.addon.getSetting('api_max_tokens'))

        xbmc.log(f"ListGenius: Addon path - {self.addonpath}", xbmc.LOGDEBUG)

    @property
    def openai_api_key(self):
        return self._openai_api_key or ""

    @property
    def base_url(self):
        return self._base_url or "https://api.openai.com/v1/completions"

    @property
    def db_path(self):
        db_path = os.path.join(self.addondir, "listgenius.db")
        xbmc.log(f"ListGenius: Database path: {db_path}", xbmc.LOGDEBUG)
        return db_path

    @property
    def api_temperature(self):
        return self._api_temperature

    @property
    def api_max_tokens(self):
        return self._api_max_tokens

    def _load_hint_file(self, filename):
        filepath = os.path.join(self.addonpath, "resources", "lib", filename)
        xbmc.log(f"ListGenius: Loading hint file from: {filepath}", xbmc.LOGDEBUG)
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
