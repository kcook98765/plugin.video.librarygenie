from .addon_ref import get_addon
import xbmcvfs

class SettingsManager:
    def __init__(self, addon_id='plugin.video.librarygenie'):
        try:
            self.addon = get_addon() if addon_id == 'plugin.video.librarygenie' else xbmcaddon.Addon(id=addon_id)
        except RuntimeError:
            self.addon = xbmcaddon.Addon(id=addon_id)
        self._cache = {}

    def get_setting(self, key, default=None):
        if key not in self._cache:
            self._cache[key] = self.addon.getSetting(key)
        # Only log non-sensitive settings
        if key not in ['lgs_upload_key', 'remote_api_key']:
            from . import utils
            utils.log(f"SettingsManager: Getting setting '{key}': '{self._cache[key] or default}'", "DEBUG")
        return self._cache[key] or default

    def set_setting(self, key, value):
        self._cache[key] = value
        self.addon.setSetting(key, str(value))
        # Only log non-sensitive settings
        if key not in ['lgs_upload_key', 'remote_api_key']:
            from . import utils
            utils.log(f"SettingsManager: Setting '{key}' to '{value}'", "DEBUG")

    def clear_cache(self):
        self._cache.clear()

    def authenticate_with_code(self):
        """Trigger one-time code authentication"""
        from resources.lib.authenticate_code import authenticate_with_code
        return authenticate_with_code()

    @property 
    def addon_path(self):
        return xbmcvfs.translatePath(self.addon.getAddonInfo('path'))

    @property
    def addon_data_path(self):
        return xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
