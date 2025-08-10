import xbmcaddon
from functools import lru_cache

ADDON_ID = "plugin.video.librarygenie"

@lru_cache(maxsize=1)
def get_addon():
    # Always pass an explicit id so Kodi doesn't need to infer context
    return xbmcaddon.Addon(id=ADDON_ID)