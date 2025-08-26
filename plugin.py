
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Main Plugin Entry Point
Handles routing and top-level navigation for the Kodi addon
"""

import sys
from urllib.parse import parse_qsl
import xbmcaddon
import xbmcplugin
import xbmcgui
import urllib.parse

# Import our addon modules
from lib.addon import AddonController
from lib.utils.logger import get_logger
from lib.auth.auth_helper import get_auth_helper
from lib.auth.state import is_authorized


def show_main_menu(handle):
    """Show main menu with auth-aware options"""
    addon = xbmcaddon.Addon()
    
    # Search (always visible)
    search_item = xbmcgui.ListItem(label=addon.getLocalizedString(35014))  # "Search"
    search_url = f"{sys.argv[0]}?action=search"
    xbmcplugin.addDirectoryItem(handle, search_url, search_item, True)
    
    # Lists (always visible)
    lists_item = xbmcgui.ListItem(label=addon.getLocalizedString(35016))  # "Lists"
    lists_url = f"{sys.argv[0]}?action=lists"
    xbmcplugin.addDirectoryItem(handle, lists_url, lists_item, True)
    
    # Auth-dependent menu items
    if is_authorized():
        # Sign out (visible only when authorized)
        signout_item = xbmcgui.ListItem(label=addon.getLocalizedString(35027))  # "Sign out"
        signout_url = f"{sys.argv[0]}?action=signout"
        xbmcplugin.addDirectoryItem(handle, signout_url, signout_item, False)
        
        # Remote features (when authorized)
        remote_lists_item = xbmcgui.ListItem(label=addon.getLocalizedString(35017))  # "Remote Lists"
        remote_lists_url = f"{sys.argv[0]}?action=remote_lists"
        xbmcplugin.addDirectoryItem(handle, remote_lists_url, remote_lists_item, True)
    else:
        # Authorize device (visible only when not authorized)
        auth_item = xbmcgui.ListItem(label=addon.getLocalizedString(35028))  # "Authorize device"
        auth_url = f"{sys.argv[0]}?action=authorize"
        xbmcplugin.addDirectoryItem(handle, auth_url, auth_item, False)
    
    xbmcplugin.endOfDirectory(handle)


def show_search_menu(handle):
    """Show search interface"""
    from lib.ui.search_handler import SearchHandler
    
    search_handler = SearchHandler(handle)
    search_handler.prompt_and_show()


def show_remote_search_menu(handle):
    """Show remote search interface"""
    addon = xbmcaddon.Addon()
    list_item = xbmcgui.ListItem(label=addon.getLocalizedString(35015))
    xbmcplugin.addDirectoryItem(handle, "", list_item, False)
    xbmcplugin.endOfDirectory(handle)


def show_lists_menu(handle):
    """Show lists management interface"""
    addon = xbmcaddon.Addon()
    list_item = xbmcgui.ListItem(label=addon.getLocalizedString(35016))
    xbmcplugin.addDirectoryItem(handle, "", list_item, False)
    xbmcplugin.endOfDirectory(handle)


def show_remote_lists_menu(handle):
    """Show remote lists interface"""
    addon = xbmcaddon.Addon()
    list_item = xbmcgui.ListItem(label=addon.getLocalizedString(35017))
    xbmcplugin.addDirectoryItem(handle, "", list_item, False)
    xbmcplugin.endOfDirectory(handle)


def handle_authorize():
    """Handle device authorization"""
    auth_helper = get_auth_helper()
    auth_helper.start_device_authorization()


def handle_signout():
    """Handle user sign out"""
    from lib.auth.state import clear_tokens
    
    addon = xbmcaddon.Addon()
    
    # Confirm sign out
    if xbmcgui.Dialog().yesno(
        addon.getLocalizedString(35029),  # "Sign out"
        addon.getLocalizedString(35030)   # "Are you sure you want to sign out?"
    ):
        if clear_tokens():
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),  # "LibraryGenie"
                addon.getLocalizedString(35031),  # "Signed out successfully"
                xbmcgui.NOTIFICATION_INFO
            )
        else:
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),  # "LibraryGenie"
                addon.getLocalizedString(35032),  # "Sign out failed"
                xbmcgui.NOTIFICATION_ERROR
            )


def main():
    """Main plugin entry point"""
    logger = get_logger(__name__)

    try:
        # Parse plugin arguments
        addon_handle = int(sys.argv[1]) if len(sys.argv) > 1 else -1
        base_url = sys.argv[0] if len(sys.argv) > 0 else ""
        query_string = sys.argv[2][1:] if len(sys.argv) > 2 and len(sys.argv[2]) > 1 else ""

        # Parse query parameters
        params = dict(parse_qsl(query_string))

        logger.debug(
            f"Plugin called with handle={addon_handle}, url={base_url}, params={params}"
        )

        # Route based on action parameter
        action = params.get('action', '')
        
        if action == 'search':
            show_search_menu(addon_handle)
        elif action == 'lists':
            show_lists_menu(addon_handle)
        elif action == 'remote_lists':
            show_remote_lists_menu(addon_handle)
        elif action == 'authorize':
            handle_authorize()
        elif action == 'signout':
            handle_signout()
        else:
            # Show main menu by default
            show_main_menu(addon_handle)

    except Exception as e:
        logger.error(f"Fatal error in plugin main: {e}")
        # Try to show error to user if possible
        try:
            import xbmcgui
            addon = xbmcaddon.Addon()
            xbmcgui.Dialog().notification(
                addon.getLocalizedString(35002),
                addon.getLocalizedString(35013),
                xbmcgui.NOTIFICATION_ERROR
            )
        except:
            pass


if __name__ == "__main__":
    main()
