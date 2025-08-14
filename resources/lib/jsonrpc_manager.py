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
        """
        if not pairs:
            return {"result": {"movies": []}}

        # Kodi boolean filter: {"or": [ {"and":[rule, rule]}, {"and":[...]} ]}
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

        props = properties or [
            "title", "year", "file", "imdbnumber", "uniqueid",
            "genre", "rating", "plot", "cast", "art"
        ]

        # Use the backoff helper so unsupported props don't kill the whole query
        filter_obj = {"or": or_groups}
        limits = {"start": int(start), "end": int(start + max(limit, len(or_groups) + 10))}
        return self._getmovies_with_backoff(properties=props, filter_obj=filter_obj, limits=limits)

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
        
        # Verbose JSONRPC logging - enabled for v19 debugging
        utils.log(f"Executing JSONRPC method: {method}", "DEBUG")
        utils.log(f"RAW JSONRPC REQUEST: {query_json}", "INFO")
        utils.log(f"RAW JSONRPC PARAMS: {json.dumps(params, indent=2)}", "INFO")

        response = xbmc.executeJSONRPC(query_json)
        parsed_response = json.loads(response)

        # Log success/error summary
        if 'error' in parsed_response:
            utils.log(f"JSONRPC {method} failed: {parsed_response['error'].get('message', 'Unknown error')}", "ERROR")
            utils.log(f"DEBUG: Full error response: {parsed_response}", "ERROR")
            # Log the request that caused the error for debugging
            utils.log(f"FAILED REQUEST JSON: {query_json}", "ERROR")
        else:
            # Only log individual GetMovies successes in debug mode
            if method != "VideoLibrary.GetMovies" or utils.is_debug_enabled():
                utils.log(f"JSONRPC {method} completed successfully", "DEBUG")

        # Always log raw responses for debugging v19 issues
        utils.log(f"RAW JSONRPC RESPONSE: {response}", "INFO")

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
        """Find a movie in Kodi library by IMDb ID"""
        try:
            utils.log(f"DEBUG: Starting JSONRPC lookup for IMDB ID: {imdb_id}", "DEBUG")

            # Try multiple search strategies
            strategies = [
                # Strategy 1: Search by uniqueid.imdb
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
                utils.log(f"DEBUG: Strategy {i+1} request: VideoLibrary.GetMovies with {strategy}", "DEBUG")

                response = self.execute('VideoLibrary.GetMovies', {
                    'properties': ['title', 'year', 'movieid', 'imdbnumber', 'uniqueid'],
                    **strategy
                })

                utils.log(f"DEBUG: Strategy {i+1} response: {response}", "DEBUG")

                if 'result' in response and 'movies' in response['result']:
                    movies = response['result']['movies']
                    utils.log(f"DEBUG: Strategy {i+1} found {len(movies)} movies for IMDB ID: {imdb_id}", "DEBUG")

                    if movies:
                        movie = movies[0]  # Take first match
                        utils.log(f"DEBUG: Strategy {i+1} returning movie: {movie}", "DEBUG")
                        return {
                            'title': movie.get('title', ''),
                            'year': movie.get('year', 0),
                            'kodi_id': movie.get('movieid', 0)
                        }

            # If no direct matches, try searching all movies and filtering manually
            utils.log(f"DEBUG: No direct JSONRPC match found, searching all movies for IMDB ID: {imdb_id}", "DEBUG")

            request_params = {
                'properties': ['title', 'year', 'movieid', 'imdbnumber', 'uniqueid']
            }
            utils.log(f"DEBUG: GetMovies request params: {request_params}", "DEBUG")

            response = self.execute('VideoLibrary.GetMovies', request_params)
            utils.log(f"DEBUG: GetMovies response keys: {list(response.keys()) if response else 'None'}", "DEBUG")

            if response and 'result' in response:
                utils.log(f"DEBUG: Response result keys: {list(response['result'].keys()) if 'result' in response else 'No result'}", "DEBUG")

            if 'result' in response and 'movies' in response['result']:
                movies = response['result']['movies']
                utils.log(f"DEBUG: Total movies in library: {len(movies)}", "DEBUG")

                # Show sample of first few movies for debugging
                if movies:
                    sample_movies = movies[:3]
                    for idx, sample in enumerate(sample_movies):
                        utils.log(f"DEBUG: Sample movie {idx+1}: Title='{sample.get('title', 'N/A')}', IMDB='{sample.get('imdbnumber', 'N/A')}', UniqueID={sample.get('uniqueid', {})}", "DEBUG")

                for movie in movies:
                    movie_imdb = movie.get('imdbnumber') or movie.get('uniqueid', {}).get('imdb')
                    if movie_imdb == imdb_id:
                        utils.log(f"DEBUG: Found manual JSONRPC match for IMDB ID: {imdb_id} -> {movie}", "DEBUG")
                        return {
                            'title': movie.get('title', ''),
                            'year': movie.get('year', 0),
                            'kodi_id': movie.get('movieid', 0)
                        }

            utils.log(f"DEBUG: No movie found in Kodi library via JSONRPC for IMDB ID: {imdb_id}", "DEBUG")
            return None

        except Exception as e:
            utils.log(f"ERROR: JSONRPC error finding movie by IMDB ID {imdb_id}: {str(e)}", "ERROR")
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
        payload = {
            "properties": self.DEFAULT_MOVIE_PROPS,
            "filter": filter_obj
        }
        return self.execute("VideoLibrary.GetMovies", payload)

    