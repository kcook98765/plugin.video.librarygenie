import xbmcaddon
import xbmcvfs

class SettingsManager:
    def __init__(self, addon_id='plugin.video.librarygenie'):
        self.addon = xbmcaddon.Addon(id=addon_id)
        self._cache = {}

    def get_setting(self, key, default=None):
        if key not in self._cache:
            self._cache[key] = self.addon.getSetting(key)
        return self._cache[key] or default

    def set_setting(self, key, value):
        self._cache[key] = value
        self.addon.setSetting(key, str(value))

    def clear_cache(self):
        self._cache.clear()

    @property 
    def addon_path(self):
        return xbmcvfs.translatePath(self.addon.getAddonInfo('path'))

    @property
    def addon_data_path(self):
        return xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
