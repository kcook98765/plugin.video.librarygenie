import json
import os
import sys
from lib.utils.kodi_log import get_kodi_logger

# Import localization function
from lib.ui.localization import L

# Set up logging
log = get_kodi_logger('lib.ui.context_menu_handler')

# Define the default plugin name
DEFAULT_PLUGIN_NAME = "Library Genie"


class ContextItem:
    """Represents an item within a context menu."""

    def __init__(self, context_info, item_info, settings, ai_client, plugin_manager):
        self.settings = settings
        self.ai_client = ai_client
        self.plugin_manager = plugin_manager
        self.context_info = context_info
        self.item_info = item_info

    def _get_quick_add_action(self, context_info):
        """Determines the action for Quick Add based on context."""
        if context_info.get("source") == "search_results":
            return "add_to_default_list_from_search"
        elif context_info.get("source") == "lib":
            return "add_to_default_list_from_library"
        else:
            return "add_to_default_list"

    def _get_quick_add_params(self, context_info, item_info):
        """Generates parameters for the Quick Add action."""
        params = {
            "item_id": item_info.get("id"),
            "item_title": item_info.get("title", ""),
            "item_year": item_info.get("year", ""),
            "item_type": item_info.get("type", ""),
            "source": context_info.get("source"),
            "plugin_name": DEFAULT_PLUGIN_NAME,
        }
        return params

    def _should_show_quick_add(self, context_info):
        """Checks if the Quick Add option should be displayed."""
        return (
            self.settings
            and self.settings.get_quick_add_to_default_list_enabled()
            and context_info.get("source") in ["search_results", "lib"]
        )

    def get_context_menu(self):
        """Generates the context menu items for the given item."""
        menu_items = []
        item_info = self.item_info
        context_info = self.context_info
        is_librarygenie_context = context_info.get("plugin_name") == DEFAULT_PLUGIN_NAME

        # Check AI search availability for potential AI-specific options
        ai_search_available = (
            self.settings and
            self.settings.get_ai_search_activated() and
            self.ai_client and
            self.ai_client.is_activated()
        )

        # Check if item has IMDb ID for Similar Movies option
        imdb_id = item_info.get('imdbnumber', '').strip()
        has_imdb_id = imdb_id and imdb_id.startswith('tt')

        # Add custom plugin actions
        if is_librarygenie_context:
            custom_actions = self.plugin_manager.get_custom_actions(item_info.get("id"))
            for action_name, action_details in custom_actions.items():
                menu_items.append({
                    'label': action_details.get('label', action_name.replace('_', ' ').title()),
                    'action': action_name,
                    'params': action_details.get('params', {})
                })

        # Add AI Search option if available
        if ai_search_available:
            menu_items.append({
                'label': f"🤖 {L(94100)}",  # AI Movie Search
                'action': 'ai_search',
                'params': {
                    'query': f"Search for '{item_info.get('title', 'Unknown')}' ({item_info.get('year', '')})",
                    'source_item_id': item_info.get('id'),
                    'is_plugin_context': is_librarygenie_context
                }
            })

        # Add Similar Movies option if AI search is available and item has IMDb ID
        if ai_search_available and has_imdb_id:
            menu_items.append({
                'label': f"🎬 {L(94106)}",  # Similar Movies
                'action': 'find_similar_movies',
                'params': {
                    'imdb_id': imdb_id,
                    'title': item_info.get('title', 'Unknown'),
                    'year': item_info.get('year', ''),
                    'is_plugin_context': is_librarygenie_context
                }
            })

        # Add Quick Add option if enabled
        if self._should_show_quick_add(context_info):
            menu_items.append({
                'label': f"⚡ {L(91001)}",  # Quick Add to Default List
                'action': self._get_quick_add_action(context_info),
                'params': self._get_quick_add_params(context_info, item_info)
            })

        # Add a separator if there are any items
        if menu_items:
            menu_items.append({})  # Add a separator

        # Add standard actions like "View Details"
        menu_items.append({
            'label': L(91000),  # View Details
            'action': 'view_details',
            'params': {
                'item_id': item_info.get('id'),
                'source': context_info.get('source'),
                'plugin_name': DEFAULT_PLUGIN_NAME
            }
        })

        return menu_items
