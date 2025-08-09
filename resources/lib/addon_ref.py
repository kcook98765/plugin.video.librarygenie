
import xbmcaddon

ADDON_ID = "plugin.video.librarygenie"

def get_addon():
    """Always pass an explicit id so Kodi doesn't need to infer context"""
    return xbmcaddon.Addon(id=ADDON_ID)
