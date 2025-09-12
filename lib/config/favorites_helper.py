
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Favorites Integration Helper
Helper functions for favorites integration settings
"""

from ..utils.kodi_log import get_kodi_logger


def on_favorites_integration_enabled():
    """Called when favorites integration is enabled via settings"""
    logger = get_kodi_logger('lib.config.favorites_helper')
    logger.info("Favorites integration enabled - folder will be visible in menu")
    
    # Ensure "Kodi Favorites" list exists in database (even if empty)
    try:
        from ..data.query_manager import get_query_manager
        query_manager = get_query_manager()
        if query_manager.initialize():
            # Check if Kodi Favorites list exists, create if not
            with query_manager.connection_manager.transaction() as conn:
                kodi_list = conn.execute("""
                    SELECT id FROM lists WHERE name = 'Kodi Favorites'
                """).fetchone()
                
                if not kodi_list:
                    # Create the Kodi Favorites list (empty initially)
                    cursor = conn.execute("""
                        INSERT INTO lists (name, created_at)
                        VALUES ('Kodi Favorites', datetime('now'))
                    """)
                    kodi_list_id = cursor.lastrowid
                    logger.info("Created empty 'Kodi Favorites' list with ID %s", kodi_list_id)
                else:
                    logger.info("'Kodi Favorites' list already exists with ID %s", kodi_list['id'])
        else:
            logger.warning("Could not initialize query manager for favorites list creation")
    except Exception as e:
        logger.error("Error ensuring Kodi Favorites list exists: %s", e)
    
    # No automatic scanning - only manual scan by user
    return True
