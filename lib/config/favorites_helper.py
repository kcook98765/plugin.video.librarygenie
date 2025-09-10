
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Favorites Integration Helper
Helper functions for favorites integration settings
"""

from ..utils.logger import get_logger


def on_favorites_integration_enabled():
    """Called when favorites integration is enabled via settings"""
    logger = get_logger(__name__)
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
                    logger.info(f"Created empty 'Kodi Favorites' list with ID {kodi_list_id}")
                else:
                    logger.info(f"'Kodi Favorites' list already exists with ID {kodi_list['id']}")
        else:
            logger.warning("Could not initialize query manager for favorites list creation")
    except Exception as e:
        logger.error(f"Error ensuring Kodi Favorites list exists: {e}")
    
    # No automatic scanning - only manual scan by user
    return True
