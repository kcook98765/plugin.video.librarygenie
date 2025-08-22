import json
from resources.lib.integrations.jsonrpc.jsonrpc_manager import JSONRPC
from resources.lib.utils import utils
from resources.lib.utils.singleton_base import Singleton
from resources.lib.data.query_manager import QueryManager
from resources.lib.config.config_manager import Config

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

                # Log first movie's complete light data
                if light_movies:
                    first_movie = light_movies[0]
                    utils.log(f"=== JSONRPC_LIGHT_DATA: First movie complete light data ===", "INFO")
                    for key, value in first_movie.items():
                        utils.log(f"JSONRPC_LIGHT_DATA: {key} = {repr(value)}", "INFO")
                    utils.log(f"=== END JSONRPC_LIGHT_DATA ===", "INFO")

                return {"result": {"movies": light_movies, "limits": response['result'].get('limits', {})}}
            else:
                utils.log("LIGHT_JSONRPC: No movies found in response", "INFO")
                utils.log(f"LIGHT_JSONRPC: Full response structure: {response}", "INFO")
                return {"result": {"movies": []}}

        except Exception as e:
            utils.log(f"=== LIGHT_JSONRPC: ERROR - {str(e)} ===", "ERROR")
            return {"result": {"movies": []}}

    def build_display_items_for_list(self, list_id, handle):
        """Build display items for a specific list with proper error handling"""
        try:
            utils.log(f"=== BUILD_DISPLAY_ITEMS: Starting for list_id {list_id} ===", "INFO")

            # Get list items from database
            list_items = self.query_manager.fetch_list_items_with_details(list_id)
            utils.log(f"=== BUILD_DISPLAY_ITEMS: Retrieved {len(list_items)} list items ===", "INFO")

            # Log first item structure for debugging (reduced verbosity)
            if list_items and utils.should_log_debug():
                first_item = list_items[0]
                utils.log(f"First item keys: {list(first_item.keys())}", "DEBUG")
                utils.log(f"Sample: title='{first_item.get('title', 'N/A')}', year={first_item.get('year', 'N/A')}, source='{first_item.get('source', 'N/A')}'", "DEBUG")

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

            # Track data quality issues
            unknown_count = 0
            total_items = len(rows)

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
                    year_val = r.get('year')
                    if year_val and str(year_val).strip() and str(year_val) != 'None':
                        year = int(year_val)
                except (ValueError, TypeError):
                    year = 0

                # Clean up IMDb ID - handle None, empty, or invalid values
                clean_imdb = None
                if imdb and str(imdb).strip() and str(imdb) != 'None':
                    imdb_str = str(imdb).strip()
                    if imdb_str.startswith('tt') and len(imdb_str) > 2:
                        clean_imdb = imdb_str

                # Clean up search score
                search_score = 0
                try:
                    score_val = r.get('search_score')
                    if score_val is not None and str(score_val) != 'None':
                        search_score = float(score_val)
                except (ValueError, TypeError):
                    search_score = 0

                # Track data quality
                if title in ['Unknown', ''] or not title:
                    unknown_count += 1

                utils.log(f"Item {len(refs)+1}: title='{title}', year={year}, imdb='{clean_imdb}', source='{src}', score={search_score}", "DEBUG")

                # Use cleaned data
                final_title = title
                final_year = year

                # Log data quality issues but don't mask them
                if not final_title or final_title.strip() == '':
                    utils.log(f"DATA_QUALITY_ERROR: Item {len(refs)+1} has missing/empty title. IMDB: {clean_imdb}, Source: {src}", "ERROR")
                if final_year == 0:
                    utils.log(f"DATA_QUALITY_WARNING: Item {len(refs)+1} has missing/zero year. Title: {final_title}, IMDB: {clean_imdb}", "WARNING")
                if not clean_imdb:
                    utils.log(f"DATA_QUALITY_WARNING: Item {len(refs)+1} has missing/invalid IMDb ID. Title: {final_title}, Raw IMDB: {repr(imdb)}", "WARNING")

                refs.append({'imdb': clean_imdb, 'title': final_title, 'year': final_year, 'search_score': search_score, 'row_id': r.get('id')})

            # Log data quality summary
            if unknown_count > 0:
                utils.log(f"=== DATA QUALITY WARNING: {unknown_count}/{total_items} items have missing/corrupted titles ===", "WARNING")

            # ---- Step 1: Light JSON-RPC batch call (avoiding heavy fields) ----
            # Create unique batch pairs to avoid duplicate lookups
            unique_pairs = {}
            refs_to_pairs = {}

            for i, ref in enumerate(refs):
                # Use enhanced data from refs instead of raw row data
                ref_title = ref.get('title', '')
                ref_year = ref.get('year', 0)

                # Create a unique key for deduplication
                pair_key = (ref_title.lower().strip(), int(ref_year or 0))

                if pair_key not in unique_pairs:
                    unique_pairs[pair_key] = {
                        'title': ref_title,
                        'year': ref_year
                    }

                # Map this ref to its pair key for later lookup
                refs_to_pairs[i] = pair_key

            batch_pairs = list(unique_pairs.values())
            utils.log(f"=== BUILD_DISPLAY_ITEMS: Reduced {len(refs)} items to {len(batch_pairs)} unique pairs for JSON-RPC ===", "INFO")

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
            utils.log(f"=== BUILD_DISPLAY_ITEMS: Fetching heavy fields for {len(movieids)} movies from cache ===", "INFO")
            utils.log(f"=== HEAVY_CACHE_LOOKUP: MovieIDs to lookup: {movieids} ===", "INFO")

            heavy_by_id = {}
            if movieids:
                try:
                    heavy_by_id = self.query_manager._listing.get_heavy_meta_by_movieids(movieids)
                    utils.log(f"=== BUILD_DISPLAY_ITEMS: Retrieved heavy fields for {len(heavy_by_id)} movies from cache ===", "INFO")

                    # Log heavy data for first movie
                    if heavy_by_id:
                        first_movieid = list(heavy_by_id.keys())[0]
                        first_heavy = heavy_by_id[first_movieid]
                        utils.log(f"=== HEAVY_CACHE_DATA: First movie heavy data (ID {first_movieid}) ===", "INFO")
                        for key, value in first_heavy.items():
                            # Truncate very long JSON strings for readability
                            if isinstance(value, str) and len(value) > 200:
                                utils.log(f"HEAVY_CACHE_DATA: {key} = {value[:200]}... (truncated)", "INFO")
                            else:
                                utils.log(f"HEAVY_CACHE_DATA: {key} = {repr(value)}", "INFO")
                        utils.log(f"=== END HEAVY_CACHE_DATA ===", "INFO")
                    else:
                        utils.log(f"=== HEAVY_CACHE_DATA: No heavy data found for any movieids ===", "ERROR")

                except Exception as e:
                    utils.log(f"=== BUILD_DISPLAY_ITEMS: Failed to get heavy fields from cache: {str(e)} ===", "ERROR")

            # ---- Step 3: Merge light + heavy data ----
            merged_count = 0
            missing_heavy_movieids = []

            for movie in light_movies:
                movieid = movie.get('movieid')
                if movieid and movieid in heavy_by_id:
                    heavy_fields = heavy_by_id[movieid]
                    utils.log(f"MERGE_DATA: Merging heavy fields for movieid {movieid}", "INFO")
                    movie.update(heavy_fields)
                    merged_count += 1
                else:
                    missing_heavy_movieids.append(movieid)
                    utils.log(f"MERGE_DATA: ERROR - No heavy data found for movieid {movieid}", "ERROR")
                    # DO NOT add empty fallback values - let the error be visible
                    # movie.update({
                    #     'cast': [],
                    #     'ratings': {},
                    #     'showlink': [],
                    #     'streamdetails': {},
                    #     'uniqueid': {},
                    #     'tag': []
                    # })

            utils.log(f"=== BUILD_DISPLAY_ITEMS: Merged heavy fields for {merged_count}/{len(light_movies)} movies ===", "INFO")
            if missing_heavy_movieids:
                utils.log(f"=== MERGE_ERROR: Missing heavy data for movieids: {missing_heavy_movieids} ===", "ERROR")
            batch_movies = light_movies

            # Reduced logging for Shield TV performance
            if batch_movies and utils.should_log_debug():
                first_movie = batch_movies[0]
                utils.log(f"=== MERGED_DATA: First movie merged successfully ===", "DEBUG")
                utils.log(f"MERGED_DATA: Keys: {list(first_movie.keys())[:10]}...", "DEBUG")  # Only show first 10 keys
                utils.log(f"=== END MERGED_DATA ===", "DEBUG")

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

            utils.log(f"=== BUILD_DISPLAY_ITEMS: Indexed {len(batch_movies)} movies into {len(idx_ty)} title+year keys and {len(idx_t)} title-only keys ===", "DEBUG")

            # Rebuild resolved list in the original refs order (already sorted by search score from query)
            display_items = []
            utils.log(f"=== BUILD_DISPLAY_ITEMS: Starting movie matching for {len(rows)} items ===", "DEBUG")

            ref_index = 0  # Track which ref we're processing
            for i, r in enumerate(rows):
                # Skip items that are already handled as external
                src = (r.get('source') or '').lower()
                if src in ('external', 'plugin_addon'):
                    continue

                # Handle favorites_import items separately to avoid library lookup
                if src == 'favorites_import':
                    # Check if item has a valid playable path
                    playable_path = r.get('path') or r.get('play') or r.get('file')

                    # Skip items without valid playable paths
                    if not playable_path or not str(playable_path).strip():
                        utils.log(f"Skipping favorites import item '{r.get('title', 'Unknown')}' - no valid playable path", "DEBUG")
                        continue

                    # For favorites imports, use the stored data directly without external processing
                    r['_viewing_list_id'] = list_id
                    r['media_id'] = r.get('id') or r.get('media_id')

                    # Only build ListItem when actually displaying the list (not during sync)
                    # Check if this is being called from a sync operation by looking at the call stack
                    import inspect
                    frame_names = [frame.function for frame in inspect.stack()]
                    is_sync_operation = any(sync_func in frame_names for sync_func in [
                        'sync_favorites', '_apply_database_changes', 'sync_only_store_media_item_to_list'
                    ])
                    
                    if is_sync_operation:
                        utils.log(f"Skipping ListItem building for favorites import item '{r.get('title', 'Unknown')}' during sync operation", "DEBUG")
                        continue

                    from resources.lib.kodi.listitem_builder import ListItemBuilder
                    list_item = ListItemBuilder.build_video_item(r, is_search_history=is_search_history)

                    # Use the playable path directly
                    item_url = playable_path
                    display_items.append((item_url, list_item, False))
                    continue

                # Get the corresponding processed ref data by index
                if ref_index >= len(refs):
                    utils.log(f"=== BUILD_DISPLAY_ITEMS: Item {i+1}: ref_index {ref_index} exceeds refs length {len(refs)} ===", "ERROR")
                    continue

                processed_ref = refs[ref_index]
                ref_index += 1

                ref_title = processed_ref.get("title", "")
                ref_year = processed_ref.get("year", 0)
                ref_imdb = processed_ref.get("imdb")  # Can be None
                row_id = processed_ref.get("row_id", r.get('id'))

                utils.log(f"=== MOVIE_MATCHING: Item {i+1}: ref_title='{ref_title}', ref_year={ref_year}, ref_imdb={repr(ref_imdb)}, row_id={row_id} ===", "INFO")

                k_exact = _key(ref_title, ref_year)
                k_title = _key(ref_title, 0)
                utils.log(f"=== MOVIE_MATCHING: Item {i+1}: Lookup keys - exact: {k_exact}, title: {k_title} ===", "INFO")

                cand = (idx_ty.get(k_exact) or idx_t.get(k_title) or [])
                kodi_movie = cand[0] if cand else None

                utils.log(f"=== MOVIE_MATCHING: Item {i+1}: Found {len(cand)} candidates, kodi_movie exists: {kodi_movie is not None} ===", "INFO")

                if kodi_movie:
                    utils.log(f"=== KODI_MATCH_DATA: Item {i+1} matched to Kodi movie ===", "INFO")
                    for key, value in kodi_movie.items():
                        if isinstance(value, str) and len(value) > 200:
                            utils.log(f"KODI_MATCH_DATA: {key} = {value[:200]}... (truncated)", "INFO")
                        else:
                            utils.log(f"KODI_MATCH_DATA: {key} = {repr(value)}", "INFO")
                    utils.log(f"=== END KODI_MATCH_DATA ===", "INFO")
                else:
                    utils.log(f"=== KODI_MATCH_ERROR: Item {i+1} NO MATCH FOUND in Kodi library ===", "ERROR")

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
                        utils.log(f"Set library file path for search result '{item_dict.get('title')}' : {file_path}", "DEBUG")
                    else:
                        # Fallback to search_history protocol for non-playable library matches
                        item_dict['play'] = f"search_history://{ref_imdb}"
                        utils.log(f"No file path for library match '{item_dict.get('title')}', using search_history protocol", "DEBUG")
                else:
                    # No Kodi match found, use processed ref data
                    display_title = ref_title if ref_title else 'Unknown Title'
                    display_year = ref_year if ref_year else 0

                    item_dict.update({
                        'title': display_title,
                        'year': display_year,
                        'imdbnumber': ref_imdb,
                        'search_score': processed_ref.get('search_score', 0),
                        'kodi_id': None,
                        'is_library_match': False
                    })

                    # Set a fallback play URL if no file path is directly available
                    if not item_dict.get('play'):
                        fallback_id = ref_imdb or row_id or 'unknown'
                        item_dict['play'] = f"info://{fallback_id}"

                    utils.log(f"Item {i+1}: No Kodi match for '{display_title}' ({display_year}), using search result data - Score: {item_dict['search_score']}", "DEBUG")

                # Add unique identification to prevent duplicates in display
                imdb_part = ref_imdb if ref_imdb else 'no_imdb'
                item_dict['_unique_id'] = f"{row_id}_{imdb_part}_{i}"  # Ensure each item is unique
                item_dict['_viewing_list_id'] = list_id
                item_dict['media_id'] = row_id or item_dict.get('kodi_id') # Use row_id for unique identification

                # Ensure IMDb ID is set for uniqueid fallback if not already present
                if not item_dict.get('imdbnumber') and ref_imdb:
                    item_dict['imdbnumber'] = ref_imdb
                    if 'uniqueid' not in item_dict or not item_dict.get('uniqueid', {}).get('imdb'):
                        item_dict['uniqueid'] = item_dict.get('uniqueid', {}) # Ensure uniqueid is a dict
                        item_dict['uniqueid']['imdb'] = ref_imdb

                # Log complete data going to ListItem builder
                utils.log(f"=== LISTITEM_INPUT_DATA: Item {i+1} data for ListItem builder ===", "INFO")
                for key, value in item_dict.items():
                    if isinstance(value, str) and len(value) > 200:
                        utils.log(f"LISTITEM_INPUT_DATA: {key} = {value[:200]}... (truncated)", "INFO")
                    else:
                        utils.log(f"LISTITEM_INPUT_DATA: {key} = {repr(value)}", "INFO")
                utils.log(f"=== END LISTITEM_INPUT_DATA ===", "INFO")

                from resources.lib.kodi.listitem_builder import ListItemBuilder
                list_item = ListItemBuilder.build_video_item(item_dict, is_search_history=is_search_history)

                # Determine the appropriate URL for this item
                # Use the 'play' key which is now reliably set
                item_url = item_dict.get('play')
                if not item_url:
                    utils.log(f"LISTITEM_ERROR: Item {i+1} has no play URL", "ERROR")
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

            if not display_items:
                utils.log(f"No display items found for list {list_id}", "INFO")
                # Create a helpful message item for empty lists
                import xbmcgui
                li = xbmcgui.ListItem("This list is empty")
                li.setInfo('video', {
                    'title': 'This list is empty',
                    'plot': 'This list contains no items yet. You can add items using the Options & Tools menu or import from your Kodi library.'
                })
                # Make it non-playable by not setting a URL
                return [li]

            utils.log(f"=== BUILD_DISPLAY_ITEMS: Created {len(display_items)} display items ===", "DEBUG")
            return display_items

        except Exception as e:
            utils.log(f"Error in build_display_items_for_list: {str(e)}", "ERROR")
            import traceback
            utils.log(f"Traceback: {traceback.format_exc()}", "ERROR")
            return []