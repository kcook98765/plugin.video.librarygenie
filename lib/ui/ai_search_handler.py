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
from ..utils.logger import get_logger
from .localization import L

# Import PluginContext if it's defined elsewhere and needed for type hinting
# For now, assuming it's a placeholder or defined in a broader context
class PluginContext:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.params = {}

class AISearchHandler:
    """Handler for AI search functionality with IMDb list matching"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.ai_client = get_ai_search_client()
        self.query_manager = get_query_manager()

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
            progress = locals().get('progress')
            if progress:
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
        Match IMDb IDs to existing media items in the database and build standard media item format

        Args:
            imdb_ids: List of IMDb IDs to match

        Returns:
            List of matched media item dictionaries in standard format
        """
        try:
            # Use correct column names from schema
            placeholders = ','.join(['?' for _ in imdb_ids])
            query = f"""
                SELECT id, title, year, imdbnumber, tmdb_id, plot, rating, 
                       genre, duration, art, kodi_id, media_type, created_at
                FROM media_items 
                WHERE imdbnumber IN ({placeholders})
                ORDER BY title
            """

            rows = self.query_manager.connection_manager.execute_query(query, imdb_ids)

            # Convert rows to standard media item dictionaries  
            matched_items = []
            for row in rows:
                item_dict = dict(row)
                # Convert to standard format expected by add_search_results_to_list
                standard_item = {
                    'kodi_id': item_dict.get('kodi_id'),
                    'media_type': item_dict.get('media_type', 'movie'),
                    'title': item_dict.get('title', ''),
                    'year': item_dict.get('year', 0),
                    'imdb_id': item_dict.get('imdbnumber', ''),
                    'plot': item_dict.get('plot', ''),
                    'rating': item_dict.get('rating', 0),
                    'genre': item_dict.get('genre', ''),
                    'runtime': item_dict.get('duration', 0),
                    'source': 'ai_search'
                }

                # Parse art JSON if available
                art_data = item_dict.get('art')
                if art_data:
                    try:
                        import json
                        art = json.loads(art_data) if isinstance(art_data, str) else art_data
                        standard_item['art'] = art
                    except:
                        standard_item['art'] = {}
                else:
                    standard_item['art'] = {}

                matched_items.append(standard_item)

            self.logger.info(f"AI SEARCH MATCH: Found {len(matched_items)} matches out of {len(imdb_ids)} IMDb IDs")

            return matched_items

        except Exception as e:
            self.logger.error(f"AI SEARCH MATCH: Error matching IMDb IDs: {e}")
            return []

    def _create_ai_search_history_list(self, query: str, matched_items: List[Dict[str, Any]], total_ai_results: int) -> Optional[int]:
        """
        Create a search history list for AI search results using standard pattern

        Args:
            query: Original search query
            matched_items: List of matched media items
            total_ai_results: Total number of results from AI search

        Returns:
            List ID if successful, None if failed
        """
        try:
            # Create search history list with AI search description - follow same pattern as local search
            query_desc = f"AI: {query}"

            list_id = self.query_manager.create_search_history_list(
                query=query_desc,
                search_type="ai_search",
                result_count=len(matched_items)
            )

            if not list_id:
                self.logger.error("AI SEARCH HISTORY: Failed to create search history list")
                return None

            self.logger.info(f"AI SEARCH HISTORY: Created search history list {list_id}")

            # Use standard method to add items to list - same as local search
            search_results = {"items": matched_items}
            added_count = self.query_manager.add_search_results_to_list(list_id, search_results)

            if added_count > 0:
                self.logger.info(f"AI SEARCH HISTORY: Added {added_count}/{len(matched_items)} items to search history list {list_id}")
                return list_id
            else:
                # Clean up empty list
                self.query_manager.delete_list(list_id)
                self.logger.warning("AI SEARCH HISTORY: No items were added to list, cleaning up")
                return None

        except Exception as e:
            self.logger.error(f"AI SEARCH HISTORY: Error creating search history list: {e}")
            return None

    def _redirect_to_search_list(self, list_id: int):
        """
        Redirect to the created search history list using same method as local search

        Args:
            list_id: ID of the list to show
        """
        try:
            import xbmcaddon
            addon = xbmcaddon.Addon()
            addon_id = addon.getAddonInfo('id')

            # Use same redirect pattern as local search
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

    def find_similar_movies(self, context) -> bool:
        """
        Find movies similar to the current item using AI search

        Args:
            context: Plugin context with parameters

        Returns:
            bool: True if successful
        """
        try:
            # Get parameters from context
            imdb_id = context.params.get('imdb_id')
            title = context.params.get('title', 'Unknown')
            year = context.params.get('year', '')
            is_plugin_context = context.params.get('is_plugin_context', False)

            if not imdb_id or not imdb_id.startswith('tt'):
                self.logger.error("SIMILAR MOVIES: Invalid or missing IMDb ID")
                xbmcgui.Dialog().notification(
                    "Similar Movies",
                    "No valid IMDb ID found",
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
                return False

            self.logger.info(f"SIMILAR MOVIES: Finding movies similar to {title} ({imdb_id})")

            # Check if AI search is activated
            if not self.ai_client.is_activated():
                self.logger.warning("SIMILAR MOVIES: AI search not activated")
                xbmcgui.Dialog().notification(
                    "Similar Movies",
                    "AI Search not activated",
                    xbmcgui.NOTIFICATION_WARNING,
                    5000
                )
                return False

            # Show facet selection dialog
            facets = self._show_facet_selection_dialog()
            if not facets:
                self.logger.info("SIMILAR MOVIES: User cancelled facet selection")
                return False

            # Show progress dialog
            progress = xbmcgui.DialogProgress()
            movie_desc = f"{title} ({year})" if year else title
            progress.create("Similar Movies", f"Finding movies similar to: {movie_desc}")
            progress.update(20, "Connecting to AI search server...")

            # Test connection first
            connection_test = self.ai_client.test_connection()
            if not connection_test.get('success'):
                progress.close()
                error_msg = connection_test.get('error', 'Connection failed')
                self.logger.error(f"SIMILAR MOVIES: Connection test failed: {error_msg}")
                xbmcgui.Dialog().notification(
                    "Similar Movies",
                    f"Connection failed: {error_msg}",
                    xbmcgui.NOTIFICATION_ERROR,
                    5000
                )
                return False

            progress.update(40, "Searching for similar movies...")

            # Call similar movies endpoint
            similar_imdb_ids = self.ai_client.search_similar_movies(imdb_id, facets)

            if not similar_imdb_ids:
                progress.close()
                self.logger.info("SIMILAR MOVIES: No similar movies found")
                xbmcgui.Dialog().notification(
                    "Similar Movies",
                    "No similar movies found",
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
                return False

            progress.update(60, "Matching with local library...")

            # Match IMDb IDs with local media items
            matched_items = self._match_imdb_ids_to_media_items(similar_imdb_ids)

            progress.update(80, "Creating results list...")

            # Create search history list for similar movies
            if matched_items:
                list_id = self._create_similar_movies_list(title, year, matched_items, len(similar_imdb_ids), facets)

                if list_id:
                    progress.close()
                    self.logger.info(f"SIMILAR MOVIES: Successfully created list {list_id} with {len(matched_items)} items")

                    # Show success notification
                    xbmcgui.Dialog().notification(
                        "Similar Movies",
                        f"Found {len(matched_items)} similar movies in your library",
                        xbmcgui.NOTIFICATION_INFO,
                        5000
                    )

                    # Always attempt to redirect to the created list
                    # The redirect logic will handle whether navigation is appropriate
                    self._redirect_to_search_list(list_id)

                    return True
                else:
                    progress.close()
                    self.logger.error("SIMILAR MOVIES: Failed to create search history list")
                    xbmcgui.Dialog().notification(
                        "Similar Movies",
                        "Failed to save results",
                        xbmcgui.NOTIFICATION_ERROR,
                        5000
                    )
                    return False
            else:
                progress.close()
                self.logger.info("SIMILAR MOVIES: No matches found in local library")
                xbmcgui.Dialog().notification(
                    "Similar Movies",
                    f"No similar movies found in your library (searched {len(similar_imdb_ids)} movies)",
                    xbmcgui.NOTIFICATION_INFO,
                    5000
                )
                return False

        except Exception as e:
            progress = locals().get('progress')
            if progress:
                progress.close()
            self.logger.error(f"SIMILAR MOVIES: Error finding similar movies: {e}")
            import traceback
            self.logger.error(f"SIMILAR MOVIES: Traceback: {traceback.format_exc()}")
            xbmcgui.Dialog().notification(
                "Similar Movies",
                "Error occurred",
                xbmcgui.NOTIFICATION_ERROR,
                5000
            )
            return False

    def _show_facet_selection_dialog(self) -> Optional[Dict[str, bool]]:
        """
        Show dialog for user to select similarity facets

        Returns:
            Dict with facet selections or None if cancelled
        """
        try:
            # Define facets with descriptions
            facet_options = [
                ("Plot/Story", "plot", "Compare story and plot elements"),
                ("Mood/Tone", "mood", "Compare emotional tone and atmosphere"),
                ("Themes", "themes", "Compare underlying themes and subtext"),
                ("Genre/Style", "genre", "Compare genre and cinematic style")
            ]

            # Show multi-select dialog
            dialog = xbmcgui.Dialog()
            selected_indices = dialog.multiselect(
                "Select similarity aspects to compare:",
                [f"{label} - {desc}" for label, _, desc in facet_options]
            )

            if selected_indices is None or len(selected_indices) == 0:
                return None

            # Build facets dict from selections
            facets = {}
            for i, (_, key, _) in enumerate(facet_options):
                facets[key] = i in selected_indices

            # Ensure at least one facet is selected
            if not any(facets.values()):
                return None

            self.logger.info(f"SIMILAR MOVIES: Selected facets: {facets}")
            return facets

        except Exception as e:
            self.logger.error(f"SIMILAR MOVIES: Error in facet selection: {e}")
            return None

    def _create_similar_movies_list(self, title: str, year: str, matched_items: List[Dict[str, Any]], 
                                   total_results: int, facets: Dict[str, bool]) -> Optional[int]:
        """
        Create a search history list for similar movies results

        Args:
            title: Original movie title
            year: Original movie year
            matched_items: List of matched media items
            total_results: Total number of similar movies found
            facets: Selected similarity facets

        Returns:
            List ID if successful, None if failed
        """
        try:
            # Build facet description
            selected_facets = [key.title() for key, selected in facets.items() if selected]
            facet_desc = ", ".join(selected_facets)

            # Create search history list with similar movies description
            movie_desc = f"{title} ({year})" if year else title
            query_desc = f"Similar to: {movie_desc}"
            description = f"Found {total_results} similar movies ({facet_desc}), {len(matched_items)} in your library"

            list_id = self.query_manager.create_search_history_list(
                query_desc,
                "similar_movies",
                len(matched_items)
            )

            if not list_id:
                self.logger.error("SIMILAR MOVIES: Failed to create search history list")
                return None

            self.logger.info(f"SIMILAR MOVIES: Created search history list {list_id}")

            # Add matched items to the list
            added_count = 0
            with self.query_manager.connection_manager.transaction() as conn:
                for position, item in enumerate(matched_items):
                    try:
                        # Add item to list using direct database insert
                        conn.execute("""
                            INSERT OR IGNORE INTO list_items (list_id, media_item_id, position)
                            VALUES (?, ?, ?)
                        """, [list_id, item['id'], position])
                        added_count += 1

                    except Exception as e:
                        self.logger.error(f"SIMILAR MOVIES: Error adding item {item.get('id', 'unknown')} to list: {e}")

            self.logger.info(f"SIMILAR MOVIES: Added {added_count}/{len(matched_items)} items to search history list {list_id}")

            if added_count > 0:
                return list_id
            else:
                # Clean up empty list
                self.query_manager.delete_list(list_id)
                return None

        except Exception as e:
            self.logger.error(f"SIMILAR MOVIES: Error creating search history list: {e}")
            return None

    def authorize_ai_search(self, context: PluginContext) -> None:
        """Handle AI search authorization"""
        try:
            # Check if already authorized
            ai_client = get_ai_search_client()
            if ai_client.is_activated():
                xbmcgui.Dialog().ok(
                    "Already Authorized", 
                    "AI Search is already activated and working."
                )
                return

            # Show OTP input dialog
            otp_code = xbmcgui.Dialog().input(
                "Enter 8-digit pairing code from AI Search website:",
                type=xbmcgui.INPUT_ALPHANUM
            )

            if not otp_code:
                return

            # Show progress dialog
            progress = xbmcgui.DialogProgress()
            progress.create("AI Search", "Activating AI Search...")
            progress.update(50)

            try:
                result = ai_client.activate_with_otp(otp_code)
                progress.update(100)
                progress.close()

                if result['success']:
                    xbmcgui.Dialog().ok(
                        "Success!",
                        f"AI Search activated successfully!\nUser: {result.get('user_email', 'Unknown')}"
                    )
                else:
                    xbmcgui.Dialog().ok(
                        "Activation Failed",
                        f"Error: {result.get('error', 'Unknown error')}"
                    )
            except Exception as e:
                progress.close()
                context.logger.error(f"Error during activation: {e}")
                xbmcgui.Dialog().ok(
                    "Error", 
                    f"Failed to activate AI Search: {str(e)}"
                )

        except Exception as e:
            context.logger.error(f"Error in authorize_ai_search: {e}")
            xbmcgui.Dialog().ok(
                "Error",
                f"An error occurred: {str(e)}"
            )

    def trigger_replace_sync(self, context: PluginContext) -> None:
        """Trigger an authoritative replace sync with AI Search server"""
        try:
            ai_client = get_ai_search_client()

            # Check if AI Search is activated
            if not ai_client.is_activated():
                xbmcgui.Dialog().ok(
                    "Not Activated",
                    "AI Search must be activated before syncing.\nUse 'Authorize AI Search' first."
                )
                return

            # Confirm replace sync
            if not xbmcgui.Dialog().yesno(
                "AI Search Replace Sync",
                "This will replace the entire server movie collection with your current Kodi library.",
                "Server movies not in Kodi will be removed.",
                "Continue with replace sync?"
            ):
                return

            # Show progress dialog
            progress = xbmcgui.DialogProgress()
            progress.create("AI Search Replace Sync", "Scanning local library...")
            progress.update(10)

            try:
                # Get movies from local database
                from ..data.connection_manager import get_connection_manager
                conn_manager = get_connection_manager()

                progress.update(30, "Collecting movie data...")

                movies_result = conn_manager.execute_query(
                    "SELECT imdbnumber, title, year FROM media_items WHERE imdbnumber IS NOT NULL AND imdbnumber != ''"
                )

                movies_with_imdb = []
                for row in movies_result:
                    imdb_id = row.get('imdbnumber', '').strip()
                    if imdb_id and imdb_id.startswith('tt'):
                        movies_with_imdb.append({
                            'imdb_id': imdb_id,
                            'title': row.get('title', ''),
                            'year': row.get('year', 0)
                        })

                progress.update(50, f"Found {len(movies_with_imdb)} movies...")

                if not movies_with_imdb:
                    progress.close()
                    xbmcgui.Dialog().ok(
                        "No Movies Found",
                        "No movies with IMDb IDs found in your library."
                    )
                    return

                progress.update(70, "Syncing with server (replace mode)...")

                # Perform replace sync
                result = ai_client.sync_media_batch(
                    movies_with_imdb, 
                    batch_size=500, 
                    use_replace_mode=True
                )

                progress.update(100)
                progress.close()

                if result and result.get('success'):
                    sync_results = result.get('results', {})
                    total_processed = result.get('total_processed', 0)

                    message = (
                        f"Replace sync completed successfully!\n\n"
                        f"Total processed: {total_processed}\n"
                        f"Added: {sync_results.get('added', 0)}\n"
                        f"Already present: {sync_results.get('already_present', 0)}\n"
                        f"Invalid: {sync_results.get('invalid', 0)}"
                    )

                    xbmcgui.Dialog().ok("Sync Complete", message)
                else:
                    error_msg = result.get('error', 'Unknown error') if result else 'No response from server'
                    xbmcgui.Dialog().ok(
                        "Sync Failed",
                        f"Replace sync failed: {error_msg}"
                    )

            except Exception as e:
                progress.close()
                context.logger.error(f"Error during replace sync: {e}")
                xbmcgui.Dialog().ok(
                    "Error",
                    f"Failed to perform replace sync: {str(e)}"
                )

        except Exception as e:
            context.logger.error(f"Error in trigger_replace_sync: {e}")
            xbmcgui.Dialog().ok(
                "Error",
                f"An error occurred: {str(e)}"
            )


def get_ai_search_handler():
    """Factory function to get AI search handler"""
    return AISearchHandler()