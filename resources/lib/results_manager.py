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

    def build_display_items_for_list(self, list_id: int):
        """Build display items for a specific list with comprehensive metadata"""
        import time
        start_time = time.time()
        try:
            utils.log(f"[LIST BUILD] Starting build_display_items_for_list for list_id={list_id}", "INFO")
            utils.log(f"[LIST BUILD] Memory check - About to fetch list items", "DEBUG")

            # Get list items with full details
            fetch_start = time.time()
            try:
                list_items = self.query_manager.fetch_list_items_with_details(list_id)
                utils.log(f"[LIST BUILD] Successfully fetched list items from database", "DEBUG")
            except Exception as fetch_error:
                utils.log(f"[LIST BUILD] CRITICAL: Database fetch failed: {str(fetch_error)}", "ERROR")
                import traceback
                utils.log(f"[LIST BUILD] Database fetch traceback: {traceback.format_exc()}", "ERROR")
                return []
                
            fetch_time = time.time() - fetch_start
            utils.log(f"[LIST BUILD] Fetched {len(list_items)} items in {fetch_time:.3f}s", "INFO")
            
            if not list_items:
                utils.log(f"[LIST BUILD] WARNING: No items found for list_id {list_id}", "WARNING")
                return []
            
            utils.log(f"[LIST BUILD] Memory check - About to process {len(list_items)} items", "DEBUG")

            # Log summary of items being processed
            utils.log(f"Processing {len(list_items)} items for list display", "DEBUG")

            rows = list_items # Renamed for consistency with original logic
            external, refs = [], []

            # Determine if this list is part of the search history
            is_search_history = self.query_manager.is_search_history(list_id)

            for r in rows:
                src = (r.get('source') or '').lower()
                if src == 'external':
                    external.append(r)
                    continue
                imdb = r.get('imdbnumber')
                title, year = '', 0

                # Try to get title/year from imdb_exports first
                if imdb:
                    try:
                        q = """SELECT title, year FROM imdb_exports WHERE imdb_id = ? ORDER BY id DESC LIMIT 1"""
                        hit = self.query_manager.execute_query(q, (imdb,)) or []
                        if hit:
                            rec = hit[0]
                            title = (rec.get('title') if isinstance(rec, dict) else rec[0]) or ''
                            year = int((rec.get('year') if isinstance(rec, dict) else rec[1]) or 0)
                            # utils.log(f"Found in imdb_exports: {title} ({year}) for IMDB {imdb}", "DEBUG")
                        else:
                            utils.log(f"No imdb_exports entry found for IMDB {imdb}", "DEBUG")
                    except Exception as e:
                        utils.log(f"Error querying imdb_exports for {imdb}: {str(e)}", "ERROR")

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

                refs.append({'imdb': imdb, 'title': title, 'year': year, 'search_score': r.get('search_score', 0)}) # Include search_score here

            # ---- Batch resolve via one JSON-RPC call using OR of (title AND year) ----
            batch_start = time.time()
            batch_pairs = [{"title": r.get("title"), "year": r.get("year")} for r in refs]
            utils.log(f"[LIST BUILD] Prepared {len(batch_pairs)} batch lookup pairs", "DEBUG")
            utils.log(f"[LIST BUILD] Sample pairs: {batch_pairs[:3]}..." if len(batch_pairs) > 3 else f"Batch lookup pairs: {batch_pairs}", "DEBUG")

            jsonrpc_start = time.time()
            batch_resp = self.jsonrpc.get_movies_by_title_year_batch(batch_pairs) or {}
            jsonrpc_time = time.time() - jsonrpc_start
            batch_movies = (batch_resp.get("result") or {}).get("movies") or []
            utils.log(f"[LIST BUILD] JSON-RPC batch lookup completed in {jsonrpc_time:.3f}s, returned {len(batch_movies)} movies", "INFO")

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
            resolved_items_for_list = []
            for i, r in enumerate(rows): # Use original 'rows' to get 'id' and 'source' for unmatched items
                ref_title = r.get("title", "") # Get title from original row if available
                ref_year = r.get("year", 0) # Get year from original row if available
                ref_imdb = r.get("imdbnumber", "") # Get imdbnumber from original row if available

                # Find the corresponding processed ref data
                processed_ref = next((ref for ref in refs if ref.get('imdb') == ref_imdb and ref.get('title') == ref_title and ref.get('year') == ref_year), None)
                if not processed_ref:
                    # Fallback if processed_ref is somehow not found, use original row data
                    processed_ref = {'title': ref_title, 'year': ref_year, 'imdb': ref_imdb, 'search_score': r.get('search_score', 0)}


                k_exact = _key(processed_ref.get("title"), processed_ref.get("year"))
                k_title = _key(processed_ref.get("title"), 0)
                cand = (idx_ty.get(k_exact) or idx_t.get(k_title) or [])
                meta = cand[0] if cand else None

                resolved_item = None
                if meta:
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
                    meta['list_item_id'] = r.get('list_item_id') # from original row
                    from resources.lib.listitem_builder import ListItemBuilder
                    list_item = ListItemBuilder.build_video_item(meta, is_search_history=is_search_history)
                    resolved_items_for_list.append((list_item, meta.get('file', ''), meta))
                else:
                    # No Kodi match found - using fallback data
                    fallback_title = processed_ref.get("title") or 'Unknown Title'
                    utils.log(f"Item {i+1}: No Kodi match for '{processed_ref.get('title')}' ({processed_ref.get('year')}), using fallback title: '{fallback_title}'", "WARNING")
                    resolved_item = {
                        'id': r.get('id'), # from original row
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
                        'list_item_id': r.get('list_item_id') # from original row
                    }
                    from resources.lib.listitem_builder import ListItemBuilder
                    list_item = ListItemBuilder.build_video_item(resolved_item, is_search_history=is_search_history)
                    resolved_items_for_list.append((list_item, resolved_item.get('file', ''), resolved_item))


            # Sort external items by search score as well if they have scores
            external_sorted = sorted(external, key=lambda x: x.get('search_score', 0), reverse=True)
            for item in external_sorted:

            # Sort external items by search score as well if they have scores
            external_sorted = sorted(external, key=lambda x: x.get('search_score', 0), reverse=True)
            for item in external_sorted:
                from resources.lib.listitem_builder import ListItemBuilder
                list_item = ListItemBuilder.build_video_item(item, is_search_history=is_search_history)
                resolved_items_for_list.append((list_item, item.get('file', ''), item))

            build_time = time.time() - batch_start
            total_time = time.time() - start_time
            utils.log(f"[LIST BUILD] Item building completed in {build_time:.3f}s", "DEBUG")
            utils.log(f"[LIST BUILD] Total list build time: {total_time:.3f}s for {len(resolved_items_for_list)} items", "INFO")
            utils.log(f"[LIST BUILD] Performance breakdown - fetch: {fetch_time:.3f}s, jsonrpc: {jsonrpc_time:.3f}s, build: {build_time:.3f}s", "INFO")
            
            return resolved_items_for_list
        except Exception as e:
            total_time = time.time() - start_time
            utils.log(f"[LIST BUILD] Error after {total_time:.3f}s in build_display_items_for_list: {e}", "ERROR")
            import traceback
            utils.log(f"[LIST BUILD] Build exception traceback: {traceback.format_exc()}", "ERROR")
            return []