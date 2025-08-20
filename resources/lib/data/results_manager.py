import json
from resources.lib.integrations.jsonrpc.jsonrpc_manager import JSONRPC
from resources.lib.utils import utils
from resources.lib.utils.singleton_base import Singleton

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

    def _get_light_movies_batch(self, title_year_pairs):
        """Light JSON-RPC batch lookup without heavy fields"""
        if not title_year_pairs:
            return {"result": {"movies": []}}

        try:
            utils.log(f"=== LIGHT_JSONRPC: Starting light batch lookup for {len(title_year_pairs)} pairs ===", "INFO")

            # Use only light properties for fast response
            properties = self.jsonrpc.get_light_properties()
            utils.log(f"=== LIGHT_JSONRPC: Using {len(properties)} light properties ===", "INFO")

            # Build OR filter for all title-year combinations
            filter_conditions = []
            for pair in title_year_pairs:
                title = (pair.get('title') or '').strip()
                year = pair.get('year') or 0

                if not title:
                    continue

                if year and str(year).isdigit():
                    # AND condition for both title and year
                    and_condition = [
                        {
                            'field': 'title',
                            'operator': 'is',
                            'value': title
                        },
                        {
                            'field': 'year',
                            'operator': 'is',
                            'value': str(year)
                        }
                    ]
                    filter_conditions.append(and_condition)
                else:
                    # Just title condition
                    title_condition = [
                        {
                            'field': 'title',
                            'operator': 'is',
                            'value': title
                        }
                    ]
                    filter_conditions.append(title_condition)

            if not filter_conditions:
                utils.log("LIGHT_JSONRPC: No valid filter conditions created", "WARNING")
                return {"result": {"movies": []}}

            # Create the proper Kodi JSON-RPC filter structure
            if len(filter_conditions) == 1:
                if len(filter_conditions[0]) == 1:
                    search_filter = filter_conditions[0][0]
                else:
                    search_filter = {
                        'and': filter_conditions[0]
                    }
            else:
                or_list = []
                for condition_group in filter_conditions:
                    if len(condition_group) == 1:
                        or_list.append(condition_group[0])
                    else:
                        or_list.append({
                            'and': condition_group
                        })

                search_filter = {
                    'or': or_list
                }

            utils.log(f"LIGHT_JSONRPC: Built OR filter with {len(filter_conditions)} conditions", "INFO")

            response = self.jsonrpc.execute('VideoLibrary.GetMovies', {
                'properties': properties,
                'filter': search_filter
            })

            if 'result' in response and 'movies' in response['result']:
                light_movies = response['result']['movies']
                utils.log(f"=== LIGHT_JSONRPC: SUCCESS - Got {len(light_movies)} light movies ===", "INFO")
                return {"result": {"movies": light_movies, "limits": response['result'].get('limits', {})}}
            else:
                utils.log("LIGHT_JSONRPC: No movies found in response", "INFO")
                return {"result": {"movies": []}}

        except Exception as e:
            utils.log(f"=== LIGHT_JSONRPC: ERROR - {str(e)} ===", "ERROR")
            return {"result": {"movies": []}}

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

                # Use stored data as primary source - it contains the actual movie information
                title = r.get('title', '').strip() if r.get('title') else ''
                year = 0
                try:
                    year = int(r.get('year') or 0)
                except Exception:
                    year = 0

                utils.log(f"Using stored metadata: title='{title}', year={year}", "DEBUG")

                # Only try imdb_exports as enhancement if we have missing data
                if (not title or title in ['Unknown', '']) and imdb:
                    utils.log(f"=== TITLE_YEAR_LOOKUP: Enhancing from imdb_exports for IMDB {imdb} ===", "DEBUG")
                    try:
                        q = """SELECT title, year FROM imdb_exports WHERE imdb_id = ? ORDER BY id DESC LIMIT 1"""
                        hit = self.query_manager.execute_query(q, (imdb,)) or []
                        if hit:
                            rec = hit[0]
                            export_title = (rec.get('title') if isinstance(rec, dict) else rec[0]) or ''
                            export_year = int((rec.get('year') if isinstance(rec, dict) else rec[1]) or 0)
                            if export_title and export_title not in ['Unknown', '']:
                                title = export_title
                                utils.log(f"Enhanced title from imdb_exports: {title}", "DEBUG")
                            if export_year > 0 and year == 0:
                                year = export_year
                                utils.log(f"Enhanced year from imdb_exports: {year}", "DEBUG")
                        else:
                            utils.log(f"=== TITLE_YEAR_LOOKUP: No imdb_exports entry found for IMDB {imdb} ===", "DEBUG")
                    except Exception as e:
                        utils.log(f"=== TITLE_YEAR_LOOKUP: Error querying imdb_exports for {imdb}: {str(e)} ===", "ERROR")

                # Final fallback only if we still have no useful title
                if not title or title.strip() == '':
                    title = f"IMDB: {imdb}" if imdb else "Unknown Movie"
                    utils.log(f"Using final fallback title: {title}", "WARNING")

                refs.append({'imdb': imdb, 'title': title, 'year': year, 'search_score': r.get('search_score', 0)})

            # ---- Step 1: Light JSON-RPC batch call (avoiding heavy fields) ----
            batch_pairs = []
            for r in rows:
                # Extract reference data for matching - use actual stored values
                ref_title = r.get('title')
                ref_year = r.get('year') 
                ref_imdb = r.get('imdbnumber')

                # Log what we actually have in the database
                if not ref_title:
                    utils.log(f"Item {len(batch_pairs)+1}: No title in database, using fallback", "DEBUG")
                    ref_title = "Unknown"
                else:
                    utils.log(f"Item {len(batch_pairs)+1}: Found title in database: '{ref_title}'", "DEBUG")

                if not ref_year or ref_year == 0:
                    utils.log(f"Item {len(batch_pairs)+1}: No year in database, using fallback", "DEBUG") 
                    ref_year = 0
                else:
                    utils.log(f"Item {len(batch_pairs)+1}: Found year in database: {ref_year}", "DEBUG")

                batch_pairs.append({
                    'title': ref_title,
                    'year': ref_year
                })

            utils.log(f"=== BUILD_DISPLAY_ITEMS: Making LIGHT JSON-RPC batch call for {len(batch_pairs)} pairs ===", "DEBUG")
            utils.log(f"=== BUILD_DISPLAY_ITEMS: First 3 batch pairs: {batch_pairs[:3]} ===", "DEBUG")

            # Make light JSON-RPC call using the existing batch method but force light mode
            try:
                batch_resp = self._get_light_movies_batch(batch_pairs) or {}
                utils.log(f"=== BUILD_DISPLAY_ITEMS: Light batch response keys: {list(batch_resp.keys()) if batch_resp else 'None'} ===", "DEBUG")
            except Exception as e:
                utils.log(f"=== BUILD_DISPLAY_ITEMS: Light batch lookup failed: {str(e)} ===", "ERROR")
                batch_resp = {}

            light_movies = (batch_resp.get("result") or {}).get("movies") or []
            utils.log(f"=== BUILD_DISPLAY_ITEMS: Light JSON-RPC returned {len(light_movies)} movies ===", "DEBUG")

            # ---- Step 2: Get heavy metadata from cache ----
            movieids = [m.get('movieid') for m in light_movies if m.get('movieid')]
            utils.log(f"=== BUILD_DISPLAY_ITEMS: Fetching heavy fields for {len(movieids)} movies from cache ===", "DEBUG")

            heavy_by_id = {}
            if movieids:
                try:
                    heavy_by_id = self.query_manager._listing.get_heavy_meta_by_movieids(movieids)
                    utils.log(f"=== BUILD_DISPLAY_ITEMS: Retrieved heavy fields for {len(heavy_by_id)} movies from cache ===", "DEBUG")
                except Exception as e:
                    utils.log(f"=== BUILD_DISPLAY_ITEMS: Failed to get heavy fields from cache: {str(e)} ===", "WARNING")

            # ---- Step 3: Merge light + heavy data ----
            merged_count = 0
            for movie in light_movies:
                movieid = movie.get('movieid')
                if movieid and movieid in heavy_by_id:
                    heavy_fields = heavy_by_id[movieid]
                    movie.update(heavy_fields)
                    merged_count += 1
                else:
                    # Add empty values for missing heavy data
                    movie.update({
                        'cast': [],
                        'ratings': {},
                        'showlink': [],
                        'streamdetails': {},
                        'uniqueid': {},
                        'tag': []
                    })

            utils.log(f"=== BUILD_DISPLAY_ITEMS: Merged heavy fields for {merged_count}/{len(light_movies)} movies ===", "DEBUG")
            batch_movies = light_movies

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

                    from resources.lib.kodi.listitem_builder import ListItemBuilder
                    list_item = ListItemBuilder.build_video_item(r, is_search_history=is_search_history)

                    # Use the playable path directly instead of info URL
                    item_url = playable_path
                    display_items.append((item_url, list_item, False))
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
                kodi_movie = cand[0] if cand else None

                utils.log(f"=== BUILD_DISPLAY_ITEMS: Item {i+1}: Found {len(cand)} candidates, kodi_movie exists: {kodi_movie is not None} ===", "DEBUG")

                # Prepare a base dictionary for the item, starting with data from the row (r)
                item_dict = dict(r) # Create a mutable copy

                # Merge library data if found
                if kodi_movie:
                    # Library match found - merge all metadata
                    item_dict.update({
                        'kodi_id': kodi_movie.get('movieid', 0),
                        'is_library_match': True,
                        'file': kodi_movie.get('file', ''),
                        'title': kodi_movie.get('title', item_dict.get('title', '')),
                        'year': kodi_movie.get('year', item_dict.get('year', 0)),
                        'rating': kodi_movie.get('rating', 0.0),
                        'votes': kodi_movie.get('votes', 0),
                        'plot': kodi_movie.get('plot', ''),
                        'tagline': kodi_movie.get('tagline', ''),
                        'genre': kodi_movie.get('genre', []),
                        'director': kodi_movie.get('director', []),
                        'writer': kodi_movie.get('writer', []),
                        'studio': kodi_movie.get('studio', []),
                        'country': kodi_movie.get('country', []),
                        'mpaa': kodi_movie.get('mpaa', ''),
                        'runtime': kodi_movie.get('runtime', 0),
                        'premiered': kodi_movie.get('premiered', ''),
                        'dateadded': kodi_movie.get('dateadded', ''),
                        'thumbnail': kodi_movie.get('thumbnail', ''),
                        'fanart': kodi_movie.get('fanart', ''),
                        'art': kodi_movie.get('art', {}),
                        'trailer': kodi_movie.get('trailer', ''),
                        'userrating': kodi_movie.get('userrating', 0),
                        'top250': kodi_movie.get('top250', 0),
                        'set': kodi_movie.get('set', ''),
                        'setid': kodi_movie.get('setid', 0),
                        'lastplayed': kodi_movie.get('lastplayed', ''),
                        'playcount': kodi_movie.get('playcount', 0),
                        'resume': kodi_movie.get('resume', {}),
                        'originaltitle': kodi_movie.get('originaltitle', ''),
                        'sorttitle': kodi_movie.get('sorttitle', ''),
                        'imdbnumber': kodi_movie.get('imdbnumber', ref_imdb),
                        'uniqueid': kodi_movie.get('uniqueid', {'imdb': ref_imdb}),
                        'cast': kodi_movie.get('cast', []),
                        'ratings': kodi_movie.get('ratings', {}),
                        'streamdetails': kodi_movie.get('streamdetails', {}),
                        'showlink': kodi_movie.get('showlink', []),
                        'tag': kodi_movie.get('tag', [])
                    })

                    # Set proper play URL for library matches
                    file_path = kodi_movie.get('file')
                    if file_path:
                        item_dict['play'] = file_path
                        utils.log(f"Set library file path for search result '{item_dict.get('title')}': {file_path}", "DEBUG")
                    else:
                        # Fallback to search_history protocol for non-playable library matches
                        item_dict['play'] = f"search_history://{imdb_id}"
                        utils.log(f"No file path for library match '{item_dict.get('title')}', using search_history protocol", "DEBUG")
                else:
                    # No Kodi match found, use available data from the row (r) and processed_ref
                    original_title = r.get('title') 
                    original_year = r.get('year')

                    # Log what we're actually using
                    display_title = original_title if original_title else 'Unknown Title'
                    display_year = original_year if original_year else 0

                    item_dict['title'] = display_title
                    item_dict['year'] = display_year
                    item_dict['imdbnumber'] = processed_ref.get('imdb') or item_dict.get('imdbnumber', '')
                    item_dict['search_score'] = processed_ref.get('search_score', 0)
                    item_dict['kodi_id'] = None
                    item_dict['is_library_match'] = False

                    # Set a fallback play URL if no file path is directly available
                    if not item_dict.get('play'):
                        item_dict['play'] = f"info://{item_dict.get('imdbnumber', item_dict.get('id', 'unknown'))}"

                    utils.log(f"Item {i+1}: No Kodi match for '{display_title}' ({display_year}), using search result data - Score: {item_dict['search_score']}", "DEBUG")


                # Add context for list viewing and removal
                item_dict['_viewing_list_id'] = list_id
                item_dict['media_id'] = r.get('id') or r.get('media_id') or item_dict.get('kodi_id') # Use kodi_id if available

                # Ensure IMDb ID is set for uniqueid fallback if not already present
                if not item_dict.get('imdbnumber') and ref_imdb:
                    item_dict['imdbnumber'] = ref_imdb
                    if 'uniqueid' not in item_dict or not item_dict['uniqueid'].get('imdb'):
                        item_dict['uniqueid'] = item_dict.get('uniqueid', {}) # Ensure uniqueid is a dict
                        item_dict['uniqueid']['imdb'] = ref_imdb

                from resources.lib.kodi.listitem_builder import ListItemBuilder
                list_item = ListItemBuilder.build_video_item(item_dict, is_search_history=is_search_history)

                # Determine the appropriate URL for this item
                # Use the 'play' key which is now reliably set
                item_url = item_dict.get('play')
                if not item_url: # Final fallback if 'play' is missing
                    item_url = f"info://{item_dict.get('id', 'unknown')}"

                display_items.append((item_url, list_item, False))


            # External items processed separately with stored metadata
            # Handle None search_score values that can't be compared
            external_sorted = sorted(external, key=lambda x: x.get('search_score') or 0, reverse=True)
            for item in external_sorted:
                # Add context for list viewing and removal
                item['_viewing_list_id'] = list_id
                item['media_id'] = item.get('id') or item.get('media_id')

                from resources.lib.kodi.listitem_builder import ListItemBuilder
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