"""Options and tools menu management for LibraryGenie addon"""

import time
import xbmc
import xbmcgui
from resources.lib.utils import utils
from resources.lib.kodi.url_builder import build_plugin_url

class OptionsManager:
    """Manages the Options & Tools menu and related functionality"""

    def __init__(self):
        # Base options that are always available
        self.base_options = [
            "Create New List",
            "Create New Folder",
            "Settings"
        ]

    def _build_options_list(self):
        """Build the options list dynamically based on current state"""
        options = []

        # Check if user is authenticated to show Search Movies
        if self._is_authenticated():
            options.append("Search Movies")

        # Check if there are search history entries to show Search History
        if self._has_search_history():
            options.append("Search History")

        # Add base options
        options.extend(self.base_options)

        return options

    def _is_authenticated(self):
        """Check if user is authenticated to the server"""
        try:
            from resources.lib.config.addon_ref import get_addon
            addon = get_addon()

            # Check if we have API configuration
            api_url = addon.getSetting('remote_api_url')
            api_key = addon.getSetting('remote_api_key')

            # Also check LGS settings as backup
            lgs_url = addon.getSetting('lgs_upload_url')
            lgs_key = addon.getSetting('lgs_upload_key')

            # User is authenticated if they have either remote API or LGS credentials
            has_remote_api = api_url and api_key
            has_lgs_auth = lgs_url and lgs_key

            return has_remote_api or has_lgs_auth

        except Exception as e:
            utils.log(f"Error checking authentication status: {str(e)}", "ERROR")
            return False

    def _has_search_history(self):
        """Check if there are any search history entries"""
        try:
            from resources.lib.config.config_manager import Config
            from resources.lib.data.database_manager import DatabaseManager

            config = Config()
            db_manager = DatabaseManager(config.db_path)

            # Get the Search History folder ID
            search_history_folder_id = db_manager.get_folder_id_by_name("Search History")

            if not search_history_folder_id:
                return False

            # Check if there are any lists in the Search History folder
            search_history_lists = db_manager.fetch_lists_by_folder(search_history_folder_id)

            return len(search_history_lists) > 0

        except Exception as e:
            utils.log(f"Error checking search history: {str(e)}", "ERROR")
            return False

    def show_options_menu(self, query_params):
        """Show the options and tools menu"""
        utils.log("=== OPTIONS DIALOG REQUEST START ===", "DEBUG")
        utils.log("Showing Options & Tools menu", "DEBUG")

        # Build dynamic options list
        self.options = self._build_options_list()
        utils.log(f"Available options: {self.options}", "DEBUG")

        # Initialize current_folder_id from query params
        current_folder_id = None
        if 'folder_id' in query_params:
            folder_id_param = query_params.get('folder_id', [None])
            if isinstance(folder_id_param, list) and folder_id_param:
                try:
                    current_folder_id = int(folder_id_param[0]) if folder_id_param[0] and folder_id_param[0].isdigit() else None
                except (ValueError, TypeError):
                    current_folder_id = None

        # Get current window information for debugging
        current_window_id = xbmc.getInfoLabel('System.CurrentWindow')
        utils.log(f"Current window ID before options: {current_window_id}", "DEBUG")
        utils.log(f"Current window ID: {current_window_id}", "DEBUG")

        # Check for navigation protection with automatic cleanup
        navigation_active = xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.Navigating)")
        if navigation_active == "true":
            # Check if navigation has been stuck for too long (more than 10 seconds)
            try:
                current_time = time.time()
                last_navigation = float(xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.LastNavigation)") or "0")
                time_since_nav = current_time - last_navigation

                if time_since_nav > 10.0:  # Clear stuck navigation flag after 10 seconds
                    utils.log(f"=== CLEARING STUCK NAVIGATION FLAG (stuck for {time_since_nav:.1f}s) ===", "WARNING")
                    xbmc.executebuiltin("ClearProperty(LibraryGenie.Navigating,Home)")
                    xbmc.executebuiltin("ClearProperty(LibraryGenie.SearchModalActive,Home)")
                else:
                    utils.log(f"=== OPTIONS BLOCKED: NAVIGATION IN PROGRESS ({time_since_nav:.1f}s) ===", "WARNING")
                    return
            except (ValueError, TypeError):
                # If we can't get timestamps, clear the flag anyway
                utils.log("=== CLEARING NAVIGATION FLAG (timestamp error) ===", "WARNING")
                xbmc.executebuiltin("ClearProperty(LibraryGenie.Navigating,Home)")
                xbmc.executebuiltin("ClearProperty(LibraryGenie.SearchModalActive,Home)")

        # Time-based protection to prevent re-triggering after navigation
        try:
            last_navigation = float(xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.LastNavigation)") or "0")
            current_time = time.time()
            time_since_nav = current_time - last_navigation

            if time_since_nav < 3.0:  # Increased back to 3 seconds for better stability
                utils.log(f"=== OPTIONS BLOCKED: TOO SOON AFTER NAVIGATION ({time_since_nav:.1f}s) ===", "WARNING")
                return
        except (ValueError, TypeError):
            pass  # If property doesn't exist or isn't a number, continue

        # Additional protection: check if we just completed a search
        try:
            search_modal_active = xbmc.getInfoLabel("Window(Home).Property(LibraryGenie.SearchModalActive)")
            if search_modal_active == "true":
                utils.log("=== OPTIONS BLOCKED: SEARCH MODAL STILL ACTIVE ===", "WARNING")
                return
        except:
            pass

        utils.log(f"Current window ID: {current_window_id}", "DEBUG")

        try:
            utils.log("=== ABOUT TO SHOW OPTIONS MODAL DIALOG ===", "DEBUG")
            utils.log(f"Pre-modal window state: {xbmcgui.getCurrentWindowId()}", "DEBUG")
            utils.log("=== CREATING xbmcgui.Dialog() INSTANCE ===", "DEBUG")

            # Use a timeout mechanism to prevent hanging
            dialog_start_time = time.time()
            dialog = xbmcgui.Dialog()
            utils.log("=== CALLING dialog.select() METHOD ===", "DEBUG")

            # Set a property to track dialog state
            xbmc.executebuiltin("SetProperty(LibraryGenie.DialogActive,true,Home)")

            selected_option = dialog.select("LibraryGenie - Options & Tools", self.options)

            # Clear dialog state property
            xbmc.executebuiltin("ClearProperty(LibraryGenie.DialogActive,Home)")

            dialog_duration = time.time() - dialog_start_time
            utils.log(f"=== OPTIONS MODAL DIALOG CLOSED, SELECTION: {selected_option}, DURATION: {dialog_duration:.1f}s ===", "DEBUG")
            utils.log(f"Post-modal window state: {xbmcgui.getCurrentWindowId()}", "DEBUG")

            # Check for timeout condition
            if dialog_duration > 4.0:  # If dialog took more than 4 seconds
                utils.log(f"=== WARNING: Dialog took {dialog_duration:.1f}s - near timeout threshold ===", "WARNING")

        except Exception as e:
            utils.log(f"=== ERROR IN OPTIONS DIALOG CREATION: {str(e)} ===", "ERROR")
            xbmc.executebuiltin("ClearProperty(LibraryGenie.DialogActive,Home)")
            return

        if selected_option == -1:
            utils.log("User cancelled options menu", "DEBUG")
            utils.log("=== OPTIONS DIALOG CANCELLED BY USER ===", "DEBUG")
            # Clear any lingering properties
            xbmc.executebuiltin("ClearProperty(LibraryGenie.DialogActive,Home)")
            return

        # Early validation
        if selected_option < 0 or selected_option >= len(self.options):
            utils.log(f"Invalid option selected: {selected_option}", "ERROR")
            xbmc.executebuiltin("ClearProperty(LibraryGenie.DialogActive,Home)")
            return

        selected_text = self.options[selected_option]
        utils.log(f"User selected option: {selected_text}", "DEBUG")
        utils.log(f"=== EXECUTING SELECTED OPTION: {selected_text} ===", "DEBUG")

        # Check remaining time budget
        execution_start_time = time.time()
        remaining_time = 4.0 - (execution_start_time - dialog_start_time)

        if remaining_time < 1.0:  # Less than 1 second left
            utils.log(f"=== INSUFFICIENT TIME REMAINING ({remaining_time:.1f}s) - DEFERRING EXECUTION ===", "WARNING")
            # Defer execution using RunScript to avoid timeout
            # Store folder context in a property for deferred execution
            folder_context_str = str(current_folder_id) if current_folder_id else "None"
            xbmc.executebuiltin(f"SetProperty(LibraryGenie.DeferredFolderContext,{folder_context_str},Home)")
            # Use the correct addon format for RunScript
            xbmc.executebuiltin(f"RunScript(plugin.video.librarygenie,deferred_option,{selected_option})")
            return

        # Minimal dialog cleanup before option execution
        utils.log("=== QUICK DIALOG CLEANUP BEFORE OPTION EXECUTION ===", "DEBUG")
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.sleep(50)
        utils.log("=== COMPLETED QUICK CLEANUP ===", "DEBUG")

        # Get current folder from params if available
        # This is a fallback if the property-based initialization didn't catch it or if it was reset
        if current_folder_id is None and 'folder_id' in query_params:
            folder_id_param = query_params.get('folder_id', [None])
            if isinstance(folder_id_param, list) and folder_id_param:
                try:
                    current_folder_id = int(folder_id_param[0]) if folder_id_param[0] and folder_id_param[0].isdigit() else None
                except (ValueError, TypeError):
                    current_folder_id = None

        self._execute_option(selected_option, selected_text, current_folder_id)

    def _execute_option(self, option_index, selected_text, current_folder_id=None):
        """Execute the selected option"""
        try:
            if "Search Movies" in selected_text:
                utils.log("=== EXECUTING: SEARCH MOVIES ===", "DEBUG")
                utils.log("=== ABOUT TO CALL run_search_flow() - MODAL WILL OPEN ===", "DEBUG")
                from main import run_search_flow
                run_search_flow()
                utils.log("=== COMPLETED: SEARCH MOVIES - ALL MODALS CLOSED ===", "DEBUG")
            elif "Search History" in selected_text:
                utils.log("=== EXECUTING: SEARCH HISTORY ===", "DEBUG")
                utils.log("=== ABOUT TO CALL browse_search_history() - MODAL WILL OPEN ===", "DEBUG")
                from main import browse_search_history
                browse_search_history()
                utils.log("=== COMPLETED: SEARCH HISTORY - ALL MODALS CLOSED ===", "DEBUG")
            elif "Create New List" in selected_text:
                utils.log("=== EXECUTING: CREATE NEW LIST ===", "DEBUG")
                utils.log("=== ABOUT TO CALL create_list() - MODAL WILL OPEN ===", "DEBUG")
                from resources.lib.core.route_handlers import create_list
                # Pass current folder context
                params = {'folder_id': [current_folder_id]} if current_folder_id else {}
                create_list(params)
                utils.log("=== COMPLETED: CREATE NEW LIST - ALL MODALS CLOSED ===", "DEBUG")
            elif "Create New Folder" in selected_text:
                utils.log("=== EXECUTING: CREATE NEW FOLDER ===", "DEBUG")
                utils.log("=== ABOUT TO CALL create_new_folder() - MODAL WILL OPEN ===", "DEBUG")
                from resources.lib.data.folder_list_manager import get_folder_list_manager
                folder_manager = get_folder_list_manager()
                folder_manager.create_new_folder(current_folder_id)
                utils.log("=== COMPLETED: CREATE NEW FOLDER - ALL MODALS CLOSED ===", "DEBUG")
            elif "Settings" in selected_text:
                utils.log("=== EXECUTING: OPEN SETTINGS ===", "DEBUG")
                utils.log("=== ABOUT TO OPEN SETTINGS WINDOW ===", "DEBUG")
                xbmc.executebuiltin("Addon.OpenSettings(plugin.video.librarygenie)")
                utils.log("=== COMPLETED: OPEN SETTINGS - SETTINGS WINDOW CLOSED ===", "DEBUG")
            else:
                utils.log(f"=== UNKNOWN OPTION SELECTED: {selected_text} ===", "WARNING")

        except Exception as e:
            utils.log(f"=== ERROR EXECUTING SELECTED OPTION: {str(e)} ===", "ERROR")
            import traceback
            utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")
        finally:
            # Note: Navigation flag is now handled in individual flows (like run_search_flow)
            utils.log("=== OPTIONS DIALOG REQUEST COMPLETE ===", "DEBUG")

    def execute_deferred_option(self, option_index, folder_context=None):
        """Execute an option that was deferred due to timeout concerns"""
        utils.log(f"=== EXECUTING DEFERRED OPTION {option_index} ===", "DEBUG")

        # Build the options list since this is a new instance
        self.options = self._build_options_list()
        utils.log(f"Built options list for deferred execution: {self.options}", "DEBUG")

        if option_index < 0 or option_index >= len(self.options):
            utils.log(f"Invalid deferred option index: {option_index}", "ERROR")
            return

        selected_text = self.options[option_index]
        utils.log(f"Executing deferred option: {selected_text}", "DEBUG")

        # Use provided folder context, or None for root
        self._execute_option(option_index, selected_text, folder_context)