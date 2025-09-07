
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - AI Search Handler
Handles AI search queries and creates search history lists with matching media items
"""

import xbmcgui
import xbmc
from typing import Optional, List, Dict, Any

from ..remote.ai_search_client import get_ai_search_client
from ..data.query_manager import get_query_manager
from ..data.storage_manager import get_storage_manager
from ..utils.logger import get_logger
from .localization import L


class AISearchHandler:
    """Handler for AI search functionality with IMDb list matching"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.ai_client = get_ai_search_client()
        self.query_manager = get_query_manager()
        self.storage_manager = get_storage_manager()

    def perform_ai_search(self, query: str) -> bool:
        """
        Perform AI search and create search history list with matched media items
        
        Args:
            query: User's search query
            
        Returns:
            bool: True if search was successful and results were saved
        """
        try:
            self.logger.info(f"AI SEARCH: Starting AI search for query: '{query}'")

            # Check if AI search is activated
            if not self.ai_client.is_activated():
                self.logger.warning("AI SEARCH: AI search not activated")
                xbmcgui.Dialog().notification(
                    "LibraryGenie",
                    "AI Search not activated",
                    xbmcgui.NOTIFICATION_WARNING,
                    5000
                )
                return False

            # Show progress dialog
            progress = xbmcgui.DialogProgress()
            progress.create("AI Search", f"Searching for: {query}")
            progress.update(20, "Connecting to AI search server...")

            # Test connection first
            connection_test = self.ai_client.test_connection()
            if not connection_test.get('success'):
                progress.close()
                error_msg = connection_test.get('error', 'Connection failed')
                self.logger.error(f"AI SEARCH: Connection test failed: {error_msg}")
                xbmcgui.Dialog().notification(
                    "AI Search",
                    f"Connection failed: {error_msg}",
                    xbmcgui.NOTIFICATION_ERROR,
                    5000
                )
                return False

            progress.update(40, "Performing AI search...")

            # Perform AI search to get IMDb IDs
            search_results = self.ai_client.search_movies(query, limit=100)
            
            if not search_results or not search_results.get('success'):
                progress.close()
                error_msg = search_results.get('error', 'Unknown error') if search_results else 'No response from server'
                self.logger.error(f"AI SEARCH: Search failed: {error_msg}")
                xbmcgui.Dialog().notification(
                    "AI Search",
                    f"Search failed: {error_msg}",
                    xbmcgui.NOTIFICATION_ERROR,
                    5000
                )
                return False

            ai_results = search_results.get('results', [])
            self.logger.info(f"AI SEARCH: Received {len(ai_results)} results from AI search")

            if not ai_results:
                progress.close()
                xbmcgui.Dialog().notification(
                    "AI Search",
                    "No results found",
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
                return False

            progress.update(60, "Matching with local library...")

            # Extract IMDb IDs from AI search results
            imdb_ids = []
            for result in ai_results:
                imdb_id = result.get('imdb_id')
                if imdb_id and imdb_id.startswith('tt'):
                    imdb_ids.append(imdb_id)

            self.logger.info(f"AI SEARCH: Extracted {len(imdb_ids)} IMDb IDs from AI results")

            # Match IMDb IDs with local media items
            matched_items = self._match_imdb_ids_to_media_items(imdb_ids)
            
            progress.update(80, "Creating search history...")

            # Create search history list
            if matched_items:
                list_id = self._create_ai_search_history_list(query, matched_items, len(ai_results))
                
                if list_id:
                    progress.close()
                    self.logger.info(f"AI SEARCH: Successfully created search history list {list_id} with {len(matched_items)} items")
                    
                    # Show success notification
                    xbmcgui.Dialog().notification(
                        "AI Search",
                        f"Found {len(matched_items)} matches in your library",
                        xbmcgui.NOTIFICATION_INFO,
                        5000
                    )
                    
                    # Redirect to the created list
                    self._redirect_to_search_list(list_id)
                    return True
                else:
                    progress.close()
                    self.logger.error("AI SEARCH: Failed to create search history list")
                    xbmcgui.Dialog().notification(
                        "AI Search",
                        "Failed to save search results",
                        xbmcgui.NOTIFICATION_ERROR,
                        5000
                    )
                    return False
            else:
                progress.close()
                self.logger.info("AI SEARCH: No matches found in local library")
                xbmcgui.Dialog().notification(
                    "AI Search",
                    f"No matches found in your library (searched {len(ai_results)} movies)",
                    xbmcgui.NOTIFICATION_INFO,
                    5000
                )
                return False

        except Exception as e:
            if 'progress' in locals():
                progress.close()
            self.logger.error(f"AI SEARCH: Error performing AI search: {e}")
            import traceback
            self.logger.error(f"AI SEARCH: Traceback: {traceback.format_exc()}")
            xbmcgui.Dialog().notification(
                "AI Search",
                "Search error occurred",
                xbmcgui.NOTIFICATION_ERROR,
                5000
            )
            return False

    def _match_imdb_ids_to_media_items(self, imdb_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Match IMDb IDs to existing media items in the database
        
        Args:
            imdb_ids: List of IMDb IDs to match
            
        Returns:
            List of matched media item dictionaries
        """
        try:
            matched_items = []
            
            # Get database connection
            conn = self.storage_manager.get_connection()
            cursor = conn.cursor()
            
            # Query to find media items by IMDb ID
            placeholders = ','.join(['?' for _ in imdb_ids])
            query = f"""
                SELECT id, title, year, imdb_id, tmdb_id, plot, rating, 
                       poster_url, fanart_url, trailer_url, genres, runtime,
                       kodi_id, kodi_dbtype, date_added
                FROM media_items 
                WHERE imdb_id IN ({placeholders})
                ORDER BY title
            """
            
            cursor.execute(query, imdb_ids)
            rows = cursor.fetchall()
            
            # Convert rows to dictionaries
            columns = [desc[0] for desc in cursor.description]
            for row in rows:
                item_dict = dict(zip(columns, row))
                matched_items.append(item_dict)
            
            self.logger.info(f"AI SEARCH MATCH: Found {len(matched_items)} matches out of {len(imdb_ids)} IMDb IDs")
            
            return matched_items
            
        except Exception as e:
            self.logger.error(f"AI SEARCH MATCH: Error matching IMDb IDs: {e}")
            return []

    def _create_ai_search_history_list(self, query: str, matched_items: List[Dict[str, Any]], total_ai_results: int) -> Optional[int]:
        """
        Create a search history list for AI search results
        
        Args:
            query: Original search query
            matched_items: List of matched media items
            total_ai_results: Total number of results from AI search
            
        Returns:
            List ID if successful, None if failed
        """
        try:
            # Create search history list with AI search description
            query_desc = f"AI: {query}"
            description = f"AI search found {total_ai_results} results, {len(matched_items)} in your library"
            
            list_id = self.query_manager.create_search_history_list(
                query=query_desc,
                search_type="ai_search",
                result_count=len(matched_items),
                description=description
            )
            
            if not list_id:
                self.logger.error("AI SEARCH HISTORY: Failed to create search history list")
                return None
            
            self.logger.info(f"AI SEARCH HISTORY: Created search history list {list_id}")
            
            # Add matched items to the list
            added_count = 0
            for item in matched_items:
                try:
                    # Add item to list using media_item_id
                    success = self.query_manager.add_media_item_to_list(list_id, item['id'])
                    if success:
                        added_count += 1
                    else:
                        self.logger.warning(f"AI SEARCH HISTORY: Failed to add item {item['id']} to list {list_id}")
                        
                except Exception as e:
                    self.logger.error(f"AI SEARCH HISTORY: Error adding item {item.get('id', 'unknown')} to list: {e}")
            
            self.logger.info(f"AI SEARCH HISTORY: Added {added_count}/{len(matched_items)} items to search history list {list_id}")
            
            if added_count > 0:
                return list_id
            else:
                # Clean up empty list
                self.query_manager.delete_list(list_id)
                return None
                
        except Exception as e:
            self.logger.error(f"AI SEARCH HISTORY: Error creating search history list: {e}")
            return None

    def _redirect_to_search_list(self, list_id: int):
        """
        Redirect to the created search history list
        
        Args:
            list_id: ID of the list to show
        """
        try:
            import xbmcaddon
            addon = xbmcaddon.Addon()
            addon_id = addon.getAddonInfo('id')
            
            list_url = f"plugin://{addon_id}/?action=show_list&list_id={list_id}"
            xbmc.executebuiltin(f'Container.Update("{list_url}",replace)')
            
            self.logger.info(f"AI SEARCH: Redirected to search history list {list_id}")
            
        except Exception as e:
            self.logger.error(f"AI SEARCH: Failed to redirect to search list: {e}")

    def prompt_and_search(self) -> bool:
        """
        Prompt user for AI search query and perform search
        
        Returns:
            bool: True if search was successful
        """
        try:
            # Get search query from user
            dialog = xbmcgui.Dialog()
            query = dialog.input(
                "Enter AI Search Query", 
                type=xbmcgui.INPUT_ALPHANUM
            )
            
            if not query or not query.strip():
                self.logger.info("AI SEARCH PROMPT: User cancelled or entered empty query")
                return False
            
            query = query.strip()
            self.logger.info(f"AI SEARCH PROMPT: User entered query: '{query}'")
            
            # Perform the search
            return self.perform_ai_search(query)
            
        except Exception as e:
            self.logger.error(f"AI SEARCH PROMPT: Error in prompt and search: {e}")
            return False


def get_ai_search_handler():
    """Factory function to get AI search handler"""
    return AISearchHandler()
