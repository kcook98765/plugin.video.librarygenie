import json
import xbmc
from resources.lib import utils
from typing import Dict, Any, Optional

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

    def _getmovies_with_backoff(self, properties=None, filter_obj=None, limits=None):
        """Call VideoLibrary.GetMovies while removing unsupported properties on-the-fly."""
        props = list(properties or [])
        # 'movieid' must NOT be in the properties list; it's implicit
        props = [p for p in props if p != 'movieid']
        
        # Build the payload with correct structure
        payload = {"properties": props}
        
        # Add filter if provided - ensure it's a proper dict structure
        if filter_obj and isinstance(filter_obj, dict):
            payload["filter"] = filter_obj
            
        # Add limits if provided - ensure proper integer types
        if limits and isinstance(limits, dict):
            payload["limits"] = {
                "start": int(limits.get("start", 0)),
                "end": int(limits.get("end", 50))
            }

        for _ in range(len(props) + 1):
            resp = self.execute("VideoLibrary.GetMovies", payload)
            if not isinstance(resp, dict) or 'error' not in resp:
                return resp
            idx = self._extract_invalid_prop_index(resp)
            if idx is None:
                return resp
            if 0 <= idx < len(payload.get('properties', [])):
                bad = payload['properties'][idx]
                try:
                    from resources.lib import utils
                    utils.log(f"JSONRPC backoff: removing unsupported property '{bad}'", "WARNING")
                except Exception:
                    pass
                del payload['properties'][idx]
            else:
                return resp
        return resp

    def get_movies_compat(self, properties=None, filter_obj=None, start=0, limit=50):
        """Compatibility wrapper around GetMovies with filters and property backoff."""
        limits = {"start": int(start), "end": int(start + limit)}
        return self._getmovies_with_backoff(properties=properties, filter_obj=filter_obj, limits=limits)

    def get_movie_by_title_year(self, title, year):
        """Resolve a movie via Title+Year using compatible GetMovies calls, then upgrade to details."""
        if not title:
            return None
        base_props = ["title", "year", "imdbnumber", "uniqueid", "file", "art"]
        # 1) Exact AND filter
        filt = {"and": [
            {"field": "title", "operator": "is", "value": title},
            {"field": "year",  "operator": "is", "value": str(year or 0)}
        ]}
        resp = self.get_movies_compat(properties=base_props, filter_obj=filt, start=0, limit=5) or {}
        movies = (resp.get('result') or {}).get('movies') or []
        if movies:
            mid = movies[0].get('movieid')
            if mid is not None:
                det = self.get_movie_details(mid) or {}
                return (det.get('result') or {}).get('moviedetails') or movies[0]
            return movies[0]
        # 2) Title exact, choose closest year
        resp2 = self.get_movies_compat(properties=base_props, filter_obj={"field":"title","operator":"is","value":title}, start=0, limit=25) or {}
        candidates = (resp2.get('result') or {}).get('movies') or []
        if not candidates:
            # 3) Title contains
            resp3 = self.get_movies_compat(properties=base_props, filter_obj={"field":"title","operator":"contains","value":title}, start=0, limit=25) or {}
            candidates = (resp3.get('result') or {}).get('movies') or []
        if not candidates:
            return None
        ty = int(year or 0)
        best = None
        for m in candidates:
            y = int(m.get('year') or 0)
            if ty and y == ty:
                best = m; break
            if ty and abs(y - ty) <= 1 and best is None:
                best = m
        best = best or candidates[0]
        mid = best.get('movieid')
        if mid is not None:
            det = self.get_movie_details(mid) or {}
            return (det.get('result') or {}).get('moviedetails') or best
        return best

    def get_movies_by_title_year_batch(self, pairs, properties=None, start=0, limit=500):
        """
        Resolve many movies in one VideoLibrary.GetMovies using an OR of (title AND year) groups.
        `pairs`: iterable of dicts like {"title": "...", "year": 2024}
        Returns the raw JSON-RPC response (same shape as GetMovies).
        v19 compatibility: Falls back to manual filtering if complex filters fail.
        """
        if not pairs:
            return {"result": {"movies": []}}

        kodi_version = self._get_kodi_version()
        props = properties or self._get_version_compatible_properties()

        # v19 may not support complex boolean filters, use manual filtering
        if kodi_version < 20:
            utils.log("DEBUG: Using v19 compatible batch search (manual filtering)", "DEBUG")
            return self._get_movies_by_title_year_batch_v19(pairs, props, start, limit)

        # v20+ can try advanced filters first
        or_groups = []
        for p in pairs:
            t = (p.get("title") or "").strip()
            y = int(p.get("year") or 0)
            if not t:
                continue
            and_group = [{"field": "title", "operator": "is", "value": t}]
            # Only add year rule if >0; otherwise title-only match
            if y > 0:
                and_group.append({"field": "year", "operator": "is", "value": str(y)})
            or_groups.append({"and": and_group})

        if not or_groups:
            return {"result": {"movies": []}}

        try:
            # Try advanced filter first
            filter_obj = {"or": or_groups}
            limits = {"start": int(start), "end": int(start + max(limit, len(or_groups) + 10))}
            result = self._getmovies_with_backoff(properties=props, filter_obj=filter_obj, limits=limits)
            
            # Check if we got results or errors
            if 'error' not in result and 'result' in result:
                return result
        except Exception as e:
            utils.log(f"DEBUG: Advanced filter failed, using manual filtering: {str(e)}", "DEBUG")

        # Fallback to manual filtering
        return self._get_movies_by_title_year_batch_manual(pairs, props, start, limit)

    def _get_movies_by_title_year_batch_v19(self, pairs, properties, start, limit):
        """v19-specific batch search using manual filtering"""
        try:
            # Get all movies first
            all_movies_response = self.execute('VideoLibrary.GetMovies', {
                'properties': properties,
                'limits': {'start': 0, 'end': 10000}  # Get more movies for manual filtering
            })

            if 'result' not in all_movies_response or 'movies' not in all_movies_response['result']:
                return {"result": {"movies": []}}

            all_movies = all_movies_response['result']['movies']
            matched_movies = []

            # Create lookup for faster matching
            title_year_pairs = set()
            for p in pairs:
                title = (p.get("title") or "").strip().lower()
                year = int(p.get("year") or 0)
                if title:
                    title_year_pairs.add((title, year))

            # Manual filtering
            for movie in all_movies:
                movie_title = (movie.get('title') or '').strip().lower()
                movie_year = int(movie.get('year') or 0)
                
                # Check for exact matches
                if (movie_title, movie_year) in title_year_pairs:
                    matched_movies.append(movie)
                # Also check title-only matches if year is 0 in search
                elif movie_title and (movie_title, 0) in title_year_pairs:
                    matched_movies.append(movie)

            # Apply pagination
            start_idx = max(0, start)
            end_idx = start_idx + limit
            paginated_movies = matched_movies[start_idx:end_idx]

            utils.log(f"DEBUG: v19 batch search found {len(matched_movies)} total matches, returning {len(paginated_movies)}", "DEBUG")

            return {
                "result": {
                    "movies": paginated_movies,
                    "limits": {
                        "start": start,
                        "end": start + len(paginated_movies),
                        "total": len(matched_movies)
                    }
                }
            }

        except Exception as e:
            utils.log(f"ERROR: v19 batch search failed: {str(e)}", "ERROR")
            return {"result": {"movies": []}}

    def _get_movies_by_title_year_batch_manual(self, pairs, properties, start, limit):
        """Manual batch search fallback for all versions"""
        try:
            # Get all movies
            response = self.execute('VideoLibrary.GetMovies', {
                'properties': properties
            })

            if 'result' not in response or 'movies' not in response['result']:
                return {"result": {"movies": []}}

            all_movies = response['result']['movies']
            matched_movies = []

            # Create lookup set for faster matching
            search_criteria = set()
            for p in pairs:
                title = (p.get("title") or "").strip().lower()
                year = int(p.get("year") or 0)
                if title:
                    search_criteria.add((title, year))

            # Filter movies
            for movie in all_movies:
                movie_title = (movie.get('title') or '').strip().lower()
                movie_year = int(movie.get('year') or 0)
                
                if (movie_title, movie_year) in search_criteria or (movie_title, 0) in search_criteria:
                    matched_movies.append(movie)

            # Apply pagination
            start_idx = max(0, start)
            end_idx = start_idx + limit
            paginated_movies = matched_movies[start_idx:end_idx]

            return {
                "result": {
                    "movies": paginated_movies,
                    "limits": {
                        "start": start,
                        "end": start + len(paginated_movies),
                        "total": len(matched_movies)
                    }
                }
            }

        except Exception as e:
            utils.log(f"ERROR: Manual batch search failed: {str(e)}", "ERROR")
            return {"result": {"movies": []}}

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JSONRPC, cls).__new__(cls)
            utils.log("JSONRPC Manager module initialized", "INFO")
        return cls._instance

    def execute(self, method, params):
        query = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }
        query_json = json.dumps(query)
        
        response = xbmc.executeJSONRPC(query_json)
        parsed_response = json.loads(response)

        # Only log errors with full details
        if 'error' in parsed_response:
            utils.log(f"JSONRPC {method} failed: {parsed_response['error'].get('message', 'Unknown error')}", "ERROR")
            utils.log(f"Full error response: {parsed_response}", "ERROR")
            utils.log(f"Failed request: {query_json}", "ERROR")

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
                utils.log(f"Detected Kodi version: {major}", "DEBUG")
                return major
        except Exception as e:
            utils.log(f"Could not detect Kodi version, assuming v20+: {str(e)}", "WARNING")
        return 20  # Default to v20+ behavior

    def _get_version_compatible_properties(self):
        """Get movie properties compatible with current Kodi version"""
        kodi_version = self._get_kodi_version()
        
        if kodi_version >= 20:
            # v20+ supports uniqueid property
            return ["title", "year", "file", "imdbnumber", "uniqueid"]
        else:
            # v19 and earlier - use only basic properties
            utils.log("Using Kodi v19 compatible properties (no uniqueid)", "DEBUG")
            return ["title", "year", "file", "imdbnumber"]

    def get_movies_with_imdb(self, progress_callback=None):
        """Get all movies from Kodi library with IMDb information"""
        utils.log("Getting all movies with IMDb information from Kodi library", "DEBUG")

        # Get version-compatible properties
        properties = self._get_version_compatible_properties()
        utils.log(f"Using properties for this Kodi version: {properties}", "DEBUG")

        all_movies = []
        start = 0
        limit = 100
        total_estimated = None

        while True:
            # Update progress if callback provided
            if progress_callback:
                if total_estimated and total_estimated > 0:
                    percent = min(80, int((len(all_movies) / total_estimated) * 80))
                    progress_callback.update(percent, f"Retrieved {len(all_movies)} of {total_estimated} movies...")
                    if progress_callback.iscanceled():
                        break
                else:
                    progress_callback.update(10, f"Retrieved {len(all_movies)} movies...")
                    if progress_callback.iscanceled():
                        break

            response = self.get_movies(start, limit, properties=properties)

            # Log response summary instead of full response
            if 'result' not in response:
                utils.log("JSONRPC GetMovies failed: No 'result' key in response", "DEBUG")
                break

            if 'movies' not in response['result']:
                utils.log("JSONRPC GetMovies failed: No 'movies' key in result", "DEBUG")
                # Check if there are any movies at all
                if 'limits' in response['result']:
                    total = response['result']['limits'].get('total', 0)
                    utils.log(f"Total movies reported by Kodi: {total}", "INFO")
                break

            movies = response['result']['movies']
            total = response['result'].get('limits', {}).get('total', 0)

            # Set total estimate on first batch
            if total_estimated is None and total > 0:
                total_estimated = total

            # Log summary every 500 movies or in debug mode
            if start % 500 == 0 or len(movies) < limit or utils.is_debug_enabled():
                utils.log(f"JSONRPC GetMovies batch: Got {len(movies)} movies (start={start}, total={total})", "DEBUG")

            if not movies:
                break

            all_movies.extend(movies)

            # Check if we got fewer movies than requested (end of collection)
            if len(movies) < limit:
                break

            start += limit

        utils.log(f"Retrieved {len(all_movies)} total movies from Kodi library", "INFO")
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

    def find_movie_by_imdb(self, imdb_id):
        """Find a movie in Kodi library by IMDb ID with v19 compatibility"""
        try:
            utils.log(f"DEBUG: Starting JSONRPC lookup for IMDB ID: {imdb_id}", "DEBUG")
            kodi_version = self._get_kodi_version()

            # Get version-compatible properties
            properties = self._get_version_compatible_properties()
            
            # v19 has limited filter support, so always fetch all movies and filter manually
            if kodi_version < 20:
                utils.log("DEBUG: Using v19 compatible search (manual filtering)", "DEBUG")
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
                utils.log(f"DEBUG: Trying JSONRPC strategy {i+1} for IMDB ID: {imdb_id}", "DEBUG")
                
                try:
                    response = self.execute('VideoLibrary.GetMovies', {
                        'properties': properties,
                        **strategy
                    })

                    if 'result' in response and 'movies' in response['result']:
                        movies = response['result']['movies']
                        utils.log(f"DEBUG: Strategy {i+1} found {len(movies)} movies for IMDB ID: {imdb_id}", "DEBUG")

                        if movies:
                            movie = movies[0]  # Take first match
                            return {
                                'title': movie.get('title', ''),
                                'year': movie.get('year', 0),
                                'kodi_id': movie.get('movieid', 0)
                            }
                except Exception as e:
                    utils.log(f"DEBUG: Strategy {i+1} failed: {str(e)}", "DEBUG")
                    continue

            # Fallback to manual search for both versions
            utils.log(f"DEBUG: Using fallback manual search for IMDB ID: {imdb_id}", "DEBUG")
            return self._find_movie_by_imdb_manual(imdb_id, properties)

        except Exception as e:
            utils.log(f"ERROR: JSONRPC error finding movie by IMDB ID {imdb_id}: {str(e)}", "ERROR")
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
                utils.log(f"DEBUG: v19 search - got {len(movies)} total movies", "DEBUG")

                for movie in movies:
                    # Check imdbnumber field (contains TMDB ID in v19)
                    movie_imdb_number = movie.get('imdbnumber', '')
                    
                    # Check uniqueid.imdb if available (contains real IMDb ID in v19)
                    uniqueid = movie.get('uniqueid', {})
                    movie_imdb_unique = uniqueid.get('imdb', '') if isinstance(uniqueid, dict) else ''
                    
                    # Priority: uniqueid.imdb first (real IMDb ID), then imdbnumber if it starts with 'tt'
                    movie_imdb = None
                    if movie_imdb_unique and movie_imdb_unique.startswith('tt'):
                        movie_imdb = movie_imdb_unique
                    elif movie_imdb_number and movie_imdb_number.startswith('tt'):
                        movie_imdb = movie_imdb_number

                    if movie_imdb == imdb_id:
                        utils.log(f"DEBUG: v19 found match for IMDB ID: {imdb_id} -> {movie.get('title', 'N/A')}", "DEBUG")
                        return {
                            'title': movie.get('title', ''),
                            'year': movie.get('year', 0),
                            'kodi_id': movie.get('movieid', 0)
                        }

            utils.log(f"DEBUG: v19 search - no match found for IMDB ID: {imdb_id}", "DEBUG")
            return None

        except Exception as e:
            utils.log(f"ERROR: v19 search failed for IMDB ID {imdb_id}: {str(e)}", "ERROR")
            return None

    def _find_movie_by_imdb_manual(self, imdb_id, properties):
        """Manual search fallback for all versions"""
        try:
            response = self.execute('VideoLibrary.GetMovies', {
                'properties': properties
            })

            if 'result' in response and 'movies' in response['result']:
                movies = response['result']['movies']
                utils.log(f"DEBUG: Manual search - checking {len(movies)} movies", "DEBUG")

                for movie in movies:
                    # Use the same logic as the IMDb upload manager for consistency
                    uniqueid = movie.get('uniqueid', {})
                    imdb_from_uniqueid = uniqueid.get('imdb', '') if isinstance(uniqueid, dict) else ''
                    imdb_from_number = movie.get('imdbnumber', '')
                    
                    # Priority: uniqueid.imdb, then imdbnumber if it starts with 'tt'
                    final_imdb = imdb_from_uniqueid or (imdb_from_number if imdb_from_number.startswith('tt') else '')
                    
                    if final_imdb == imdb_id:
                        utils.log(f"DEBUG: Manual search found match: {movie.get('title', 'N/A')}", "DEBUG")
                        return {
                            'title': movie.get('title', ''),
                            'year': movie.get('year', 0),
                            'kodi_id': movie.get('movieid', 0)
                        }

            utils.log(f"DEBUG: Manual search - no match found for IMDB ID: {imdb_id}", "DEBUG")
            return None

        except Exception as e:
            utils.log(f"ERROR: Manual search failed for IMDB ID {imdb_id}: {str(e)}", "ERROR")
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

    def search_movies(self, filter_obj: Dict[str, Any]) -> Dict[str, Any]:
        """Search movies with v19 compatibility"""
        kodi_version = self._get_kodi_version()
        properties = self._get_version_compatible_properties()
        
        # v19 may not support complex filters
        if kodi_version < 20:
            utils.log("DEBUG: Using v19 compatible movie search", "DEBUG")
            return self._search_movies_v19(filter_obj, properties)
        
        # v20+ can use full property set and filters
        try:
            payload = {
                "properties": self.DEFAULT_MOVIE_PROPS,
                "filter": filter_obj
            }
            return self.execute("VideoLibrary.GetMovies", payload)
        except Exception as e:
            utils.log(f"DEBUG: Advanced search failed, using fallback: {str(e)}", "DEBUG")
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
            utils.log(f"ERROR: v19 movie search failed: {str(e)}", "ERROR")
            return {"result": {"movies": []}}

    