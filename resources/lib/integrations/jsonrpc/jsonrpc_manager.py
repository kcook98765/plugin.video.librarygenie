import json
import xbmc
import time
from resources.lib.utils.utils import log
from typing import Dict, Any

class JSONRPC:

    def _extract_invalid_prop_index(self, error_obj):
        """Parse Kodi JSON-RPC 'Invalid params' to get invalid property index (int) or None."""
        try:
            stack = (error_obj or {}).get('error', {}).get('data', {}).get('stack', {})
            msg = stack.get('message') or ''
            import re
            m = re.search(r'index\s+(\d+)', msg)
            return int(m.group(1)) if m else None
        except Exception:
            return None

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JSONRPC, cls).__new__(cls)
            log("JSONRPC Manager module initialized", "INFO")
        return cls._instance

    def execute(self, method, params):
        request_data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }
        query_json = json.dumps(request_data)

        # Log all JSON-RPC requests with details
        log(f"=== JSONRPC REQUEST: {method} ===", "DEBUG")
        log(f"Request params: {params}", "DEBUG")
        log(f"Full request JSON: {json.dumps(request_data, indent=2)}", "DEBUG")

        # Start timing
        start_time = time.time()
        
        # Send JSONRPC request
        response = xbmc.executeJSONRPC(query_json)
        
        # End timing and log execution time
        end_time = time.time()
        execution_time_ms = (end_time - start_time) * 1000
        log(f"=== JSONRPC TIMING: {method} executed in {execution_time_ms:.2f}ms ===", "INFO")

        # Log raw response
        log(f"=== JSONRPC RESPONSE RAW: {method} ===", "DEBUG")
        log(f"Raw response length: {len(response)} chars", "DEBUG")

        parsed_response = json.loads(response)

        # Log parsed response details
        log(f"=== JSONRPC RESPONSE PARSED: {method} ===", "DEBUG")
        if 'result' in parsed_response:
            result = parsed_response['result']
            if isinstance(result, dict):
                log(f"Response result keys: {list(result.keys())}", "DEBUG")
                # Log movie count for movie-related methods
                if method in ['VideoLibrary.GetMovies', 'VideoLibrary.GetMovieDetails']:
                    if 'movies' in result:
                        log(f"Movies returned: {len(result['movies'])}", "DEBUG")
                        if result['movies']:
                            # Log first movie sample with detailed IMDb analysis
                            first_movie = result['movies'][0]
                            log(f"First movie sample keys: {list(first_movie.keys())}", "DEBUG")
                            log(f"First movie title: {first_movie.get('title', 'N/A')}", "DEBUG")


                    elif 'moviedetails' in result:
                        movie = result['moviedetails']
                        log(f"Movie details keys: {list(movie.keys())}", "DEBUG")
                        log(f"Movie title: {movie.get('title', 'N/A')}", "DEBUG")

                        # Detailed IMDb ID logging for movie details
                        imdbnumber = movie.get('imdbnumber', '')
                        uniqueid = movie.get('uniqueid', {})
                        log("=== IMDB_TRACE: JSONRPC GetMovieDetails ===", "INFO")
                        log(f"IMDB_TRACE: imdbnumber field = '{imdbnumber}' (type: {type(imdbnumber)})", "INFO")
                        log(f"IMDB_TRACE: uniqueid field = {uniqueid} (type: {type(uniqueid)})", "INFO")
                        if isinstance(uniqueid, dict):
                            log(f"IMDB_TRACE: uniqueid.imdb = '{uniqueid.get('imdb', 'NOT_FOUND')}'", "INFO")
                        log("=== END IMDB_TRACE ===", "INFO")
            else:
                log(f"Response result type: {type(result)}", "DEBUG")

        # Log errors with full details
        if 'error' in parsed_response:
            log(f"=== JSONRPC ERROR: {method} ===", "ERROR")
            log(f"Error message: {parsed_response['error'].get('message', 'Unknown error')}", "ERROR")
            log(f"Full error response: {parsed_response}", "ERROR")
            log(f"Failed request: {query_json}", "ERROR")
        else:
            log(f"=== JSONRPC SUCCESS: {method} ===", "DEBUG")

        return parsed_response

    def get_movies(self, start=0, limit=50, properties=None):
        if properties is None:
            properties = ["title", "year", "file", "imdbnumber", "uniqueid"]

        return self.execute("VideoLibrary.GetMovies", {
            "properties": properties,
            "limits": {"start": start, "end": start + limit}
        })

    def get_movie_details(self, movie_id, properties=None):
        if properties is None:
            properties = [
                'title', 'genre', 'year', 'director', 'cast', 'plot', 'rating',
                'file', 'thumbnail', 'fanart', 'runtime', 'tagline', 'art',
                'writer', 'imdbnumber', 'premiered', 'mpaa', 'trailer', 'votes',
                'country', 'dateadded', 'studio'
            ]

        return self.execute("VideoLibrary.GetMovieDetails", {
            'movieid': movie_id,
            'properties': properties
        })

    def get_movies_for_export(self, start=0, limit=50):
        response = self.get_movies(start, limit)
        if 'result' in response and 'movies' in response['result']:
            return response['result']['movies'], response['result'].get('limits', {}).get('total', 0)
        return [], 0

    def _get_kodi_version(self):
        """Get Kodi version for version-aware API calls"""
        try:
            response = self.execute("Application.GetProperties", {"properties": ["version"]})
            if 'result' in response and 'version' in response['result']:
                major = response['result']['version'].get('major', 0)
                log(f"Detected Kodi version: {major}", "DEBUG")
                return major
        except Exception as e:
            log(f"Could not detect Kodi version, assuming v20+: {str(e)}", "WARNING")
        return 20  # Default to v20+ behavior

    def _get_version_compatible_properties(self):
        """Get movie properties compatible with current Kodi version"""
        kodi_version = self._get_kodi_version()

        if kodi_version >= 20:
            # v20+ supports uniqueid property
            return ["title", "year", "file", "imdbnumber", "uniqueid"]
        else:
            # v19 and earlier - use only basic properties
            log("Using Kodi v19 compatible properties (no uniqueid)", "DEBUG")
            return ["title", "year", "file", "imdbnumber"]

    def get_movies_with_imdb(self, progress_callback=None):
        """Get all movies from Kodi library with IMDb information and cache heavy fields"""
        log("Getting all movies with IMDb information from Kodi library", "DEBUG")

        # Get comprehensive properties for full scan (includes heavy fields)
        properties = self.get_comprehensive_properties()
        log(f"Using comprehensive properties for full scan: {len(properties)} fields", "DEBUG")

        all_movies = []
        start = 0
        limit = 100
        total_estimated = None
        cached_count = 0

        while True:
            # Update progress if callback provided
            if progress_callback:
                if total_estimated and total_estimated > 0:
                    percent = min(80, int((len(all_movies) / total_estimated) * 80))
                    progress_callback.update(percent, f"Retrieved {len(all_movies)} of {total_estimated} movies (cached {cached_count})...")
                    if progress_callback.iscanceled():
                        break
                else:
                    progress_callback.update(10, f"Retrieved {len(all_movies)} movies (cached {cached_count})...")
                    if progress_callback.iscanceled():
                        break

            response = self.get_movies(start, limit, properties=properties)

            # Log response summary instead of full response
            if 'result' not in response:
                log("JSONRPC GetMovies failed: No 'result' key in response", "DEBUG")
                break

            if 'movies' not in response['result']:
                log("JSONRPC GetMovies failed: No 'movies' key in result", "DEBUG")
                # Check if there are any movies at all
                if 'limits' in response['result']:
                    total = response['result']['limits'].get('total', 0)
                    log(f"Total movies reported by Kodi: {total}", "INFO")
                break

            movies = response['result']['movies']
            total = response['result'].get('limits', {}).get('total', 0)

            # Set total estimate on first batch
            if total_estimated is None and total > 0:
                total_estimated = total

            # Cache heavy fields for each movie in this batch
            batch_cached = 0
            for movie in movies:
                if self.cache_heavy_meta(movie):
                    batch_cached += 1
            cached_count += batch_cached

            # Log summary only every 500 movies to reduce spam
            if start % 500 == 0:
                log(f"JSONRPC GetMovies batch: Got {len(movies)} movies (start={start}, total={total}, cached={batch_cached})", "DEBUG")

            if not movies:
                break

            all_movies.extend(movies)

            # Check if we got fewer movies than requested (end of collection)
            if len(movies) < limit:
                break

            start += limit

        log(f"Retrieved {len(all_movies)} total movies from Kodi library", "INFO")
        log(f"Cached heavy metadata for {cached_count} movies", "INFO")
        return all_movies

    def get_episode_details(self, episode_id, properties=None):
        if properties is None:
            properties = [
                'title', 'plot', 'rating', 'writer', 'firstaired', 'playcount',
                'runtime', 'director', 'season', 'episode', 'originaltitle',
                'showtitle', 'cast', 'streamdetails', 'lastplayed', 'fanart',
                'thumbnail', 'file', 'resume', 'tvshowid', 'dateadded', 'uniqueid', 'art'
            ]

        return self.execute("VideoLibrary.GetEpisodeDetails", {
            'episodeid': episode_id,
            'properties': properties
        })

    def find_movie_by_imdb(self, imdb_id, properties=None):
        """Find a movie in Kodi library by IMDb ID with v19 compatibility"""
        try:
            log(f"DEBUG: Starting JSONRPC lookup for IMDB ID: {imdb_id}", "DEBUG")

            # Get version-compatible properties
            properties = properties or self._get_version_compatible_properties()

            # v19 may not support complex filters, so always fetch all movies and filter manually
            if self._get_kodi_version() < 20:
                log("DEBUG: Using v19 compatible search (manual filtering)", "DEBUG")
                return self._find_movie_by_imdb_v19(imdb_id, properties)

            # v20+ can use more advanced filters
            strategies = [
                # Strategy 1: Search by uniqueid.imdb (v20+ only)
                {
                    'filter': {
                        'field': 'uniqueid',
                        'operator': 'is',
                        'value': imdb_id
                    }
                },
                # Strategy 2: Search by imdbnumber
                {
                    'filter': {
                        'field': 'imdbnumber',
                        'operator': 'is',
                        'value': imdb_id
                    }
                }
            ]

            for i, strategy in enumerate(strategies):
                log(f"DEBUG: Trying JSONRPC strategy {i+1} for IMDB ID: {imdb_id}", "DEBUG")

                try:
                    response = self.execute('VideoLibrary.GetMovies', {
                        'properties': properties,
                        **strategy
                    })

                    if 'result' in response and 'movies' in response['result']:
                        movies = response['result']['movies']
                        log(f"DEBUG: Strategy {i+1} found {len(movies)} movies for IMDB ID: {imdb_id}", "DEBUG")

                        if movies:
                            movie = movies[0]  # Take first match
                            return {
                                'title': movie.get('title', ''),
                                'year': movie.get('year', 0),
                                'kodi_id': movie.get('movieid', 0)
                            }
                except Exception as e:
                    log(f"DEBUG: Strategy {i+1} failed: {str(e)}", "DEBUG")
                    continue

            # Fallback to manual search for both versions
            log(f"DEBUG: Using fallback manual search for IMDB ID: {imdb_id}", "DEBUG")
            return self._find_movie_by_imdb_manual(imdb_id, properties)

        except Exception as e:
            log(f"ERROR: JSONRPC error finding movie by IMDB ID {imdb_id}: {str(e)}", "ERROR")
            return None

    def _find_movie_by_imdb_v19(self, imdb_id, properties):
        """v19-specific movie search using manual filtering"""
        try:
            # Get all movies (v19 has limited filter support)
            response = self.execute('VideoLibrary.GetMovies', {
                'properties': properties
            })

            if 'result' in response and 'movies' in response['result']:
                movies = response['result']['movies']
                log(f"DEBUG: v19 search - got {len(movies)} total movies", "DEBUG")

                for movie in movies:
                    # Streamlined IMDb ID extraction prioritizing most reliable methods
                    imdb_id_found = ''

                    # Primary method: uniqueid.imdb (works consistently across versions)
                    if 'uniqueid' in movie and isinstance(movie.get('uniqueid'), dict):
                        imdb_id_found = movie.get('uniqueid', {}).get('imdb', '')

                    # Secondary method: imdbnumber (only if it's valid tt format)
                    if not imdb_id_found:
                        fallback_id = movie.get('imdbnumber', '')
                        if fallback_id and str(fallback_id).strip().startswith('tt'):
                            imdb_id_found = str(fallback_id).strip()
                        # Note: Numeric IDs are ignored as they're typically TMDB IDs in v19

                    # Clean up IMDb ID format
                    if imdb_id_found:
                        imdb_id_found = str(imdb_id_found).strip()
                        # Remove common prefixes that might be present
                        if imdb_id_found.startswith('imdb://'):
                            imdb_id_found = imdb_id_found[7:]
                        elif imdb_id_found.startswith('http'):
                            # Extract tt number from URLs
                            import re
                            match = re.search(r'tt\d+', imdb_id_found)
                            imdb_id_found = match.group(0) if match else ''

                    if imdb_id_found == imdb_id:
                        log(f"DEBUG: v19 found match for IMDB ID: {imdb_id} -> {movie.get('title', 'N/A')}", "DEBUG")
                        return {
                            'title': movie.get('title', ''),
                            'year': movie.get('year', 0),
                            'kodi_id': movie.get('movieid', 0)
                        }

            log(f"DEBUG: v19 search - no match found for IMDB ID: {imdb_id}", "DEBUG")
            return None

        except Exception as e:
            log(f"ERROR: v19 search failed for IMDB ID {imdb_id}: {str(e)}", "ERROR")
            return None

    def _find_movie_by_imdb_manual(self, imdb_id, properties):
        """Manual search fallback for all versions"""
        try:
            response = self.execute('VideoLibrary.GetMovies', {
                'properties': properties
            })

            if 'result' in response and 'movies' in response['result']:
                movies = response['result']['movies']
                log(f"DEBUG: Manual search - checking {len(movies)} movies", "DEBUG")

                for movie in movies:
                    # Use the same logic as the IMDb upload manager for consistency
                    uniqueid = movie.get('uniqueid', {})
                    imdb_from_uniqueid = uniqueid.get('imdb', '') if isinstance(uniqueid, dict) else ''
                    imdb_from_number = movie.get('imdbnumber', '')

                    # Priority: uniqueid.imdb, then imdbnumber if it starts with 'tt'
                    final_imdb = imdb_from_uniqueid or (imdb_from_number if imdb_from_number.startswith('tt') else '')

                    if final_imdb == imdb_id:
                        log(f"DEBUG: Manual search found match: {movie.get('title', 'N/A')}", "DEBUG")
                        return {
                            'title': movie.get('title', ''),
                            'year': movie.get('year', 0),
                            'kodi_id': movie.get('movieid', 0)
                        }

            log(f"DEBUG: Manual search - no match found for IMDB ID: {imdb_id}", "DEBUG")
            return None

        except Exception as e:
            log(f"ERROR: Manual search failed for IMDB ID {imdb_id}: {str(e)}", "ERROR")
            return None

    # v19+ (API v12) Video.Fields.Movie (must be valid enums)
    # Source: Kodi JSON-RPC API v12 docs
    # https://kodi.wiki/view/JSON-RPC_API/v12
    DEFAULT_MOVIE_PROPS = [
        "title","genre","year","rating","director","trailer","tagline","plot",
        "plotoutline","originaltitle","lastplayed","playcount","writer","studio",
        "mpaa","cast","country","imdbnumber","runtime","set","showlink",
        "streamdetails","top250","votes","fanart","thumbnail","file","sorttitle",
        "resume","setid","dateadded","tag","art","userrating","ratings",
        "premiered","uniqueid"
    ]

    def search_movies(self, filter_obj: Dict[str, Any], properties=None) -> Dict[str, Any]:
        """Search movies with v19 compatibility"""
        # Get version-compatible properties
        properties = properties or self._get_version_compatible_properties()

        # v19 may not support complex filters
        if self._get_kodi_version() < 20:
            log("DEBUG: Using v19 compatible movie search", "DEBUG")
            return self._search_movies_v19(filter_obj, properties)

        # v20+ can use full property set and filters
        try:
            payload = {
                "properties": self.DEFAULT_MOVIE_PROPS,
                "filter": filter_obj
            }
            return self.execute("VideoLibrary.GetMovies", payload)
        except Exception as e:
            log(f"DEBUG: Advanced search failed, using fallback: {str(e)}", "DEBUG")
            return self._search_movies_v19(filter_obj, properties)

    def _search_movies_v19(self, filter_obj: Dict[str, Any], properties):
        """v19-compatible movie search with manual filtering"""
        try:
            # Get all movies first
            all_movies = self.execute("VideoLibrary.GetMovies", {
                "properties": properties
            })

            if 'result' not in all_movies or 'movies' not in all_movies['result']:
                return {"result": {"movies": []}}

            movies = all_movies['result']['movies']
            filtered_movies = []

            # Manual filter application (basic support)
            if 'field' in filter_obj and 'operator' in filter_obj and 'value' in filter_obj:
                field = filter_obj['field']
                operator = filter_obj['operator']
                value = filter_obj['value']

                for movie in movies:
                    movie_value = movie.get(field, '')

                    if operator == 'is' and str(movie_value).lower() == str(value).lower():
                        filtered_movies.append(movie)
                    elif operator == 'contains' and str(value).lower() in str(movie_value).lower():
                        filtered_movies.append(movie)
                    elif operator == 'startswith' and str(movie_value).lower().startswith(str(value).lower()):
                        filtered_movies.append(movie)
            else:
                # If complex filter, return all movies (let caller handle filtering)
                filtered_movies = movies

            return {
                "result": {
                    "movies": filtered_movies,
                    "limits": {
                        "start": 0,
                        "end": len(filtered_movies),
                        "total": len(filtered_movies)
                    }
                }
            }

        except Exception as e:
            log(f"ERROR: v19 movie search failed: {str(e)}", "ERROR")
            return {"result": {"movies": []}}

    def get_comprehensive_properties(self):
        """Get maximum possible property set for current Kodi version with intelligent backoff"""
        # v20+ comprehensive property set - includes all available properties
        # v19 comprehensive property set - includes all v19-compatible properties
        return [
            "title", "genre", "year", "rating", "director", "trailer", "tagline", "plot",
            "plotoutline", "originaltitle", "lastplayed", "playcount", "writer", "studio",
            "mpaa", "cast", "country", "imdbnumber", "runtime", "set", "showlink",
            "streamdetails", "top250", "votes", "fanart", "thumbnail", "file", "sorttitle",
            "resume", "setid", "dateadded", "tag", "art", "userrating", "ratings",
            "premiered", "uniqueid"
        ]

    def get_light_properties(self):
        """Get fast properties excluding heavy fields for batch operations"""
        # Exclude slow fields: cast, ratings, showlink, streamdetails, uniqueid, tag
        return [
            "title", "genre", "year", "rating", "director", "trailer", "tagline", "plot",
            "plotoutline", "originaltitle", "lastplayed", "playcount", "writer", "studio",
            "mpaa", "country", "imdbnumber", "runtime", "set", "top250", "votes", 
            "fanart", "thumbnail", "file", "sorttitle", "resume", "setid", "dateadded", 
            "art", "userrating", "premiered", "movieid"
        ]

    def cache_heavy_meta(self, movie_data):
        """Cache heavy metadata fields for a movie"""
        try:
            movieid = movie_data.get('movieid')
            if not movieid:
                return False
            
            # Import here to avoid circular imports
            from resources.lib.data.query_manager import QueryManager
            from resources.lib.config.config_manager import Config
            query_manager = QueryManager(Config().db_path)
            
            import json
            
            # Extract heavy fields
            imdbnumber = movie_data.get('imdbnumber', '')
            cast_json = json.dumps(movie_data.get('cast', []))
            ratings_json = json.dumps(movie_data.get('ratings', {}))
            showlink_json = json.dumps(movie_data.get('showlink', []))
            stream_json = json.dumps(movie_data.get('streamdetails', {}))
            uniqueid_json = json.dumps(movie_data.get('uniqueid', {}))
            tags_json = json.dumps(movie_data.get('tag', []))
            
            # Cache the heavy fields
            query_manager._listing.upsert_heavy_meta(
                movieid, imdbnumber, cast_json, ratings_json, 
                showlink_json, stream_json, uniqueid_json, tags_json
            )
            
            return True
            
        except Exception as e:
            log(f"Error caching heavy metadata for movie {movieid}: {str(e)}", "ERROR")
            return False




    def get_movie_details_comprehensive(self, movie_id):
        properties = self.get_comprehensive_properties()
        response = self.get_movie_details(movie_id, properties=properties)
        
        # Cache heavy fields if we got a successful response
        if 'result' in response and 'moviedetails' in response['result']:
            movie_data = response['result']['moviedetails']
            # Add movieid if not present (should be there but let's be safe)
            if 'movieid' not in movie_data:
                movie_data['movieid'] = movie_id
            self.cache_heavy_meta(movie_data)
        
        return response

    def get_movies_by_title_year_batch(self, title_year_pairs):
        """Optimized lookup using OR filter for title-year combinations with cached heavy fields"""
        if not title_year_pairs:
            return {"result": {"movies": []}}

        try:
            log(f"=== BATCH JSON-RPC: Starting FAST batch lookup for {len(title_year_pairs)} title/year pairs ===", "INFO")

            # Log sample of what we're looking for
            sample_pairs = title_year_pairs[:3]
            for i, pair in enumerate(sample_pairs):
                log(f"BATCH JSON-RPC: Sample {i+1}: '{pair.get('title', 'N/A')}' ({pair.get('year', 'N/A')})", "INFO")
            if len(title_year_pairs) > 3:
                log(f"BATCH JSON-RPC: ... and {len(title_year_pairs) - 3} more", "INFO")

            # Use light properties for faster response
            properties = self.get_light_properties()
            log(f"BATCH JSON-RPC: Using {len(properties)} light properties (excluding heavy fields)", "INFO")

            # Build OR filter for all title-year combinations using proper Kodi JSON-RPC syntax
            filter_conditions = []
            for pair in title_year_pairs:
                title = (pair.get('title') or '').strip()
                year = pair.get('year') or 0

                if not title:
                    continue

                if year and str(year).isdigit():
                    # AND condition for both title and year - use proper Kodi syntax
                    # NOTE: All values must be strings for Kodi JSON-RPC
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
                    # Just title condition - wrap in array for consistency
                    title_condition = [
                        {
                            'field': 'title',
                            'operator': 'is',
                            'value': title
                        }
                    ]
                    filter_conditions.append(title_condition)

            if not filter_conditions:
                log("BATCH JSON-RPC: No valid filter conditions created", "WARNING")
                return {"result": {"movies": []}}

            # Create the proper Kodi JSON-RPC filter structure
            if len(filter_conditions) == 1:
                # Single condition - use AND if multiple fields, single field if one
                if len(filter_conditions[0]) == 1:
                    search_filter = filter_conditions[0][0]
                else:
                    search_filter = {
                        'and': filter_conditions[0]
                    }
            else:
                # Multiple conditions - use OR with AND subconditions
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

            log(f"BATCH JSON-RPC: Built OR filter with {len(filter_conditions)} conditions", "INFO")
            log("BATCH JSON-RPC: Making FAST JSONRPC call to VideoLibrary.GetMovies", "INFO")

            response = self.execute('VideoLibrary.GetMovies', {
                'properties': properties,
                'filter': search_filter
            })

            if 'result' in response and 'movies' in response['result']:
                light_movies = response['result']['movies']
                log(f"=== BATCH JSON-RPC: Got {len(light_movies)} light movies from fast call ===", "INFO")

                # Step 2: Merge cached heavy fields
                movieids = [m.get('movieid') for m in light_movies if m.get('movieid')]
                log(f"BATCH JSON-RPC: Fetching heavy fields for {len(movieids)} movies from cache", "INFO")

                if movieids:
                    try:
                        # Import here to avoid circular imports
                        from resources.lib.data.query_manager import QueryManager
                        from resources.lib.config.config_manager import Config
                        query_manager = QueryManager(Config().db_path)
                        
                        # Get heavy fields from cache in one DB call
                        heavy_by_id = query_manager._listing.get_heavy_meta_by_movieids(movieids)
                        log(f"BATCH JSON-RPC: Retrieved heavy fields for {len(heavy_by_id)} movies from cache", "INFO")
                        
                        # Merge heavy fields back into light movies
                        merged_count = 0
                        for movie in light_movies:
                            movieid = movie.get('movieid')
                            if movieid and movieid in heavy_by_id:
                                heavy_fields = heavy_by_id[movieid]
                                movie.update(heavy_fields)
                                merged_count += 1
                        
                        log(f"BATCH JSON-RPC: Merged heavy fields for {merged_count}/{len(light_movies)} movies", "INFO")
                        
                    except Exception as e:
                        log(f"BATCH JSON-RPC: Warning - Failed to merge heavy fields: {str(e)}", "WARNING")
                        # Continue with light movies even if heavy field merge fails

                # Log sample matches
                for i, movie in enumerate(light_movies[:3]):
                    has_cast = len(movie.get('cast', [])) > 0
                    has_uniqueid = bool(movie.get('uniqueid', {}))
                    log(f"BATCH JSON-RPC: Match {i+1}: '{movie.get('title', 'N/A')}' ({movie.get('year', 'N/A')}) [cast:{has_cast}, uniqueid:{has_uniqueid}]", "INFO")
                if len(light_movies) > 3:
                    log(f"BATCH JSON-RPC: ... and {len(light_movies) - 3} more matches", "INFO")

                log(f"=== BATCH JSON-RPC: SUCCESS - Completed FAST batch with heavy field merge ===", "INFO")
                return {"result": {"movies": light_movies, "limits": response['result'].get('limits', {})}}
            else:
                log("BATCH JSON-RPC: No movies found in response", "INFO")
                return {"result": {"movies": []}}

        except Exception as e:
            log(f"=== BATCH JSON-RPC: ERROR - {str(e)} ===", "ERROR")
            return {"result": {"movies": []}}