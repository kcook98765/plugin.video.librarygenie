"""
Data normalization functions for LibraryGenie
Converts raw payloads from different sources into standardized MediaItem objects
"""
from typing import Dict, Any, List, Optional
from ..models import MediaItem, Actor
import json
# Assuming 'utils' is available in the same directory or accessible path
# from ..utils import log  # Uncomment if utils is available and log is needed


def from_jsonrpc(payload: Dict[str, Any]) -> MediaItem:
    """Convert JSON-RPC payload to MediaItem"""
    try:
        # Extract basic fields
        media_id = payload.get('movieid') or payload.get('id') or 0
        title = payload.get('title') or payload.get('label', 'Unknown')
        year = payload.get('year', 0)

        # Handle IMDb ID from various sources
        imdb = ''
        if isinstance(payload.get('uniqueid'), dict):
            imdb = payload.get('uniqueid', {}).get('imdb', '')
        if not imdb:
            imdb = payload.get('imdbnumber', '')

        # Handle TMDb ID
        tmdb = ''
        if isinstance(payload.get('uniqueid'), dict):
            tmdb = payload.get('uniqueid', {}).get('tmdb', '')

        # Normalize plot
        plot = payload.get('plot', '')
        if plot and len(plot) > 1000:
            plot = plot[:997] + "..."

        # Normalize genres
        genres = payload.get('genre', [])
        if isinstance(genres, str):
            genres = [g.strip() for g in genres.split('/') if g.strip()]
        elif not isinstance(genres, list):
            genres = []

        # Normalize cast
        cast_list = []
        cast_data = payload.get('cast', [])
        if isinstance(cast_data, list):
            for i, actor in enumerate(cast_data):
                if isinstance(actor, dict):
                    cast_list.append(Actor(
                        name=actor.get('name', ''),
                        role=actor.get('role', ''),
                        order=actor.get('order', i),
                        thumb=actor.get('thumbnail', '')
                    ))

        # Normalize art
        art = {}
        if isinstance(payload.get('art'), dict):
            art = payload.get('art', {})

        # Add fallbacks for missing art
        if payload.get('thumbnail') and 'thumb' not in art:
            art['thumb'] = payload.get('thumbnail')
        if payload.get('fanart') and 'fanart' not in art:
            art['fanart'] = payload.get('fanart')

        # Normalize runtime (convert to seconds)
        runtime = payload.get('runtime', 0)
        if isinstance(runtime, str) and runtime.isdigit():
            runtime = int(runtime) * 60  # Assume minutes, convert to seconds
        elif not isinstance(runtime, (int, float)):
            runtime = 0

        # Normalize rating and votes
        rating = float(payload.get('rating', 0.0))
        votes = int(payload.get('votes', 0)) if str(payload.get('votes', 0)).isdigit() else 0

        # Determine playable path
        play_path = payload.get('file', '')
        is_folder = payload.get('filetype') == 'directory' or bool(payload.get('isFolder'))

        # Stream details
        stream_details = payload.get('streamdetails', {})

        # Handle director/writer with enhanced processing
        director = payload.get('director', [])
        if isinstance(director, list):
            director = ' / '.join(str(d) for d in director if d)
        elif director:
            director = str(director)
        else:
            director = ""

        writer = payload.get('writer', [])
        if isinstance(writer, list):
            writer = ' / '.join(str(w) for w in writer if w)
        elif writer:
            writer = str(writer)
        else:
            writer = ""

        # Capture additional metadata fields
        tagline = payload.get('tagline', '')
        set_name = payload.get('set', '')
        premiered = payload.get('premiered', '')
        mpaa = payload.get('mpaa', '')
        trailer = payload.get('trailer', '')

        # Store additional fields in extras for richer display
        extras = {
            'movieid': payload.get('movieid', 0),
            'file': payload.get('file', ''),
            'dateadded': payload.get('dateadded', ''),
            'lastplayed': payload.get('lastplayed', ''),
            'playcount': payload.get('playcount', 0),
            'resume': payload.get('resume', {}),
            'search_score': payload.get('search_score', 0),
            '_viewing_list_id': payload.get('_viewing_list_id'),
            'media_id': payload.get('media_id'),
            'director': director,
            'writer': writer,
            'tagline': tagline,
            'set': set_name,
            'premiered': premiered,
            'mpaa': mpaa,
            'trailer': trailer
        }

        return MediaItem(
            id=media_id,
            media_type='movie',  # JSON-RPC typically deals with movies
            title=title,
            year=year,
            imdb=imdb,
            tmdb=tmdb,
            plot=plot,
            genres=genres,
            runtime=runtime,
            rating=rating,
            votes=votes,
            studio=payload.get('studio', ''),
            country=payload.get('country', ''),
            stream_details=stream_details,
            play_path=play_path,
            is_folder=is_folder,
            art=art,
            cast=cast_list,
            context_tags=set(),
            sort_keys={},
            extras=extras  # Store original payload for additional fields
        )

    except Exception as e:
        # Log the error if utils is available
        # if 'utils' in locals():
        #     utils.log(f"Error converting JSON-RPC payload: {e}", "ERROR")
        # Return minimal MediaItem on error
        return MediaItem(
            id=0,
            media_type='unknown',
            title=str(payload.get('title', 'Error')),
            is_folder=False
        )


def from_remote_api(payload: Dict[str, Any]) -> MediaItem:
    """Convert Remote API payload to MediaItem"""
    try:
        # Remote API typically provides search results
        media_id = payload.get('id') or payload.get('imdb_id', '')
        title = payload.get('title', 'Unknown')
        year = payload.get('year', 0)

        # IMDb from API
        imdb = payload.get('imdb_id', '') or payload.get('imdb', '')
        if imdb and not imdb.startswith('tt'):
            imdb = f"tt{imdb}"

        # TMDb ID
        tmdb = str(payload.get('tmdb_id', '')) or str(payload.get('tmdb', ''))

        # Plot handling
        plot = payload.get('plot', '') or payload.get('overview', '')
        if plot and len(plot) > 1000:
            plot = plot[:997] + "..."

        # Genres from API
        genres = []
        if isinstance(payload.get('genres'), list):
            genres = [g.get('name', g) if isinstance(g, dict) else str(g) for g in payload.get('genres', [])]
        elif isinstance(payload.get('genres'), str):
            genres = [g.strip() for g in payload.get('genres').split(',') if g.strip()]

        # Rating from API (usually 0-10 scale)
        rating = float(payload.get('vote_average', 0) or payload.get('rating', 0))
        votes = int(payload.get('vote_count', 0) or payload.get('votes', 0))

        # Runtime
        runtime = payload.get('runtime', 0)
        if isinstance(runtime, str) and runtime.isdigit():
            runtime = int(runtime) * 60

        # Art from API
        art = {}
        base_url = "https://image.tmdb.org/t/p/w500"

        if payload.get('poster_path'):
            art['poster'] = f"{base_url}{payload.get('poster_path')}"
        if payload.get('backdrop_path'):
            art['fanart'] = f"{base_url}{payload.get('backdrop_path')}"

        # Add search score if available
        search_score = float(payload.get('search_score', 0))

        # Additional fields for extras
        director = payload.get('director', '')
        writer = payload.get('writer', '')
        tagline = payload.get('tagline', '')
        set_name = payload.get('set', '')
        premiered = payload.get('premiered', '')
        mpaa = payload.get('mpaa', '')
        trailer = payload.get('trailer', '')

        extras = {
            'id': payload.get('id'),
            'imdb_id': payload.get('imdb_id'),
            'tmdb_id': payload.get('tmdb_id'),
            'vote_average': payload.get('vote_average'),
            'vote_count': payload.get('vote_count'),
            'search_score': search_score,
            'director': director,
            'writer': writer,
            'tagline': tagline,
            'set': set_name,
            'premiered': premiered,
            'mpaa': mpaa,
            'trailer': trailer,
            'overview': payload.get('overview', '') # Include overview from API
        }

        return MediaItem(
            id=media_id,
            media_type='movie',
            title=title,
            year=year,
            imdb=imdb,
            tmdb=tmdb,
            plot=plot,
            genres=genres,
            runtime=runtime,
            rating=rating,
            votes=votes,
            studio='',
            country='',
            stream_details={},
            play_path='',
            is_folder=False,
            art=art,
            cast=[],
            context_tags=set(),
            sort_keys={'search_score': search_score},
            extras=extras
        )

    except Exception as e:
        # Log the error if utils is available
        # if 'utils' in locals():
        #     utils.log(f"Error converting Remote API payload: {e}", "ERROR")
        return MediaItem(
            id=0,
            media_type='unknown',
            title=str(payload.get('title', 'Error')),
            is_folder=False
        )


def from_db(row: Dict[str, Any]) -> MediaItem:
    """Convert database row to MediaItem"""
    try:
        # Extract basic fields
        media_id = row.get('id') or row.get('media_id') or row.get('movieid') or 0
        title = row.get('title') or row.get('label', 'Unknown')
        year = row.get('year', 0)

        # Handle IMDb ID
        imdb = row.get('imdbnumber') or row.get('imdb') or row.get('imdb_id', '')

        # Handle TMDb ID  
        tmdb = row.get('tmdb') or row.get('tmdb_id', '')

        # Content fields
        plot = row.get('plot') or row.get('plotoutline', '')
        if plot and len(plot) > 1000:
            plot = plot[:997] + "..."

        # Handle genres
        genres = row.get('genre', [])
        if isinstance(genres, str):
            genres = [g.strip() for g in genres.split('/') if g.strip()]
        elif not isinstance(genres, list):
            genres = []

        # Runtime handling
        runtime = 0
        if 'runtime' in row:
            try:
                runtime = int(row['runtime'])
            except (ValueError, TypeError):
                runtime = 0
        elif 'duration' in row:
            try:
                runtime = int(row['duration']) 
            except (ValueError, TypeError):
                runtime = 0

        # Rating
        rating = 0.0
        if 'rating' in row:
            try:
                rating = float(row['rating'])
            except (ValueError, TypeError):
                rating = 0.0

        # Votes
        votes = 0
        if 'votes' in row:
            try:
                votes = int(row['votes'])
            except (ValueError, TypeError):
                votes = 0

        # Other fields
        studio = row.get('studio', '')
        country = row.get('country', '')

        # Art handling - comprehensive extraction
        art = {}
        art_fields = ['poster', 'fanart', 'thumb', 'banner', 'landscape', 'clearart', 'clearlogo', 'icon']
        for field in art_fields:
            if field in row and row[field]:
                art[field] = str(row[field])

        # Handle art as JSON string
        if 'art' in row and row['art']:
            try:
                if isinstance(row['art'], str):
                    art_data = json.loads(row['art'])
                elif isinstance(row['art'], dict):
                    art_data = row['art']
                else:
                    art_data = {}

                if isinstance(art_data, dict):
                    art.update(art_data)
            except (json.JSONDecodeError, TypeError):
                pass

        # Cast handling
        cast_list = []
        if 'cast' in row and row['cast']:
            try:
                if isinstance(row['cast'], str):
                    cast_data = json.loads(row['cast'])
                elif isinstance(row['cast'], list):
                    cast_data = row['cast']
                else:
                    cast_data = []

                for actor in cast_data[:10]:  # Limit to 10 actors
                    if isinstance(actor, dict):
                        cast_list.append(Actor(
                            name=actor.get('name', ''),
                            role=actor.get('role', ''),
                            order=actor.get('order', 0),
                            thumb=actor.get('thumbnail', '')
                        ))
            except (json.JSONDecodeError, TypeError):
                pass

        # Handle director, writer, etc.
        director = row.get('director', '')
        if isinstance(director, list):
            director = ' / '.join(director)

        writer = row.get('writer', '')
        if isinstance(writer, list):
            writer = ' / '.join(writer)

        # Determine if this is a folder
        is_folder = row.get('is_folder', False) or row.get('media_type') == 'folder'

        # Set media type
        media_type = row.get('media_type', 'movie')
        if is_folder and media_type != 'folder':
            media_type = 'folder'

        # Context tags
        context_tags = set()
        if row.get('_viewing_list_id'):
            context_tags.add('in_list')

        # Sort keys
        sort_keys = {}
        if 'search_score' in row:
            try:
                sort_keys['search_score'] = float(row['search_score'])
            except (ValueError, TypeError):
                pass

        # Extras for additional fields
        extras = {}
        for key, value in row.items():
            if key not in ['id', 'media_id', 'movieid', 'title', 'label', 'year', 'imdbnumber', 'imdb', 'imdb_id', 
                          'tmdb', 'tmdb_id', 'plot', 'plotoutline', 'genre', 'runtime', 'duration', 'rating', 
                          'votes', 'studio', 'country', 'art', 'cast', 'director', 'writer', 'is_folder', 
                          'media_type', 'search_score'] and value is not None:
                extras[key] = value

        # Store additional metadata in extras
        if director:
            extras['director'] = director
        if writer:
            extras['writer'] = writer
        if row.get('tagline'):
            extras['tagline'] = row.get('tagline')
        if row.get('mpaa'):
            extras['mpaa'] = row.get('mpaa')
        if row.get('premiered'):
            extras['premiered'] = row.get('premiered')
        if row.get('dateadded'):
            extras['dateadded'] = row.get('dateadded')
        if row.get('lastplayed'):
            extras['lastplayed'] = row.get('lastplayed')
        if row.get('playcount'):
            extras['playcount'] = row.get('playcount')

        return MediaItem(
            id=media_id,
            media_type=media_type,
            title=title,
            year=year,
            imdb=imdb,
            tmdb=tmdb,
            plot=plot,
            genres=genres,
            runtime=runtime,
            rating=rating,
            votes=votes,
            studio=studio,
            country=country,
            stream_details={},
            play_path=row.get('file', ''),
            is_folder=is_folder,
            art=art,
            cast=cast_list,
            context_tags=context_tags,
            sort_keys=sort_keys,
            extras=extras
        )

    except Exception as e:
        # Log the error if utils is available
        # if 'utils' in locals():
        #     utils.log(f"Error converting DB row: {e}", "ERROR")
        # Return minimal MediaItem on error
        return MediaItem(
            id=row.get('id', 0),
            media_type='unknown',
            title=str(row.get('title', 'Error')),
            is_folder=False
        )