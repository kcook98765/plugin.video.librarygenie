#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - List Operations
Handles core list management operations (create, delete, rename, add items)
"""

from typing import Dict, Any, Optional
import xbmcgui
from lib.ui.plugin_context import PluginContext
from lib.ui.response_types import DialogResponse
from lib.ui.localization import L
from lib.utils.kodi_log import get_kodi_logger
from lib.data.query_manager import get_query_manager


class ListOperations:
    """Handles core list management operations"""

    def __init__(self, context: PluginContext):
        self.context = context
        self.logger = get_kodi_logger('lib.ui.list_operations')
        # Get query manager with fallback
        self.query_manager = context.query_manager
        if self.query_manager is None:
            from lib.data.query_manager import get_query_manager
            self.query_manager = get_query_manager()
        self.storage_manager = context.storage_manager

    def create_list(self, context: PluginContext) -> DialogResponse:
        """Handle creating a new list"""
        try:
            context.logger.info("Handling create list request")

            # Get list name from user
            list_name = xbmcgui.Dialog().input(
                "Enter list name:", # This string should also be localized
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not list_name or not list_name.strip():
                context.logger.info("User cancelled list creation or entered empty name")
                return DialogResponse(success=False, message="")

            # Use injected query manager and create list
            if not self.query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message=L(34306)  # "Database error" (red color)
                )

            result = self.query_manager.create_list(list_name.strip())

            if result.get("error"):
                if result["error"] == "duplicate_name":
                    message = f"List '{list_name}' already exists" # This string should also be localized
                else:
                    message = L(30507)  # "Failed to create list" (red color)

                return DialogResponse(
                    success=False,
                    message=message
                )
            else:
                context.logger.info("Successfully created list: %s", list_name)
                return DialogResponse(
                    success=True,
                    message=f"Created list: {list_name}", # This string should also be localized
                    refresh_needed=True,
                    data={'id': result.get('id'), 'name': list_name}  # Include new list ID
                )

        except Exception as e:
            context.logger.error("Error creating list: %s", e)
            return DialogResponse(
                success=False,
                message="Error creating list" # This string should also be localized
            )

    def delete_list(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Handle deleting a list"""
        try:
            context.logger.info("Deleting list %s", list_id)

            # Use injected query manager
            if not self.query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message=L(34306)  # "Database error" (red color)
                )

            # Get current list info
            list_info = self.query_manager.get_list_by_id(list_id)
            if not list_info:
                return DialogResponse(
                    success=False,
                    message=L(37019)  # "List not found" (red color)
                )
            list_name = list_info.get('name', 'Unnamed List')

            # Show confirmation dialog with proper formatting
            dialog_lines = [
                f"Are you sure you want to delete '{list_name}'?",
                "",
                "This will permanently remove the list and all its items.",
                "",
                "This action cannot be undone."
            ]

            confirm = xbmcgui.Dialog().yesno(
                "Delete List",
                "\n".join(dialog_lines)
            )

            if not confirm:
                context.logger.info("User cancelled list deletion")
                return DialogResponse(success=False, message="")

            # Delete the list
            result = self.query_manager.delete_list(list_id)

            if result.get("error"):
                return DialogResponse(
                    success=False,
                    message="Failed to delete list" # This string should also be localized
                )
            else:
                context.logger.info("Successfully deleted list: %s", list_name)
                return DialogResponse(
                    success=True,
                    message=f"Deleted list: {list_name}", # This string should also be localized
                    navigate_to_lists=True  # Navigate away from deleted list to prevent stale view
                )

        except Exception as e:
            context.logger.error("Error deleting list: %s", e)
            return DialogResponse(
                success=False,
                message="Error deleting list" # This string should also be localized
            )

    def rename_list(self, context: PluginContext, list_id: str) -> DialogResponse:
        """Handle renaming a list"""
        try:
            context.logger.info("Renaming list %s", list_id)

            # Use injected query manager
            if not self.query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message=L(34306)  # "Database error" (red color)
                )

            # Get current list info
            list_info = self.query_manager.get_list_by_id(list_id)
            if not list_info:
                return DialogResponse(
                    success=False,
                    message=L(37019)  # "List not found" (red color)
                )

            # Get new name from user
            new_name = xbmcgui.Dialog().input(
                "Enter new list name:", # This string should also be localized
                defaultt=list_info['name'],
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not new_name or not new_name.strip():
                context.logger.info("User cancelled list rename or entered empty name")
                return DialogResponse(success=False, message="")

            # Update the list name
            result = self.query_manager.rename_list(list_id, new_name.strip())

            if result.get("error"):
                if result["error"] == "duplicate_name":
                    message = f"List '{new_name}' already exists" # This string should also be localized
                else:
                    message = "Failed to rename list" # This string should also be localized

                return DialogResponse(
                    success=False,
                    message=message
                )
            else:
                context.logger.info("Successfully renamed list to: %s", new_name)
                return DialogResponse(
                    success=True,
                    message=f"Renamed list to: {new_name}" # This string should also be localized
                )

        except Exception as e:
            context.logger.error("Error renaming list: %s", e)
            return DialogResponse(
                success=False,
                message="Error renaming list" # This string should also be localized
            )

    def remove_from_list(self, context: PluginContext, list_id: str, item_id: str) -> DialogResponse:
        """Handle removing an item from a list"""
        try:
            # Use injected query manager
            if not self.query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return DialogResponse(
                    success=False,
                    message=L(34306)  # "Database error" (red color)
                )

            # Get list and item info
            list_info = self.query_manager.get_list_by_id(list_id)
            if not list_info:
                return DialogResponse(
                    success=False,
                    message=L(37019)  # "List not found" (red color)
                )

            # Get item info to show in confirmation - search through list items to find the specific item
            list_items = self.query_manager.get_list_items(list_id, limit=1000)
            item_info = None
            for item in list_items:
                if str(item.get('id')) == str(item_id):
                    item_info = item
                    break
            
            if not item_info:
                return DialogResponse(
                    success=False,
                    message="Item not found" # This string should also be localized
                )

            item_title = item_info.get('title', 'Unknown Item')
            list_name = list_info.get('name', 'Unnamed List')

            # Show confirmation dialog
            confirm = xbmcgui.Dialog().yesno(
                "Remove Item",
                f"Remove '{item_title}' from '{list_name}'?"
            )

            if not confirm:
                context.logger.info("User cancelled item removal")
                return DialogResponse(success=False, message="")

            # Remove item from list - use correct method name
            result = self.query_manager.delete_item_from_list(list_id, item_id)

            if result.get("error"):
                return DialogResponse(
                    success=False,
                    message="Failed to remove item from list" # This string should also be localized
                )
            else:
                context.logger.info("Successfully removed item %s from list %s", item_id, list_id)
                return DialogResponse(
                    success=True,
                    message=f"Removed '{item_title}' from '{list_name}'", # This string should also be localized
                    refresh_needed=True
                )

        except Exception as e:
            context.logger.error("Error removing item from list: %s", e)
            return DialogResponse(
                success=False,
                message="Error removing item from list" # This string should also be localized
            )

    def set_default_list(self, context: PluginContext) -> DialogResponse:
        """Handle setting the default list for quick-add functionality"""
        try:
            context.logger.info("Handling set default list request")

            # Initialize query manager
            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager for set_default_list")
                return DialogResponse(
                    success=False,
                    message=L(34306)  # "Database error" (red color)
                )

            # Get all available lists
            all_lists = query_manager.get_all_lists_with_folders()

            if not all_lists:
                # Offer to create a new list if none exist
                if xbmcgui.Dialog().yesno("No Lists Found", "No lists available. Create a new list to set as default?"): # Localize these strings
                    result = self.create_list(context)
                    if result.success:
                        # Refresh the list of lists
                        all_lists = query_manager.get_all_lists_with_folders()
                    else:
                        context.logger.warning("Failed to create a new list for default.")
                        return DialogResponse(
                            success=False,
                            message="Failed to create new list" # Localize this string
                        )
                else:
                    context.logger.info("User chose not to create a new list.")
                    return DialogResponse(success=False, message="")

            if not all_lists:  # Still no lists
                return DialogResponse(
                    success=False,
                    message="No lists available to set as default" # Localize this string
                )

            # Build list options for selection
            list_options = []
            list_ids = []
            for lst in all_lists:
                folder_name = lst.get('folder_name', 'Root')
                if folder_name == 'Root' or not folder_name:
                    display_name = lst['name']
                else:
                    display_name = f"{folder_name}/{lst['name']}"
                list_options.append(display_name)
                list_ids.append(lst['id'])

            # Add option to create new list
            list_options.append(f"+ {L(37018)}")

            # Show list selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Set Default Quick-Add List:", list_options) # Localize this string

            if selected_index < 0:
                context.logger.info("User cancelled setting default list.")
                return DialogResponse(success=False, message="")

            target_list_id = None
            if selected_index == len(list_options) - 1:  # User chose to create a new list
                result = self.create_list(context)
                if not result.success:
                    context.logger.warning("Failed to create new list for default.")
                    return DialogResponse(
                        success=False,
                        message="Failed to create new list" # Localize this string
                    )
                # Get the newly created list ID
                all_lists = query_manager.get_all_lists_with_folders()  # Refresh lists
                if all_lists:
                    target_list_id = all_lists[-1]['id']  # Assume last created
                else:
                    context.logger.error("Could not retrieve newly created list ID.")
                    return DialogResponse(
                        success=False,
                        message="Could not retrieve newly created list" # Localize this string
                    )
            else:
                target_list_id = list_ids[selected_index]

            if target_list_id is None:
                context.logger.error("Target list ID is None.")
                return DialogResponse(
                    success=False,
                    message="Invalid list selection" # Localize this string
                )

            # Set the default list ID in settings
            from lib.config.settings import SettingsManager
            settings = SettingsManager()
            settings.set_default_list_id(target_list_id)

            # Get list name for confirmation message
            selected_list_name = list_options[selected_index].split(' (')[0] if selected_index < len(list_options) - 1 else "newly created list"

            context.logger.info("Set default quick-add list to: %s", selected_list_name)
            return DialogResponse(
                success=True,
                message=f"Default quick-add list set to: '{selected_list_name}'" # Localize this string
            )

        except Exception as e:
            context.logger.error("Error in set_default_list: %s", e)
            return DialogResponse(
                success=False,
                message="Failed to set default list" # Localize this string
            )

    def add_to_list_menu(self, context: PluginContext, media_item_id: str) -> bool:
        """Handle adding media item to a list"""
        try:
            if not media_item_id:
                context.logger.error("No media item ID provided")
                return False

            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager")
                return False

            # Get all available lists, excluding special lists
            all_lists = query_manager.get_all_lists_with_folders()
            available_lists = [lst for lst in all_lists if lst.get('folder_name') != 'Search History' and lst.get('name') != 'Kodi Favorites']
            if not available_lists:
                # Offer to create a new list
                if xbmcgui.Dialog().yesno("No Lists Found", "No lists available. Create a new list?"): # Localize these strings
                    result = self.create_list(context)
                    if result.success:
                        # Refresh lists and continue
                        all_lists = query_manager.get_all_lists_with_folders()
                        available_lists = [lst for lst in all_lists if lst.get('folder_name') != 'Search History' and lst.get('name') != 'Kodi Favorites']
                    else:
                        return False
                else:
                    return False

            # Build list options for selection
            list_options = []
            for lst in available_lists:
                folder_name = lst.get('folder_name', 'Root')
                if folder_name == 'Root' or not folder_name:
                    list_options.append(lst['name'])
                else:
                    list_options.append(f"{folder_name}/{lst['name']}")

            # Add option to create new list
            list_options.append(f"+ {L(37018)}")

            # Show list selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Add to List:", list_options) # Localize this string

            if selected_index < 0:
                return False

            # Handle selection
            if selected_index == len(list_options) - 1:  # Create new list
                result = self.create_list(context)
                if not result.success:
                    return False
                # Get the newly created list ID and add item to it
                all_lists = query_manager.get_all_lists_with_folders() # Refresh lists
                available_lists = [lst for lst in all_lists if lst.get('folder_name') != 'Search History' and lst.get('name') != 'Kodi Favorites']
                if available_lists:
                    target_list_id = available_lists[-1]['id']  # Assume last created
                else:
                    return False
            else:
                target_list_id = available_lists[selected_index]['id']

            # Add item to selected list
            result = query_manager.add_item_to_list(target_list_id, media_item_id)

            if result is not None and result.get("success"):
                list_name = available_lists[selected_index]['name'] if selected_index < len(available_lists) else "new list"
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Added to '{list_name}'", # Localize this string
                    xbmcgui.NOTIFICATION_INFO
                )
                return True
            else:
                error_msg = result.get("error", "Unknown error") if result else "Query manager returned None"
                if error_msg == "duplicate":
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        "Item already in list", # Localize this string
                        xbmcgui.NOTIFICATION_WARNING
                    )
                else:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        f"Failed to add to list: {error_msg}", # Localize this string
                        xbmcgui.NOTIFICATION_ERROR
                    )
                return False

        except Exception as e:
            context.logger.error("Error adding to list: %s", e)
            return False

    def add_library_item_to_list_context(self, context: PluginContext) -> bool:
        """Handle adding library item to a list from context menu"""
        try:
            # Get library item parameters
            dbtype = context.get_param('dbtype')
            dbid = context.get_param('dbid')
            title = context.get_param('title', f'Item {dbid}')  # Extract title from context

            if not dbtype or not dbid:
                context.logger.error("Missing dbtype or dbid for library item")
                return False

            context.logger.info("Adding library item to list: dbtype=%s, dbid=%s, title='%s'", dbtype, dbid, title)

            query_manager = get_query_manager()
            if not query_manager.initialize():
                context.logger.error("Failed to initialize query manager for library item add")
                return False

            # Get all available lists, excluding special lists
            all_lists = query_manager.get_all_lists_with_folders()
            available_lists = [lst for lst in all_lists if lst.get('folder_name') != 'Search History' and lst.get('name') != 'Kodi Favorites']
            if not available_lists:
                # Offer to create a new list
                if xbmcgui.Dialog().yesno("No Lists Found", "No lists available. Create a new list?"): # Localize these strings
                    result = self.create_list(context)
                    if result.success:
                        all_lists = query_manager.get_all_lists_with_folders() # Refresh lists
                        available_lists = [lst for lst in all_lists if lst.get('folder_name') != 'Search History' and lst.get('name') != 'Kodi Favorites']
                    else:
                        return False
                else:
                    return False

            if not available_lists: # Still no lists after offering to create
                xbmcgui.Dialog().notification("LibraryGenie", "No lists available to add to.", xbmcgui.NOTIFICATION_WARNING) # Localize strings
                return False

            # Build list options for selection
            list_options = []
            for lst in available_lists:
                folder_name = lst.get('folder_name', 'Root')
                if folder_name == 'Root' or not folder_name:
                    list_options.append(lst['name'])
                else:
                    list_options.append(f"{folder_name}/{lst['name']}")

            # Add option to create new list
            list_options.append(f"+ {L(37018)}")

            # Show list selection dialog
            dialog = xbmcgui.Dialog()
            selected_index = dialog.select("Add to List:", list_options) # Localize this string

            if selected_index < 0:
                return False # User cancelled

            # Handle selection
            target_list_id = None
            if selected_index == len(list_options) - 1:  # Create new list
                result = self.create_list(context)
                if not result.success:
                    return False
                # Use the newly created list ID directly from the result
                target_list_id = result.data.get('id') if result.data else None
                if target_list_id is None:
                    context.logger.error("Failed to get new list ID from create_list result")
                    return False
                context.logger.debug("Using newly created list ID: %s", target_list_id)
            else:
                target_list_id = available_lists[selected_index]['id']

            if target_list_id is None:
                return False

            # Simple library item approach - just need minimal fields for existing Kodi items
            context.logger.debug("Adding library item to list: kodi_id=%s, title='%s', media_type=%s", 
                               dbid, title, dbtype)

            # Direct database operations for library items (much simpler than search pipeline)
            with query_manager.connection_manager.transaction() as conn:
                # Check if library item already exists in media_items
                existing_media_item = conn.execute("""
                    SELECT id FROM media_items 
                    WHERE kodi_id = ? AND media_type = ? AND source = 'lib'
                """, [int(dbid), dbtype]).fetchone()

                if existing_media_item:
                    media_item_id = existing_media_item['id']
                    context.logger.debug("Found existing library media_item: id=%s", media_item_id)
                else:
                    # Insert minimal library item record (no complex metadata needed)
                    cursor = conn.execute("""
                        INSERT INTO media_items (kodi_id, media_type, title, source, created_at)
                        VALUES (?, ?, ?, 'lib', datetime('now'))
                    """, [int(dbid), dbtype, title])
                    media_item_id = cursor.lastrowid
                    context.logger.debug("Created new library media_item: id=%s", media_item_id)

                # Check if already in target list
                existing_list_item = conn.execute("""
                    SELECT id FROM list_items WHERE list_id = ? AND media_item_id = ?
                """, [target_list_id, media_item_id]).fetchone()

                if existing_list_item:
                    context.logger.debug("Item already in list %s", target_list_id)
                    result = {"success": True, "already_exists": True}
                else:
                    # Add to list
                    conn.execute("""
                        INSERT INTO list_items (list_id, media_item_id, position)
                        VALUES (?, ?, COALESCE((SELECT MAX(position) + 1 FROM list_items WHERE list_id = ?), 0))
                    """, [target_list_id, media_item_id, target_list_id])
                    context.logger.debug("Added library item to list %s", target_list_id)
                    result = {"success": True}

            if result is not None and result.get("success"):
                # Determine the correct list name based on what actually happened
                if selected_index == len(list_options) - 1:  # Created new list
                    # Get the name of the newly created list
                    all_lists = query_manager.get_all_lists_with_folders()
                    available_lists_refreshed = [lst for lst in all_lists if lst.get('folder_name') != 'Search History' and lst.get('name') != 'Kodi Favorites']
                    if available_lists_refreshed and target_list_id:
                        # Find the list with the target_list_id
                        target_list = next((lst for lst in available_lists_refreshed if str(lst['id']) == str(target_list_id)), None)
                        list_name = target_list['name'] if target_list else "new list"
                    else:
                        list_name = "new list"
                else:
                    # Adding to existing list
                    list_name = available_lists[selected_index]['name'] if selected_index < len(available_lists) else "unknown list"
                
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    f"Added to '{list_name}'", # Localize this string
                    xbmcgui.NOTIFICATION_INFO
                )
                return True
            else:
                error_msg = result.get("error", "Unknown error") if result else "Query manager returned None"
                if error_msg == "duplicate":
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        "Item already in list", # Localize this string
                        xbmcgui.NOTIFICATION_WARNING
                    )
                else:
                    xbmcgui.Dialog().notification(
                        "LibraryGenie",
                        f"Failed to add to list: {error_msg}", # Localize this string
                        xbmcgui.NOTIFICATION_ERROR
                    )
                return False

        except Exception as e:
            context.logger.error("Error adding library item to list: %s", e)
            return False