import json
import os
import sys
import logging

# Set up logging
log = logging.getLogger(__name__)

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
        elif context_info.get("source") == "library":
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
            and context_info.get("source") in ["search_results", "library"]
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
                'label': f"🤖 AI Search",
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
                'label': f"🎬 {L(34201)}",  # Similar Movies
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
                'label': f"⚡ {L(31001)}",  # Quick Add to Default List
                'action': self._get_quick_add_action(context_info),
                'params': self._get_quick_add_params(context_info, item_info)
            })

        # Add a separator if there are any items
        if menu_items:
            menu_items.append({})  # Add a separator

        # Add standard actions like "View Details"
        menu_items.append({
            'label': L(31000),  # View Details
            'action': 'view_details',
            'params': {
                'item_id': item_info.get('id'),
                'source': context_info.get('source'),
                'plugin_name': DEFAULT_PLUGIN_NAME
            }
        })

        return menu_items

# Mock function and class for demonstration purposes
# In a real scenario, these would be provided by the framework or other modules.
class MockSettings:
    def __init__(self):
        self._ai_search_activated = True
        self._quick_add_enabled = True

    def get_ai_search_activated(self):
        return self._ai_search_activated

    def get_quick_add_to_default_list_enabled(self):
        return self._quick_add_enabled

class MockAIClient:
    def __init__(self):
        self._activated = True

    def is_activated(self):
        return self._activated

    def search(self, query):
        log.info(f"AI Client searching for: {query}")
        # Mock search results
        return [{"title": f"AI Result for {query}", "type": "movie", "year": 2023, "imdbnumber": "tt1234567"}]

    def find_similar_movies(self, imdb_id):
        log.info(f"AI Client finding similar movies for: {imdb_id}")
        # Mock similar movies results
        return [{"title": f"Similar to {imdb_id}", "type": "movie", "year": 2022, "imdbnumber": "tt7654321"}]


class MockPluginManager:
    def __init__(self):
        self._custom_actions = {}

    def register_custom_action(self, item_id, action_name, action_details):
        if item_id not in self._custom_actions:
            self._custom_actions[item_id] = {}
        self._custom_actions[item_id][action_name] = action_details

    def get_custom_actions(self, item_id):
        return self._custom_actions.get(item_id, {})

# Import proper localization function
from lib.ui.localization import L

# Example Usage:
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    mock_settings = MockSettings()
    mock_ai_client = MockAIClient()
    mock_plugin_manager = MockPluginManager()

    # Example item with IMDb ID
    item_with_imdb = {
        "id": "movie1",
        "title": "Inception",
        "year": 2010,
        "type": "movie",
        "imdbnumber": "tt1375666"
    }

    # Example item without IMDb ID
    item_without_imdb = {
        "id": "movie2",
        "title": "The Matrix",
        "year": 1999,
        "type": "movie",
        "imdbnumber": ""
    }

    # Example context for search results
    search_context = {"source": "search_results", "plugin_name": DEFAULT_PLUGIN_NAME}

    # Example context for library
    library_context = {"source": "library", "plugin_name": DEFAULT_PLUGIN_NAME}

    # Example context from another plugin
    other_plugin_context = {"source": "some_other_source", "plugin_name": "Other Plugin"}

    # --- Test Case 1: Item with IMDb ID in search results context ---
    log.info("--- Test Case 1: Item with IMDb ID in search results ---")
    context_item_1 = ContextItem(search_context, item_with_imdb, mock_settings, mock_ai_client, mock_plugin_manager)
    menu_1 = context_item_1.get_context_menu()
    log.info(f"Menu 1: {json.dumps(menu_1, indent=2)}")

    # --- Test Case 2: Item without IMDb ID in library context ---
    log.info("\n--- Test Case 2: Item without IMDb ID in library ---")
    context_item_2 = ContextItem(library_context, item_without_imdb, mock_settings, mock_ai_client, mock_plugin_manager)
    menu_2 = context_item_2.get_context_menu()
    log.info(f"Menu 2: {json.dumps(menu_2, indent=2)}")

    # --- Test Case 3: Item with IMDb ID in other plugin context ---
    log.info("\n--- Test Case 3: Item with IMDb ID in other plugin context ---")
    context_item_3 = ContextItem(other_plugin_context, item_with_imdb, mock_settings, mock_ai_client, mock_plugin_manager)
    menu_3 = context_item_3.get_context_menu()
    log.info(f"Menu 3: {json.dumps(menu_3, indent=2)}")

    # --- Test Case 4: AI Search Disabled ---
    log.info("\n--- Test Case 4: AI Search Disabled ---")
    mock_settings._ai_search_activated = False
    context_item_4 = ContextItem(search_context, item_with_imdb, mock_settings, mock_ai_client, mock_plugin_manager)
    menu_4 = context_item_4.get_context_menu()
    log.info(f"Menu 4: {json.dumps(menu_4, indent=2)}")
    mock_settings._ai_search_activated = True # Reset for subsequent tests

    # --- Test Case 5: AI Client not activated ---
    log.info("\n--- Test Case 5: AI Client not activated ---")
    mock_ai_client._activated = False
    context_item_5 = ContextItem(search_context, item_with_imdb, mock_settings, mock_ai_client, mock_plugin_manager)
    menu_5 = context_item_5.get_context_menu()
    log.info(f"Menu 5: {json.dumps(menu_5, indent=2)}")
    mock_ai_client._activated = True # Reset

    # --- Test Case 6: Quick Add Disabled ---
    log.info("\n--- Test Case 6: Quick Add Disabled ---")
    mock_settings._quick_add_enabled = False
    context_item_6 = ContextItem(search_context, item_with_imdb, mock_settings, mock_ai_client, mock_plugin_manager)
    menu_6 = context_item_6.get_context_menu()
    log.info(f"Menu 6: {json.dumps(menu_6, indent=2)}")
    mock_settings._quick_add_enabled = True # Reset

    # --- Test Case 7: Registering a custom action ---
    log.info("\n--- Test Case 7: Registering a custom action ---")
    mock_plugin_manager.register_custom_action(
        item_id="movie1",
        action_name="my_custom_action",
        action_details={"label": "My Action", "params": {"data": "123"}}
    )
    context_item_7 = ContextItem(search_context, item_with_imdb, mock_settings, mock_ai_client, mock_plugin_manager)
    menu_7 = context_item_7.get_context_menu()
    log.info(f"Menu 7: {json.dumps(menu_7, indent=2)}")