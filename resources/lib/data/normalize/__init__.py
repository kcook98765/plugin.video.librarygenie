"""
Data normalization functions for LibraryGenie
Converts raw payloads from different sources into standardized MediaItem objects
"""
from typing import Dict, Any, List, Optional
from ..models import MediaItem, Actor
import json


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
            extras=payload  # Store original payload for additional fields
        )

    except Exception as e:
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
            extras=payload
        )

    except Exception as e:
        return MediaItem(
            id=0,
            media_type='unknown',
            title=str(payload.get('title', 'Error')),
            is_folder=False
        )


def from_db(row: Dict[str, Any]) -> MediaItem:
    """Convert database row to MediaItem"""
    try:
        # Handle different ID sources
        media_id = row.get('id') or row.get('media_id') or row.get('movieid') or 0

        title = row.get('title', 'Unknown')
        year = int(row.get('year', 0)) if str(row.get('year', 0)).isdigit() else 0

        # Handle IMDb ID
        imdb = row.get('imdbnumber', '') or row.get('imdb', '') or row.get('imdb_id', '')

        # Handle TMDb ID
        tmdb = str(row.get('tmdb', '')) or str(row.get('tmdb_id', ''))

        # Plot
        plot = row.get('plot', '')

        # Genres - handle both string and JSON array
        genres = []
        genre_data = row.get('genre', '')
        if isinstance(genre_data, str):
            if genre_data.startswith('['):
                try:
                    genres = json.loads(genre_data)
                except:
                    genres = [g.strip() for g in genre_data.split(',') if g.strip()]
            else:
                genres = [g.strip() for g in genre_data.split(',') if g.strip()]
        elif isinstance(genre_data, list):
            genres = genre_data

        # Cast - handle JSON string
        cast_list = []
        cast_data = row.get('cast', '[]')
        if isinstance(cast_data, str):
            try:
                cast_json = json.loads(cast_data)
                for i, actor in enumerate(cast_json):
                    if isinstance(actor, dict):
                        cast_list.append(Actor(
                            name=actor.get('name', ''),
                            role=actor.get('role', ''),
                            order=actor.get('order', i),
                            thumb=actor.get('thumb', '')
                        ))
            except:
                pass
        elif isinstance(cast_data, list):
            for i, actor in enumerate(cast_data):
                if isinstance(actor, dict):
                    cast_list.append(Actor(
                        name=actor.get('name', ''),
                        role=actor.get('role', ''),
                        order=actor.get('order', i),
                        thumb=actor.get('thumb', '')
                    ))

        # Art - handle JSON string
        art = {}
        art_data = row.get('art', '{}')
        if isinstance(art_data, str):
            try:
                art = json.loads(art_data)
            except:
                pass
        elif isinstance(art_data, dict):
            art = art_data

        # Add individual art fields as fallbacks
        for field in ['thumbnail', 'poster', 'fanart']:
            if row.get(field) and field not in art:
                art[field] = row.get(field)

        # Numeric fields
        runtime = int(row.get('duration', 0) or row.get('runtime', 0)) if str(row.get('duration', 0)).isdigit() else 0
        rating = float(row.get('rating', 0.0))
        votes = int(row.get('votes', 0)) if str(row.get('votes', 0)).isdigit() else 0

        # Playable path
        play_path = row.get('file', '') or row.get('play', '')

        # Folder detection
        is_folder = bool(row.get('is_folder', False)) or bool(row.get('isFolder', False))

        # Stream details
        stream_details = {}
        if row.get('stream_details'):
            if isinstance(row.get('stream_details'), str):
                try:
                    stream_details = json.loads(row.get('stream_details'))
                except:
                    pass
            elif isinstance(row.get('stream_details'), dict):
                stream_details = row.get('stream_details')

        # Context tags for list viewing
        context_tags = set()
        if row.get('_viewing_list_id'):
            context_tags.add('in_list')
        if row.get('search_score', 0) > 0:
            context_tags.add('search_result')

        # Sort keys
        sort_keys = {}
        if row.get('search_score'):
            sort_keys['search_score'] = float(row.get('search_score', 0))

        # Determine media type
        media_type = row.get('media_type', 'movie')
        if not media_type or media_type == 'unknown':
            media_type = 'movie'  # Default to movie for rich metadata

        # Additional fields that were missing
        studio = row.get('studio', '')
        country = row.get('country', '')
        extras = dict(row)  # Store original row data

        # Create MediaItem with proper defaults
        media_item = MediaItem(
            id=row.get('id') or row.get('kodi_id') or row.get('movieid'),
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
            stream_details=stream_details,
            play_path=play_path,
            is_folder=is_folder,
            art=art,
            cast=cast_list,
            context_tags=context_tags,
            sort_keys=sort_keys,
            extras=extras
        )

        utils.log(f"=== FROM_DB: Created MediaItem - media_type: '{media_item.media_type}', title: '{media_item.title}' ===", "DEBUG")
        utils.log(f"=== FROM_DB: MediaItem plot length: {len(media_item.plot)}, rating: {media_item.rating} ===", "DEBUG")
        utils.log(f"=== FROM_DB: MediaItem art keys: {list(media_item.art.keys())}, runtime: {media_item.runtime} ===", "DEBUG")
        utils.log(f"=== FROM_DB: MediaItem genres: {media_item.genres}, studio: '{media_item.studio}' ===", "DEBUG")

        return media_item

    except Exception as e:
        return MediaItem(
            id=0,
            media_type='unknown',
            title=str(row.get('title', 'Error')),
            is_folder=False
        )