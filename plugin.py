
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Main Plugin Entry Point
Handles routing and top-level navigation for the Kodi addon
"""

import sys
from urllib.parse import parse_qsl
import xbmcaddon
import xbmcplugin

# Import our addon modules
from lib.addon import AddonController
from lib.utils.logger import get_logger


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

        # Initialize addon controller
        controller = AddonController(addon_handle, base_url, params)

        # Route the request
        controller.route()

    except Exception as e:
        logger.error(f"Fatal error in plugin main: {e}")
        # Try to show error to user if possible
        try:
            import xbmcgui
            xbmcgui.Dialog().notification(
                "Movie List Manager",
                "Plugin failed to start. Check logs.",
                xbmcgui.NOTIFICATION_ERROR
            )
        except:
            pass


if __name__ == "__main__":
    main()
