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

    



    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JSONRPC, cls).__new__(cls)
            utils.log("JSONRPC Manager module initialized", "INFO")
        return cls._instance

    def execute(self, method, params):
        request_data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }
        query_json = json.dumps(request_data)

        # Log all JSON-RPC requests
        utils.log(f"JSONRPC Request: {method}", "INFO")
        # Send JSONRPC request

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

    def find_movie_by_imdb(self, imdb_id, properties=None):
        """Find a movie in Kodi library by IMDb ID with v19 compatibility"""
        try:
            utils.log(f"DEBUG: Starting JSONRPC lookup for IMDB ID: {imdb_id}", "DEBUG")

            # Get version-compatible properties
            properties = properties or self._get_version_compatible_properties()

            # v19 may not support complex filters, so always fetch all movies and filter manually
            if utils.is_kodi_v19():
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

    def search_movies(self, filter_obj: Dict[str, Any], properties=None) -> Dict[str, Any]:
        """Search movies with v19 compatibility"""
        # Get version-compatible properties
        properties = properties or self._get_version_compatible_properties()

        # v19 may not support complex filters
        if utils.is_kodi_v19():
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


    

    def get_movie_details_comprehensive(self, movie_id):
        properties = self.get_comprehensive_properties()
        return self.get_movie_details(movie_id, properties=properties)