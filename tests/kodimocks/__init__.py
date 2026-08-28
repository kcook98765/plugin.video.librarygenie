"""
Lightweight Kodi API stubs for running LibraryGenie tests outside Kodi.

This package installs stand-in modules for the Kodi Python API (xbmc,
xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs) into ``sys.modules`` so that the
addon's ``lib`` package can be imported and its pure-Python / mockable logic
exercised without a live Kodi runtime.

Design goals
------------
* Minimal and readable - just enough surface for import-time and the
  pure-logic / config / search / import-export tests that ship with the
  repository.
* Permissive - any Kodi attribute that is not explicitly modelled resolves
  to a ``unittest.mock.MagicMock`` so that incidental use does not raise.
* Deterministic - ``xbmcaddon.Addon`` settings are backed by a process-wide
  shared dict so that the ``ConfigManager`` / ``SettingsManager`` instances
  that production code creates internally all see the same seeded values,
  and tests can reset it between cases.

Usage
-----
Call :func:`install` (done automatically by ``tests/conftest.py``) *before*
any ``lib`` submodule is imported::

    from tests.kodimocks import install, reset_settings, seed_settings
    install()
    seed_settings(search_page_size=10)
    import lib.config.settings  # now safe
"""

from __future__ import annotations

import types
from unittest.mock import MagicMock

# Log level constants used by lib.utils.kodi_log and friends.
_LOG_LEVELS = {
    "LOGDEBUG": 0,
    "LOGINFO": 1,
    "LOGWARNING": 2,
    "LOGERROR": 3,
    "LOGFATAL": 4,
    "LOGNONE": 99,
}

# Process-wide shared settings store. ``Addon`` instances all read/write here
# so that internally-created ``ConfigManager`` / ``SettingsManager`` objects
# observe the values a test seeded.
_STATE: dict = {"settings": {}}


def seed_settings(**values) -> None:
    """Set one or more addon setting values for the current test."""
    _STATE["settings"].update(values)


def reset_settings() -> None:
    """Clear all seeded addon setting values (call in a fixture)."""
    _STATE["settings"].clear()


def get_seed() -> dict:
    """Return the current seeded settings (read-only convenience)."""
    return dict(_STATE["settings"])


class _StubBase:
    """Permissive base for Kodi classes that get subclassed or instantiated.

    Accepts any constructor arguments and no-ops common Kodi methods so that
    class definitions and casual instance method calls do not raise.
    """

    def __init__(self, *args, **kwargs):  # noqa: D401 - intentionally permissive
        self._label = ""
        self._path = ""

    # -- common Kodi object methods (no-ops / identity) ---------------------
    def close(self, *args, **kwargs):
        return None

    def setLabel(self, *args, **kwargs):
        return None

    setItem = setLabel

    def setArt(self, *args, **kwargs):
        return None

    def setInfo(self, *args, **kwargs):
        return None

    def select(self, *args, **kwargs):
        return True

    def clear(self, *args, **kwargs):
        return None

    def addItem(self, *args, **kwargs):
        return None

    def addSortMethod(self, *args, **kwargs):
        return None

    def setFocus(self, *args, **kwargs):
        return None

    def setProperty(self, *args, **kwargs):
        return None

    def getFocus(self, *args, **kwargs):
        return -1

    def getNumItems(self, *args, **kwargs):
        return 0


class Addon:
    """Stub of ``xbmcaddon.Addon`` backed by a shared dict of setting values.

    * ``getAddonInfo(key)`` returns plausible special:// paths.
    * ``getLocalizedString(msgid)`` returns a deterministic string.
    * ``getSettingString(key)`` returns the seeded value, or ``""`` when the
      key is not seeded (matches Kodi's "unset" behaviour for strings).
    * The typed getters (``getSettingBool/Int/Number``) return the seeded
      value when present and otherwise **raise**, which drives
      ``ConfigManager`` into its documented string/defaults fallback path --
      the behaviour we want to exercise in tests.
    """

    def __init__(self, addon_id: str = "plugin.video.librarygenie", values: dict | None = None):
        self._id = addon_id
        # Per-instance seed overrides layered on top of the shared store.
        self._overrides = dict(values or {})

    # -- settings store helpers --------------------------------------------
    def _get(self, key: str):
        if key in self._overrides:
            return self._overrides[key]
        return _STATE["settings"].get(key)

    # -- info ---------------------------------------------------------------
    def getAddonInfo(self, key: str):
        if key == "profile":
            return "special://userdata/addon_data/plugin.video.librarygenie/"
        if key == "path":
            return "/opt/kodi/addons/" + self._id + "/"
        if key in ("id", "addon"):
            return self._id
        if key == "name":
            return "LibraryGenie"
        if key == "version":
            return "0.8.49"
        return ""

    def getAddonId(self):
        return self._id

    def getAddonVersion(self):
        return "0.8.49"

    def hasSetting(self, key: str):
        return key in self._overrides or key in _STATE["settings"]

    def getSettingString(self, key: str):
        value = self._get(key)
        return "" if value is None else value

    def getSettingBool(self, key: str):
        value = self._get(key)
        if value is None:
            raise RuntimeError("getSettingBool: no bool value for '%s'" % key)
        return bool(value)

    def getSettingInt(self, key: str):
        value = self._get(key)
        if value is None:
            raise RuntimeError("getSettingInt: no int value for '%s'" % key)
        return int(value)

    def getSettingNumber(self, key: str):
        value = self._get(key)
        if value is None:
            raise RuntimeError("getSettingNumber: no number value for '%s'" % key)
        return float(value)

    def getSettingSelect(self, key: str):
        value = self._get(key)
        return int(value) if value is not None else 0

    # -- write helpers ------------------------------------------------------
    def setSetting(self, key: str, value):
        _STATE["settings"][key] = value
        return True

    def setSettingBool(self, key: str, value: bool):
        _STATE["settings"][key] = bool(value)
        return True

    def setSettingInt(self, key: str, value: int):
        _STATE["settings"][key] = int(value)
        return True

    def setSettingNumber(self, key: str, value):
        _STATE["settings"][key] = float(value)
        return True

    def setSettingString(self, key: str, value: str):
        _STATE["settings"][key] = str(value)
        return True

    def getSetting(self, key: str):  # legacy alias
        return self.getSettingString(key)

    def getLocalizedString(self, msgid):
        return "loc_%s" % msgid


class _Window(_StubBase):
    """Stub ``xbmcgui.Window`` with the few methods used at import time."""

    def getProperty(self, key: str):
        return ""

    def setProperty(self, key: str, value):
        return None

    def isModalDialogVisible(self, *args, **kwargs):
        return False


# GUI dialog / listitem classes that LibraryGenie subclasses or constructs.
_WINDOW_XML_DIALOG = type("WindowXMLDialog", (_StubBase,), {})
_WINDOW_XML = type("WindowXML", (_StubBase,), {})
_DIALOG = type("Dialog", (_StubBase,), {})
_DIALOG_OK = type("DialogOK", (_StubBase,), {})
_INFO_DIALOG = type("InfoDialog", (_StubBase,), {})
_TEXT_ENTRY_DIALOG = type("TextEntryDialog", (_StubBase,), {})
_TEXT_EDITOR_DIALOG = type("TextEditorDialog", (_StubBase,), {})
_PROGRESS = type("Progress", (_StubBase,), {})
_NOTIFICATION = type("Notification", (_StubBase,), {})
_LIST_ITEM = type("ListItem", (_StubBase,), {})
_GUI_WINDOW = _Window


def _build_module(name: str, extra: dict | None = None) -> types.ModuleType:
    """Create a module with explicit attributes plus a MagicMock fallback."""
    module = types.ModuleType(name)

    def _module_getattr(attr: str):
        # Anything not explicitly provided resolves to a fresh MagicMock so
        # incidental Kodi usage in pure-logic code paths does not raise.
        return MagicMock(name="%s.%s" % (name, attr))

    module.__dict__["__getattr__"] = _module_getattr  # PEP 562
    if extra:
        for key, value in extra.items():
            setattr(module, key, value)
    return module


def install() -> None:
    """Install all Kodi API stub modules into ``sys.modules``.

    Idempotent - safe to call more than once.
    """
    import sys

    xbmc = _build_module(
        "xbmc",
        {
            "log": lambda message, level=0: None,
            "executebuiltin": lambda *a, **k: None,
            "executePermacommand": lambda *a, **k: None,
            "getCondVisibility": lambda expr: False,
            "Monitor": _StubBase,
            "Monit": _StubBase,
            "Notification": _NOTIFICATION,
            "ShutDown": lambda *a, **k: None,
            "TranslatePath": lambda p: "/tmp/" + (p or ""),
        },
    )
    for level, value in _LOG_LEVELS.items():
        setattr(xbmc, level, value)

    xbmcaddon = _build_module(
        "xbmcaddon",
        {
            "Addon": Addon,
            "Monitor": _StubBase,
            "GUI": _StubBase,
        },
    )

    xbmcgui = _build_module(
        "xbmcgui",
        {
            "WindowXMLDialog": _WINDOW_XML_DIALOG,
            "WindowXML": _WINDOW_XML,
            "Dialog": _DIALOG,
            "DialogOK": _DIALOG_OK,
            "InfoDialog": _INFO_DIALOG,
            "TextEntryDialog": _TEXT_ENTRY_DIALOG,
            "TextEditorDialog": _TEXT_EDITOR_DIALOG,
            "Progress": _PROGRESS,
            "Notification": _NOTIFICATION,
            "ListItem": _LIST_ITEM,
            "Window": _GUI_WINDOW,
            "WindowDialog": _DIALOG,
            "INPUT": {"OK": 0},
        },
    )

    # xbmcplugin constants are referenced as module attributes in some paths.
    xbmcplugin = _build_module(
        "xbmcplugin",
        {
            "addDirectoryResult": lambda *a, **k: None,
            "endOfDirectory": lambda *a, **k: None,
            "setResolvedUrl": lambda *a, **k: None,
            "sortMethods": {},
        },
    )
    for const in (
        "SORT_METHOD_NONE", "SORT_METHOD_LABEL", "SORT_METHOD_DATE",
        "SORT_METHOD_SIZE", "SORT_METHOD_TYPE", "SORT_METHOD_VIDEO_DURATION",
    ):
        setattr(xbmcplugin, const, 0)

    import tempfile

    _stub_dir = tempfile.mkdtemp(prefix="lg_kodi_stub_")

    xbmcvfs = _build_module(
        "xbmcvfs",
        {
            "translatePath": lambda p: (
                p.replace("special://userdata/addon_data/", _stub_dir + "/")
                if p and p.startswith("special://")
                else _stub_dir + "/" + (p or "")
            ),
            "exists": lambda p: False,
            "deleteFile": lambda *a, **k: True,
            "File": _StubBase,
            "create": lambda *a, **k: None,
            "FreeSpace": lambda p: 1_000_000_000,
            "GetDiskSpace": lambda p: 1_000_000_000,
        },
    )

    sys.modules["xbmc"] = xbmc
    sys.modules["xbmcaddon"] = xbmcaddon
    sys.modules["xbmcgui"] = xbmcgui
    sys.modules["xbmcplugin"] = xbmcplugin
    sys.modules["xbmcvfs"] = xbmcvfs


__all__ = ["install", "Addon", "seed_settings", "reset_settings", "get_seed"]
