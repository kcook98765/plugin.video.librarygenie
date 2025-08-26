#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Movie List Manager - Main Addon Controller (Reconstructed)
Handles routing, UI, and user interactions
Includes Phase 10 Import/Export & Backup functionality
"""

import xbmcaddon
import xbmcgui
import xbmcplugin

import urllib.parse
from typing import Dict, Any, Optional
from .config import get_config
from .data import QueryManager
from .ui import MenuBuilder
from .utils.logger import get_logger


class AddonController:
    """Main controller for addon routing and navigation"""

    def __init__(self, addon_handle, base_url):
        self.logger = get_logger(__name__)
        self.config = get_config()
        self.addon_handle = addon_handle
        self.base_url = base_url
        self.menu_builder = MenuBuilder(self._get_string)
        self.query_manager = QueryManager()

    def route(self, action, params):
        """Route requests to appropriate handlers"""
        self.logger.debug(f"Routing action: {action}, params: {params}")

        try:
            if action == "root" or action == "":
                self._show_root_menu()
            elif action == "my_lists":
                self._show_my_lists()
            elif action == "view_list":
                list_id = params.get("list_id")
                if list_id:
                    self._show_list_detail(list_id)
                else:
                    self._show_my_lists()
            elif action == "create_list":
                self._create_list_dialog()
            elif action == "browse_library":
                self._show_browse_library()
            elif action == "search":
                from .ui.search_handler import get_search_handler
                search_handler = get_search_handler()
                search_handler.show_search_dialog()
            elif action == "search_results":
                from .ui.search_handler import get_search_handler
                search_handler = get_search_handler()
                query_params = {k: v for k, v in params.items() if k != 'action'}
                search_handler.show_search_results(query_params)
            elif action == "import_export":
                self._show_import_export_menu()
            elif action == "export_data":
                export_types = params.get("export_types", "lists,list_items").split(",")
                file_format = params.get("file_format", "json")
                custom_path = params.get("custom_path")
                self._handle_export_data(export_types, file_format, custom_path)
            elif action == "import_data":
                file_path = params.get("file_path")
                self._handle_import_data(file_path)
            elif action == "manage_backups":
                self._show_backup_management()
            elif action == "settings":
                self._open_settings()
            # Phase 11: Playback actions
            elif action in ["play_movie", "resume_movie", "queue_movie", "show_info"]:
                kodi_id = params.get("kodi_id")
                if kodi_id:
                    self._handle_playback_action(action, kodi_id)
                else:
                    self.logger.error(f"Missing kodi_id for playback action: {action}")
            # Phase 2: Settings actions
            elif action == "set_default_list":
                self._handle_set_default_list()
            # Phase 12: Remote integration actions
            elif action == "remote_lists":
                self._show_remote_lists()
            elif action == "view_remote_list":
                list_id = params.get("list_id")
                if list_id:
                    self._show_remote_list_contents(list_id)
                else:
                    self._show_remote_lists()
            elif action == "test_remote_connection":
                self._test_remote_connection()
            elif action == "clear_remote_cache":
                self._clear_remote_cache()
            elif action == "remote_search":
                query = params.get("query", "")
                self._show_remote_search_results(query)
            else:
                self.logger.warning(f"Unknown action: {action}")
                self._show_root_menu()
        except Exception as e:
            self.logger.error(f"Error routing action {action}: {e}")
            self._show_error_dialog("An error occurred while processing your request")

    def _show_root_menu(self):
        """Show the main addon menu"""
        self.logger.debug("Showing root menu")

        items = [
            {
                "title": self._get_string(31200),  # "My Lists"
                "action": "my_lists",
                "description": "View and manage your custom lists",
                "is_folder": True
            },
            {
                "title": self._get_string(30700),  # "Browse Library"
                "action": "browse_library",
                "description": "Browse your indexed movie library",
                "is_folder": True
            },
            {
                "title": self._get_string(33000),  # "Search"
                "description": self._get_string(33001),  # "Search Movies and Lists"
                "action": "search",
                "is_folder": False
            },
            {
                "title": self._get_string(34000),  # "Import/Export & Backups"
                "description": self._get_string(34001),  # "Export, import, and backup data"
                "action": "import_export",
                "is_folder": True
            },
            {
                "title": self._get_string(30201),  # "Settings"
                "action": "settings",
                "description": "Configure addon settings",
                "is_folder": False
            }
        ]
        
        # Phase 12: Add remote lists if enabled
        try:
            from .remote.service import get_remote_service
            remote_service = get_remote_service()
            if remote_service.is_enabled():
                items.insert(-1, {  # Insert before Settings
                    "title": self._get_string(35030),  # "Remote Lists"
                    "action": "remote_lists", 
                    "description": "Browse lists from remote services",
                    "is_folder": True
                })
        except Exception as e:
            self.logger.debug(f"Remote service not available: {e}")

        self.menu_builder.build_menu(items, self.addon_handle, self.base_url)

    def _show_my_lists(self):
        """Show user's custom lists"""
        self.logger.debug("Showing my lists")
        
        try:
            self.query_manager.initialize()
            user_lists = self.query_manager.get_user_lists()

            items = [{
                "title": self._get_string(30400),  # "New List"
                "description": "Create a new list",
                "action": "create_list",
                "is_folder": False
            }]
            
            show_counts = self.config.get("show_item_counts", True)
            
            for list_data in user_lists:
                title = list_data.get("name", "Unknown List")
                if show_counts and list_data.get("item_count", 0) > 0:
                    title += f" ({list_data['item_count']})"
                
                items.append({
                    "title": title,
                    "description": list_data.get("description", ""),
                    "action": "view_list",
                    "list_id": list_data.get("id", ""),
                    "is_folder": True
                })

            if len(items) == 1:  # Only the "New List" option
                items.append({
                    "title": "No lists yet",
                    "description": "Use 'New List' above to create your first list",
                    "action": "",
                    "is_folder": False
                })

            self.menu_builder.build_menu(items, self.addon_handle, self.base_url)

        except Exception as e:
            self.logger.error(f"Error loading user lists: {e}")
            self._show_error_dialog("Failed to load lists")

    def _show_list_detail(self, list_id):
        """Show items in a specific list"""
        self.logger.info(f"Showing list detail for {list_id} (basic implementation)")
        items = [{"title": f"List {list_id} items", "action": "", "is_folder": False}]
        self.menu_builder.build_menu(items, self.addon_handle, self.base_url)

    def _create_list_dialog(self):
        """Show dialog to create a new list"""
        self.logger.info("Create list dialog (basic implementation)")
        if KODI_AVAILABLE:
            dialog = xbmcgui.Dialog()
            name = dialog.input("Enter list name")
            if name:
                self.logger.info(f"Creating list: {name}")
        self._show_my_lists()

    def _show_browse_library(self):
        """Show library browser"""
        self.logger.info("Browse library (basic implementation)")
        items = [{"title": "Library movies", "action": "", "is_folder": False}]
        self.menu_builder.build_menu(items, self.addon_handle, self.base_url)

    def _show_search_dialog(self):
        """Show search interface"""
        self.logger.info("Search dialog (basic implementation)")
        if KODI_AVAILABLE:
            dialog = xbmcgui.Dialog()
            query = dialog.input("Enter search terms")
            if query:
                self.route("search_results", {"query": query})
        else:
            self.route("search_results", {"query": "test search"})

    def _show_search_results(self, query_params):
        """Show search results"""
        self.logger.info(f"Search results (basic implementation): {query_params}")
        items = [{"title": "Search results", "action": "", "is_folder": False}]
        self.menu_builder.build_menu(items, self.addon_handle, self.base_url)

    # Phase 10 Import/Export UI Handlers
    
    def _show_import_export_menu(self):
        """Show import/export main menu"""
        self.logger.debug("Showing import/export menu")
        
        items = [
            {
                "title": self._get_string(34002),  # "Export Data"
                "description": "Export lists and data to files",
                "action": "export_data",
                "export_types": "lists,list_items",
                "file_format": "json",
                "is_folder": False
            },
            {
                "title": self._get_string(34003),  # "Import Data" 
                "description": "Import data from backup files",
                "action": "import_data",
                "is_folder": False
            },
            {
                "title": self._get_string(34004),  # "Manage Backups"
                "description": "View and manage automatic backups", 
                "action": "manage_backups",
                "is_folder": True
            }
        ]
        
        self.menu_builder.build_menu(items, self.addon_handle, self.base_url)
    
    def _handle_export_data(self, export_types, file_format, custom_path=None):
        """Handle data export operation"""
        self.logger.info(f"Starting export: {export_types}, format: {file_format}")
        
        try:
            from .import_export import get_export_engine
            export_engine = get_export_engine()
            
            if isinstance(export_types, str):
                export_types = [t.strip() for t in export_types.split(",")]
            
            result = export_engine.export_data(
                export_types=export_types,
                file_format=file_format,
                custom_path=custom_path
            )
            
            if result["success"]:
                message = (f"{self._get_string(34011)}!\n"  # "Export Successful"
                          f"File: {result['filename']}\n"
                          f"Items: {result['total_items']}")
                
                if KODI_AVAILABLE:
                    xbmcgui.Dialog().ok(self._get_string(35003), message)
                else:
                    self.logger.info(f"Export success: {message}")
                    
                self._show_import_export_menu()
            else:
                error_msg = result.get("error", "Unknown error")
                self.logger.error(f"Export failed: {error_msg}")
                self._show_error_dialog(f"{self._get_string(34014)}: {error_msg}")
                
        except Exception as e:
            self.logger.error(f"Error in export operation: {e}")
            self._show_error_dialog(f"{self._get_string(34014)}: {str(e)}")
    
    def _handle_import_data(self, file_path=None):
        """Handle data import operation"""
        self.logger.info("Starting import operation")
        
        try:
            from .import_export import get_import_engine
            import_engine = get_import_engine()
            
            if not file_path:
                if KODI_AVAILABLE:
                    dialog = xbmcgui.Dialog()
                    file_path = dialog.browse(1, self._get_string(34008), 'files', '.json|.csv')
                    
                    if not file_path:
                        self._show_import_export_menu()
                        return
                else:
                    self.logger.info("Import file dialog (stub mode)")
                    self._show_import_export_menu()
                    return
            
            # Validate and import
            validation = import_engine.validate_import_file(file_path)
            if not validation["valid"]:
                error_msg = ", ".join(validation["errors"])
                self._show_error_dialog(f"{self._get_string(34016)}: {error_msg}")
                return
            
            # Show preview
            preview = import_engine.preview_import(file_path)
            preview_msg = (f"{self._get_string(34017)}:\n"
                          f"{self._get_string(34019)}: {len(preview.lists_to_create)}\n"
                          f"{self._get_string(34020)}: {preview.items_to_add}")
            
            if KODI_AVAILABLE:
                if not xbmcgui.Dialog().yesno(self._get_string(34018), preview_msg):
                    self._show_import_export_menu()
                    return
            else:
                self.logger.info(f"Import preview: {preview_msg}")
            
            # Perform import
            result = import_engine.import_data(file_path)
            
            if result.success:
                success_msg = (f"{self._get_string(34012)}!\n"
                              f"Lists created: {result.lists_created}\n"
                              f"Items added: {result.items_added}")
                
                if KODI_AVAILABLE:
                    xbmcgui.Dialog().ok("Import Complete", success_msg)
                else:
                    self.logger.info(f"Import success: {success_msg}")
            else:
                error_msg = ", ".join(result.errors) if result.errors else "Unknown error"
                self._show_error_dialog(f"{self._get_string(34014)}: {error_msg}")
                
            self._show_import_export_menu()
                
        except Exception as e:
            self.logger.error(f"Error in import operation: {e}")
            self._show_error_dialog(f"{self._get_string(34014)}: {str(e)}")
    
    def _show_backup_management(self):
        """Show backup management interface"""
        self.logger.debug("Showing backup management")
        
        try:
            from .import_export import get_backup_manager
            backup_manager = get_backup_manager()
            
            settings = backup_manager.get_backup_settings()
            backups = backup_manager.list_backups()
            
            items = []
            
            backup_status = "Enabled" if settings["enabled"] else "Disabled" 
            items.append({
                "title": f"{self._get_string(34022)}: {backup_status}",  # "Auto Backup"
                "description": f"Interval: {settings['interval']}, Keep: {settings['retention_count']}",
                "action": "settings",
                "is_folder": False
            })
            
            items.append({
                "title": "Create Backup Now",
                "description": "Create immediate backup",
                "action": "export_data",
                "export_types": "lists,list_items,favorites",
                "file_format": "json",
                "is_folder": False
            })
            
            for backup in backups[:10]:
                age_text = f"{backup['age_days']} days ago"
                size_kb = backup['file_size'] // 1024
                
                items.append({
                    "title": f"Backup: {backup['backup_time'].strftime('%Y-%m-%d %H:%M')}",
                    "description": f"{backup['export_type']} - {size_kb}KB - {age_text}",
                    "action": "import_data",
                    "file_path": backup["file_path"],
                    "is_folder": False
                })
            
            if not backups:
                items.append({
                    "title": "No backups found",
                    "description": "Create your first backup above",
                    "action": "",
                    "is_folder": False
                })
            
            self.menu_builder.build_menu(items, self.addon_handle, self.base_url)
            
        except Exception as e:
            self.logger.error(f"Error showing backup management: {e}")
            self._show_error_dialog("Failed to load backup management")

    # Phase 11: Playback action handlers
    
    def _handle_playback_action(self, action: str, kodi_id: str):
        """Handle playback actions from context menus"""
        try:
            from .ui.playback_actions import get_context_menu_handler
            handler = get_context_menu_handler(self.base_url, self._get_string)
            
            success = handler.handle_playback_action(action, kodi_id)
            if not success:
                self._show_error_dialog(f"Playback action failed: {action}")
                
        except Exception as e:
            self.logger.error(f"Error handling playback action {action}: {e}")
            self._show_error_dialog(f"Playback error: {str(e)}")
    
    def _show_library_with_artwork(self, **options):
        """Show library browser with Phase 11 enhanced ListItems"""
        try:
            from .library.scanner import LibraryScanner
            scanner = LibraryScanner()
            
            # Get movies with full metadata 
            movies = scanner.get_indexed_movies(include_removed=False, limit=100, offset=0)
            
            if not movies:
                items = [{"title": "No movies found", "description": "Library may not be indexed yet", "action": "", "is_folder": False}]
                self.menu_builder.build_menu(items, self.addon_handle, self.base_url)
                return
            
            # Use the enhanced movie menu builder
            self.menu_builder.build_movie_menu(
                movies, 
                self.addon_handle, 
                self.base_url,
                category="Movie Library",
                default_action="play_movie"
            )
            
        except Exception as e:
            self.logger.error(f"Error showing enhanced library: {e}")
            self._show_error_dialog("Failed to load library")
    
    def _show_list_with_artwork(self, list_id: str):
        """Show list contents with Phase 11 enhanced ListItems"""
        try:
            self.query_manager.initialize()
            
            # Get list movies with full metadata
            movies = self.query_manager.get_list_movies_with_metadata(list_id)
            
            if not movies:
                items = [{"title": "List is empty", "description": "Add some movies to this list", "action": "", "is_folder": False}]
                self.menu_builder.build_menu(items, self.addon_handle, self.base_url)
                return
            
            # Use the enhanced movie menu builder
            self.menu_builder.build_movie_menu(
                movies,
                self.addon_handle,
                self.base_url,
                category=f"List: {list_id}",
                default_action="play_movie"
            )
            
        except Exception as e:
            self.logger.error(f"Error showing enhanced list {list_id}: {e}")
            self._show_error_dialog("Failed to load list")

    # Phase 12: Remote integration handlers
    
    def _show_remote_lists(self):
        """Show available remote lists"""
        try:
            from .remote.service import get_remote_service
            remote_service = get_remote_service()
            
            if not remote_service.is_enabled():
                self._show_error_dialog("Remote integration is disabled")
                return
            
            if not remote_service.is_configured():
                self._show_error_dialog("Remote service not configured. Please check settings.")
                return
            
            # Get remote lists
            lists, used_remote = remote_service.get_remote_lists()
            
            if not used_remote:
                self._show_error_dialog("Failed to connect to remote service")
                return
            
            if not lists:
                items = [
                    {"title": "No remote lists available", "description": "", "action": "", "is_folder": False},
                    {"title": "Test Connection", "description": "Test remote service connection", "action": "test_remote_connection", "is_folder": False}
                ]
            else:
                items = []
                for remote_list in lists:
                    items.append({
                        "title": remote_list.get('name', 'Unnamed List'),
                        "description": f"{remote_list.get('item_count', 0)} items - {remote_list.get('description', '')}",
                        "action": "view_remote_list",
                        "list_id": remote_list.get('id'),
                        "is_folder": True
                    })
                
                # Add utility options
                items.extend([
                    {"title": "─────────────────", "description": "", "action": "", "is_folder": False},
                    {"title": "Test Connection", "description": "Test remote service connection", "action": "test_remote_connection", "is_folder": False},
                    {"title": "Clear Cache", "description": "Clear remote data cache", "action": "clear_remote_cache", "is_folder": False}
                ])
            
            self.menu_builder.build_menu(items, self.addon_handle, self.base_url)
            
        except Exception as e:
            self.logger.error(f"Error showing remote lists: {e}")
            self._show_error_dialog("Failed to load remote lists")
    
    def _show_remote_list_contents(self, list_id: str):
        """Show contents of a remote list"""
        try:
            from .remote.service import get_remote_service
            remote_service = get_remote_service()
            
            # Get list contents
            items, used_remote = remote_service.get_list_contents(list_id)
            
            if not used_remote:
                self._show_error_dialog("Failed to load remote list contents")
                return
            
            if not items:
                menu_items = [{"title": "List is empty", "description": "", "action": "", "is_folder": False}]
                self.menu_builder.build_menu(menu_items, self.addon_handle, self.base_url)
                return
            
            # Use enhanced movie menu for mapped items
            mapped_items = [item for item in items if item.get('_mapped', False)]
            unmapped_items = [item for item in items if not item.get('_mapped', False)]
            
            if mapped_items:
                # Show mapped items with enhanced display
                self.menu_builder.build_movie_menu(
                    mapped_items,
                    self.addon_handle,
                    self.base_url,
                    category=f"Remote List: {list_id}",
                    default_action="play_movie"
                )
            else:
                # Show basic menu for unmapped items
                menu_items = []
                for item in unmapped_items:
                    menu_items.append({
                        "title": f"{item.get('title', 'Unknown')} ({item.get('year', 'N/A')})",
                        "description": f"Not in library - {item.get('plot', '')}",
                        "action": "",
                        "is_folder": False
                    })
                
                self.menu_builder.build_menu(menu_items, self.addon_handle, self.base_url)
            
        except Exception as e:
            self.logger.error(f"Error showing remote list {list_id}: {e}")
            self._show_error_dialog("Failed to load remote list")
    
    def _test_remote_connection(self):
        """Test connection to remote service"""
        try:
            from .remote.service import get_remote_service
            remote_service = get_remote_service()
            
            result = remote_service.test_connection()
            
            if KODI_AVAILABLE:
                dialog = xbmcgui.Dialog()
                if result.get('success'):
                    message = f"Connection successful!\n\nResponse time: {result.get('response_time_ms', 0)}ms"
                    service_info = result.get('service_info', {})
                    if service_info:
                        message += f"\nService: {service_info.get('name', 'Unknown')}"
                        if service_info.get('version'):
                            message += f" v{service_info['version']}"
                    
                    dialog.ok(self._get_string(35005), message)
                else:
                    message = f"Connection failed!\n\n{result.get('message', 'Unknown error')}"
                    action = result.get('action')
                    if action == 'enable_remote':
                        message += "\n\nPlease enable remote integration in settings."
                    elif action == 'configure_remote':
                        message += "\n\nPlease configure URL and API key in settings."
                    
                    dialog.ok(self._get_string(35005), message)
            else:
                self.logger.info(f"Connection test result: {result}")
                
        except Exception as e:
            self.logger.error(f"Error testing remote connection: {e}")
            if KODI_AVAILABLE:
                xbmcgui.Dialog().ok(self._get_string(35006), f"Test failed with error:\n{str(e)}")
    
    def _clear_remote_cache(self):
        """Clear remote cache data"""
        try:
            from .remote.service import get_remote_service
            remote_service = get_remote_service()
            
            success = remote_service.clear_cache()
            
            if KODI_AVAILABLE:
                dialog = xbmcgui.Dialog()
                if success:
                    dialog.ok(self._get_string(35007), self._get_string(35011))
                else:
                    dialog.ok(self._get_string(35008), self._get_string(35012))
            else:
                self.logger.info(f"Cache clear result: {success}")
                
        except Exception as e:
            self.logger.error(f"Error clearing remote cache: {e}")
            if KODI_AVAILABLE:
                xbmcgui.Dialog().ok(self._get_string(35009), f"Failed to clear cache:\n{str(e)}")
    
    def _show_remote_search_results(self, query: str):
        """Show search results including remote results"""
        try:
            from .remote.service import get_remote_service
            remote_service = get_remote_service()
            
            # Get remote search results
            remote_results, used_remote = remote_service.search_movies(query)
            
            if used_remote and remote_results:
                # Show enhanced movie menu with remote results
                self.menu_builder.build_movie_menu(
                    remote_results,
                    self.addon_handle,
                    self.base_url,
                    category=f"Remote Search: {query}",
                    default_action="play_movie"
                )
            else:
                # Fall back to local search
                self._show_search_results({"query": query})
                
        except Exception as e:
            self.logger.error(f"Error showing remote search results: {e}")
            # Fall back to local search
            self._show_search_results({"query": query})

    # Phase 2: Settings action handlers
    
    def _handle_set_default_list(self):
        """Handle set default list action from settings"""
        try:
            lists = self.query_manager.get_user_lists()
            
            if not lists:
                # No lists available
                if KODI_AVAILABLE:
                    xbmcgui.Dialog().ok(
                        self._get_string(30074),  # "Default List Configuration"
                        self._get_string(30071)   # "No lists found. Create a list first."
                    )
                else:
                    self.logger.info("No lists found for default selection")
                return
            
            # Prepare list picker options
            list_names = []
            list_ids = []
            
            for user_list in lists:
                list_names.append(user_list.get('name', 'Unnamed List'))
                list_ids.append(str(user_list.get('id')))
            
            # Show list picker
            if KODI_AVAILABLE:
                dialog = xbmcgui.Dialog()
                selected_index = dialog.select(
                    self._get_string(30073),  # "Please select a default list:"
                    list_names
                )
                
                if selected_index >= 0:
                    # Valid selection made
                    selected_list_id = list_ids[selected_index]
                    selected_list_name = list_names[selected_index]
                    
                    # Save the selection
                    from .config import get_config
                    config = get_config()
                    success = config.set_default_list_id(selected_list_id)
                    
                    if success:
                        # Show confirmation
                        confirmation_msg = self._get_string(30070) % selected_list_name  # "Default list set to: %s"
                        dialog.ok(
                            self._get_string(30074),  # "Default List Configuration"
                            confirmation_msg
                        )
                        self.logger.info(f"Default list set to: {selected_list_name} (ID: {selected_list_id})")
                    else:
                        # Error saving
                        dialog.ok(
                            self._get_string(30074),  # "Default List Configuration"
                            self._get_string(30075)   # "Invalid list selection"
                        )
                        self.logger.error(f"Failed to save default list ID: {selected_list_id}")
                else:
                    # User cancelled
                    self.logger.debug("User cancelled default list selection")
            else:
                # Testing mode - select first list
                if list_ids:
                    selected_list_id = list_ids[0]
                    selected_list_name = list_names[0]
                    
                    from .config import get_config
                    config = get_config()
                    config.set_default_list_id(selected_list_id)
                    self.logger.info(f"Default list set to: {selected_list_name} (testing mode)")
                    
        except Exception as e:
            self.logger.error(f"Error handling set default list: {e}")
            if KODI_AVAILABLE:
                xbmcgui.Dialog().ok(
                    self._get_string(30074),  # "Default List Configuration"
                    f"Error: {str(e)}"
                )

    def _open_settings(self):
        """Open addon settings"""
        addon = xbmcaddon.Addon()
        addon.openSettings()

    def _show_error_dialog(self, message):
        """Show error dialog to user"""
        xbmcgui.Dialog().ok(self._get_string(35002), message)

    def _get_string(self, string_id):
        """Get localized string by ID"""
        try:
            addon = xbmcaddon.Addon()
            return addon.getLocalizedString(string_id)
            except:
                pass

        # Fallback strings for testing
        fallback_strings = {
            30200: "My Lists",
            30201: "Settings", 
            30400: "New List",
            30700: "Browse Library",
            33000: "Search",
            33001: "Search Movies and Lists",
            # Phase 10: Import/Export & Backups
            34000: "Import/Export & Backups",
            34001: "Export, import, and backup data",
            34002: "Export Data",
            34003: "Import Data", 
            34004: "Manage Backups",
            34008: "Choose file to import",
            34011: "Export Successful",
            34012: "Import Successful",
            34014: "Operation Failed",
            34016: "Invalid file format",
            34017: "Preview Changes",
            34018: "Confirm Import",
            34019: "Lists to create",
            34020: "Items to add",
            34022: "Auto Backup",
            # Phase 2: Settings UX strings
            30041: "Set default list…",
            30070: "Default list set to: %s",
            30071: "No lists found. Create a list first.",
            30072: "Background interval (minutes)",
            30073: "Please select a default list:",
            30074: "Default List Configuration",
            30075: "Invalid list selection",
            # Phase 12: Remote integration strings
            35030: "Remote Lists",
            35031: "Remote Integration",
            35032: "Enable Remote Features",
            35033: "Remote Service URL",
            35034: "API Key",
            35035: "Connection Timeout",
            35036: "Test Connection",
            35037: "Clear Remote Cache",
            35038: "Show Non-Library Items",
            35039: "Cache Remote Results",
            35040: "Remote Search",
            35041: "Connection successful",
            35042: "Connection failed",
            35043: "Remote service not configured",
            35044: "Remote integration disabled",
            35045: "Not in library",
        }
        return fallback_strings.get(string_id, f"String {string_id}")