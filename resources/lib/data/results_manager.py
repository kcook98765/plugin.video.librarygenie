import json
from resources.lib.integrations.jsonrpc.jsonrpc_manager import JSONRPC
from resources.lib.utils import utils
from resources.lib.utils.singleton_base import Singleton
from resources.lib.data.normalize import from_jsonrpc, from_db
from resources.lib.kodi.listitem.factory import build_listitem

class ResultsManager(Singleton):
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.jsonrpc = JSONRPC()
            from resources.lib.data.query_manager import QueryManager
            from resources.lib.config.config_manager import Config
            self.query_manager = QueryManager(Config().db_path)
            self._initialized = True

    def search_movie_by_criteria(self, title, year=None, director=None):
        try:
            return self.query_manager.get_matched_movies(title, year, director)
        except Exception as e:
            utils.log(f"Error searching movies: {e}", "ERROR")
            return []

    def build_display_items_for_list(self, list_id, handle):
        """Build display items for a specific list with proper error handling"""
        try:
            utils.log(f"=== BUILD_DISPLAY_ITEMS: Starting for list_id {list_id} ===", "DEBUG")

            # Get list items from database
            list_items = self.query_manager.fetch_list_items_with_details(list_id)
            utils.log(f"=== BUILD_DISPLAY_ITEMS: Retrieved {len(list_items)} list items ===", "DEBUG")

            if not list_items:
                utils.log(f"=== BUILD_DISPLAY_ITEMS: No items found for list {list_id} ===", "DEBUG")
                return []

            # Log first item structure for debugging
            if list_items:
                first_item = list_items[0]
                utils.log(f"=== BUILD_DISPLAY_ITEMS: First item keys: {list(first_item.keys())} ===", "DEBUG")
                sample_data = {k: v for k, v in list(first_item.items())[:4]}
                utils.log(f"=== BUILD_DISPLAY_ITEMS: First item sample data: {sample_data} ===", "DEBUG")

            # Check if this is from Search History folder
            list_info = self.query_manager.fetch_list_by_id(list_id)
            is_search_history = False
            if list_info and list_info.get('folder_id'):
                search_history_folder_id = self.query_manager.get_folder_id_by_name("Search History")
                is_search_history = (list_info['folder_id'] == search_history_folder_id)

            utils.log(f"=== BUILD_DISPLAY_ITEMS: Is search history: {is_search_history} ===", "DEBUG")

            # Use the working approach from your original file
            rows = list_items  # Renamed for consistency with original logic
            external, refs = [], []

            for r in rows:
                src = (r.get('source') or '').lower()
                # Sources that don't use Kodi library processing: external, plugin_addon
                # All other sources (lib, manual, search, kodi_library, shortlist_import, favorites_import) follow library item processing path
                if src in ('external', 'plugin_addon'):
                    external.append(r)
                    continue
                imdb = r.get('imdbnumber')
                title, year = '', 0

                # Try to get title/year from imdb_exports first
                if imdb:
                    utils.log(f"=== TITLE_YEAR_LOOKUP: Looking up IMDB {imdb} in imdb_exports ===", "DEBUG")
                    try:
                        q = """SELECT title, year FROM imdb_exports WHERE imdb_id = ? ORDER BY id DESC LIMIT 1"""
                        hit = self.query_manager.execute_query(q, (imdb,)) or []
                        if hit:
                            rec = hit[0]
                            title = (rec.get('title') if isinstance(rec, dict) else rec[0]) or ''
                            year = int((rec.get('year') if isinstance(rec, dict) else rec[1]) or 0)
                            utils.log(f"=== TITLE_YEAR_LOOKUP: Found in imdb_exports: {title} ({year}) for IMDB {imdb} ===", "DEBUG")
                        else:
                            utils.log(f"=== TITLE_YEAR_LOOKUP: No imdb_exports entry found for IMDB {imdb} ===", "DEBUG")
                    except Exception as e:
                        utils.log(f"=== TITLE_YEAR_LOOKUP: Error querying imdb_exports for {imdb}: {str(e)} ===", "ERROR")

                # Fallback to stored data if imdb lookup failed
                if not title:
                    title = r.get('title') or ''
                    utils.log(f"Using fallback title: {title}", "DEBUG")

                if not year:
                    try:
                        year = int(r.get('year') or 0)
                        utils.log(f"Using fallback year: {year}", "DEBUG")
                    except Exception:
                        year = 0

                # If we still have no title, try to extract from the original stored data
                if not title or title == '':
                    # Check if there's any identifying information we can use
                    stored_title = r.get('title', '')
                    if stored_title and stored_title.strip():
                        title = stored_title.strip()
                        utils.log(f"Using stored title as final fallback: {title}", "DEBUG")
                    else:
                        title = f"IMDB: {imdb}" if imdb else "Unknown Movie"
                        utils.log(f"Using IMDB ID as title fallback: {title}", "WARNING")

                refs.append({'imdb': imdb, 'title': title, 'year': year, 'search_score': r.get('search_score', 0)})

            # ---- Batch resolve via one JSON-RPC call using OR of (title AND year) ----
            batch_pairs = [{"title": r.get("title"), "year": r.get("year")} for r in refs]
            utils.log(f"=== BUILD_DISPLAY_ITEMS: Batch lookup pairs count: {len(batch_pairs)} ===", "DEBUG")
            utils.log(f"=== BUILD_DISPLAY_ITEMS: First 3 batch pairs: {batch_pairs[:3]} ===", "DEBUG")

            utils.log("=== BUILD_DISPLAY_ITEMS: Calling get_movies_by_title_year_batch ===", "DEBUG")
            try:
                lookup_result = self.jsonrpc.get_movies_by_title_year_batch(batch_pairs) or {}
                utils.log(f"=== BUILD_DISPLAY_ITEMS: Batch response keys: {list(lookup_result.keys()) if lookup_result else 'None'} ===", "DEBUG")
            except AttributeError as e:
                utils.log(f"=== BUILD_DISPLAY_ITEMS: Method not found error: {str(e)} ===", "ERROR")
                lookup_result = {}
            except Exception as e:
                utils.log(f"=== BUILD_DISPLAY_ITEMS: Batch lookup failed: {str(e)} ===", "ERROR")
                lookup_result = {}

            batch_movies = (lookup_result.get("result") or {}).get("movies") or []
            utils.log(f"=== BUILD_DISPLAY_ITEMS: JSON-RPC returned {len(batch_movies)} movies from batch lookup ===", "DEBUG")

            if batch_movies:
                # Log sample of first returned movie
                first_movie = batch_movies[0]
                utils.log(f"=== BUILD_DISPLAY_ITEMS: First returned movie keys: {list(first_movie.keys())} ===", "DEBUG")
                utils.log(f"=== BUILD_DISPLAY_ITEMS: First movie title/year: {first_movie.get('title')}/{first_movie.get('year')} ===", "DEBUG")

            # Build a simple matcher key: (normalized_title, year_int)
            def _key(t, y):
                nt = (t or "").strip().lower()
                try:
                    yi = int(y or 0)
                except Exception:
                    yi = 0
                return (nt, yi)

            # Index returned movies by (title,year) and also title-only as fallback
            idx_ty = {}
            idx_t = {}
            for m in batch_movies:
                kty = _key(m.get("title"), m.get("year"))
                idx_ty.setdefault(kty, []).append(m)
                kt = _key(m.get("title"), 0)
                idx_t.setdefault(kt, []).append(m)

            # Rebuild resolved list in the original refs order (already sorted by search score from query)
            display_items = []
            utils.log(f"=== BUILD_DISPLAY_ITEMS: Starting movie matching for {len(rows)} items ===", "DEBUG")

            for i, r in enumerate(rows):
                # Skip items that are already handled as external
                src = (r.get('source') or '').lower()
                if src in ('external', 'plugin_addon'):
                    continue

                # Handle favorites_import items separately to avoid library lookup
                if src == 'favorites_import':
                    # Check if item has a valid playable path
                    playable_path = r.get('path') or r.get('play') or r.get('file')

                    # Skip items without valid playable paths (similar to shortlist import logic)
                    if not playable_path or not str(playable_path).strip():
                        utils.log(f"Skipping favorites import item '{r.get('title', 'Unknown')}' - no valid playable path", "DEBUG")
                        continue

                    # Validate the path is actually playable (basic check)
                    path_str = str(playable_path).strip()
                    if not (path_str.startswith(('smb://', 'nfs://', 'http://', 'https://', 'ftp://', 'ftps://', 'plugin://', '/')) or
                            '\\' in path_str):  # Windows network paths
                        utils.log(f"Skipping favorites import item '{r.get('title', 'Unknown')}' - invalid path format: {path_str}", "DEBUG")
                        continue

                    # For favorites imports, use the stored data directly
                    r['_viewing_list_id'] = list_id
                    r['media_id'] = r.get('id') or r.get('media_id')

                    media_item = from_db(r)
                    list_item = build_listitem(media_item, 'search_history' if is_search_history else 'default')

                    # Use the playable path instead of info URL
                    item_url = playable_path
                    display_items.append((item_url, list_item, False))
                    continue

                processed_ref = {}
                try:
                    # Process each field that might exist in the row
                    for field in ['title', 'year', 'plot', 'rating', 'genre', 'director', 'cast', 'duration', 'search_score']:
                        processed_ref[field] = r.get(field)

                    # Handle special fields that might have different names or need processing
                    processed_ref['title'] = r.get('title') or 'Unknown Title'
                    processed_ref['year'] = r.get('year') or 0

                    if not processed_ref['title'] or processed_ref['title'] == 'Unknown Title':
                        utils.log(f"Using fallback title: {r.get('title', 'Unknown')}", "DEBUG")
                        processed_ref['title'] = r.get('title', 'Unknown')

                    if not processed_ref['year']:
                        utils.log(f"Using fallback year: {r.get('year', 0)}", "DEBUG")
                        processed_ref['year'] = r.get('year', 0)

                except Exception as e:
                    utils.log(f"Error processing row {i}: {str(e)}", "ERROR")
                    processed_ref = {'title': 'Error', 'year': 0}

                # Find matching Kodi library entries
                cand = []
                if lookup_result and 'result' in lookup_result and 'movies' in lookup_result['result']:
                    movies = lookup_result['result']['movies']
                    for movie in movies:
                        movie_title = movie.get('title', '').lower().strip()
                        ref_title = processed_ref['title'].lower().strip()
                        movie_year = movie.get('year', 0)
                        ref_year = processed_ref['year'] or 0

                        # More flexible matching - exact title match or relaxed year matching
                        if movie_title == ref_title and (movie_year == ref_year or ref_year == 0):
                            cand.append(movie)
                            utils.log(f"=== BUILD_DISPLAY_ITEMS: Item {i+1}: Found match - '{movie_title}' ({movie_year}) ===", "DEBUG")

                meta = cand[0] if cand else None

                if meta:
                    utils.log(f"=== BUILD_DISPLAY_ITEMS: Item {i+1}: Found Kodi match - title: {meta.get('title')}, movieid: {meta.get('movieid')} ===", "DEBUG")
                    # Found in Kodi library via JSON-RPC
                    cast = meta.get('cast') or []
                    if isinstance(cast, list):
                        cast = [{'name': a.get('name'),
                                 'role': a.get('role'),
                                 'thumbnail': a.get('thumbnail')} for a in cast]
                    meta['cast'] = cast
                    if isinstance(meta.get('writer'), list):
                        meta['writer'] = ' / '.join(meta['writer'])
                    # Preserve search score from original item for sorting
                    meta['search_score'] = processed_ref.get('search_score', 0)
                    meta['list_item_id'] = r.get('list_item_id')

                    # Add context for list viewing and removal
                    meta['_viewing_list_id'] = list_id
                    meta['media_id'] = r.get('id') or r.get('media_id') or meta.get('movieid')

                    media_item = from_jsonrpc(meta)
                    list_item = build_listitem(media_item, 'search_history' if is_search_history else 'default')

                    # Determine the appropriate URL for this item
                    # For manual items and library items, use the file path if available
                    file_path = meta.get('file')
                    if file_path:
                        item_url = file_path
                    else:
                        # Fallback for items without file path
                        item_url = f"info://{r.get('id', 'unknown')}"
                    display_items.append((item_url, list_item, False))
                else:
                    utils.log(f"=== BUILD_DISPLAY_ITEMS: Item {i+1}: No Kodi match found, using database data for '{processed_ref.get('title')}' ===", "DEBUG")
                    # No library match - create item from database data

                    # Use the original database row data and normalize it
                    db_item = dict(r)  # Copy the original row

                    # Add context data
                    db_item['list_item_id'] = r.get('list_item_id')
                    db_item['_viewing_list_id'] = list_id
                    db_item['media_id'] = r.get('id') or r.get('media_id')
                    db_item['source'] = 'db'

                    # Ensure we have the basic required fields
                    if not db_item.get('title'):
                        db_item['title'] = processed_ref.get('title', 'Unknown')
                    if not db_item.get('year'):
                        db_item['year'] = processed_ref.get('year', 0)
                    
                    # Set proper media type for rich metadata
                    db_item['media_type'] = 'movie'

                    utils.log(f"=== BUILD_DISPLAY_ITEMS: Item {i+1}: Creating from DB data - title: '{db_item.get('title')}', plot length: {len(str(db_item.get('plot', '')))} ===", "DEBUG")

                    media_item = from_db(db_item)
                    list_item = build_listitem(media_item, 'search_history' if is_search_history else 'default')

                    utils.log(f"=== BUILD_DISPLAY_ITEMS: Item {i+1}: Successfully created ListItem from database data ===", "DEBUG")

                    # Use fallback URL for items without file path
                    item_url = f"info://{r.get('id', 'unknown')}"
                    display_items.append((item_url, list_item, False))

            # External items processed separately with stored metadata
            # Handle None search_score values that can't be compared
            external_sorted = sorted(external, key=lambda x: x.get('search_score') or 0, reverse=True)
            for item in external_sorted:
                # Add context for list viewing and removal
                item['_viewing_list_id'] = list_id
                item['media_id'] = item.get('id') or item.get('media_id')

                media_item = from_db(item) # Assuming from_db can handle external item structure
                list_item = build_listitem(media_item, 'search_history' if is_search_history else 'default')

                # Use file path or fallback URL for external items
                item_url = item.get('file', f"external://{item.get('id', 'unknown')}")
                display_items.append((item_url, list_item, False))

            utils.log(f"=== BUILD_DISPLAY_ITEMS: Created {len(display_items)} display items ===", "DEBUG")
            return display_items

        except Exception as e:
            utils.log(f"Error in build_display_items_for_list: {str(e)}", "ERROR")
            import traceback
            utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")
            return []