
import json
from resources.lib.jsonrpc_manager import JSONRPC
from resources.lib import utils
from resources.lib.singleton_base import Singleton

class ResultsManager(Singleton):
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.jsonrpc = JSONRPC()
            from resources.lib.query_manager import QueryManager
            from resources.lib.config_manager import Config
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
                # Only external and plugin_addon sources go to external processing
                # All other sources (lib, manual, search, kodi_library) follow library item processing path
                if src == 'external' or src == 'plugin_addon':
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
            batch_resp = self.jsonrpc.get_movies_by_title_year_batch(batch_pairs) or {}
            utils.log(f"=== BUILD_DISPLAY_ITEMS: Batch response keys: {list(batch_resp.keys()) if batch_resp else 'None'} ===", "DEBUG")

            batch_movies = (batch_resp.get("result") or {}).get("movies") or []
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
                if src == 'external' or src == 'plugin_addon':
                    continue

                ref_title = r.get("title", "")
                ref_year = r.get("year", 0)
                ref_imdb = r.get("imdbnumber", "")

                utils.log(f"=== BUILD_DISPLAY_ITEMS: Item {i+1}: ref_title='{ref_title}', ref_year={ref_year}, ref_imdb='{ref_imdb}' ===", "DEBUG")

                # Find the corresponding processed ref data
                processed_ref = next((ref for ref in refs if ref.get('imdb') == ref_imdb and ref.get('title') == ref_title and ref.get('year') == ref_year), None)
                if not processed_ref:
                    # Fallback if processed_ref is somehow not found, use original row data
                    processed_ref = {'title': ref_title, 'year': ref_year, 'imdb': ref_imdb, 'search_score': r.get('search_score', 0)}
                    utils.log(f"=== BUILD_DISPLAY_ITEMS: Item {i+1}: Using fallback processed_ref ===", "WARNING")
                else:
                    utils.log(f"=== BUILD_DISPLAY_ITEMS: Item {i+1}: Found matching processed_ref ===", "DEBUG")

                k_exact = _key(processed_ref.get("title"), processed_ref.get("year"))
                k_title = _key(processed_ref.get("title"), 0)
                utils.log(f"=== BUILD_DISPLAY_ITEMS: Item {i+1}: Lookup keys - exact: {k_exact}, title: {k_title} ===", "DEBUG")

                cand = (idx_ty.get(k_exact) or idx_t.get(k_title) or [])
                meta = cand[0] if cand else None

                utils.log(f"=== BUILD_DISPLAY_ITEMS: Item {i+1}: Found {len(cand)} candidates, meta exists: {meta is not None} ===", "DEBUG")

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
                    
                    from resources.lib.listitem_builder import ListItemBuilder
                    list_item = ListItemBuilder.build_video_item(meta, is_search_history=is_search_history)
                    
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
                    # No Kodi match found - using fallback data
                    fallback_title = processed_ref.get("title") or 'Unknown Title'
                    utils.log(f"Item {i+1}: No Kodi match for '{processed_ref.get('title')}' ({processed_ref.get('year')}), using fallback title: '{fallback_title}'", "WARNING")
                    resolved_item = {
                        'id': r.get('id'),
                        'title': f"[Unmatched] {processed_ref.get('title') or ref_imdb or 'Unknown'}",
                        'year': processed_ref.get('year', 0) or 0,
                        'plot': f"IMDb ID: {ref_imdb} - Not found in Kodi library" if ref_imdb else "Not found in Kodi library",
                        'rating': 0.0,
                        'kodi_id': None,
                        'file': None,
                        'genre': '',
                        'cast': [],
                        'art': {},
                        'search_score': processed_ref.get('search_score', 0),
                        'list_item_id': r.get('list_item_id'),
                        '_viewing_list_id': list_id,
                        'media_id': r.get('id') or r.get('media_id'),
                        'playable': False
                    }
                    from resources.lib.listitem_builder import ListItemBuilder
                    list_item = ListItemBuilder.build_video_item(resolved_item, is_search_history=is_search_history)
                    
                    # Use info URL for non-playable items
                    item_url = f"info://{ref_imdb}" if ref_imdb else f"info://{r.get('id', 'unknown')}"
                    display_items.append((item_url, list_item, False))

            # Sort external items by search score as well if they have scores
            external_sorted = sorted(external, key=lambda x: x.get('search_score', 0), reverse=True)
            for item in external_sorted:
                # Add context for list viewing and removal
                item['_viewing_list_id'] = list_id
                item['media_id'] = item.get('id') or item.get('media_id')
                
                from resources.lib.listitem_builder import ListItemBuilder
                list_item = ListItemBuilder.build_video_item(item, is_search_history=is_search_history)
                
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
