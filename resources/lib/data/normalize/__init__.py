from typing import Dict, Any, List
from ..models import MediaItem, Actor
import json

def from_jsonrpc(payload: Dict[str, Any]) -> MediaItem:
    """Normalize JSON-RPC payload to MediaItem"""
    if not payload:
        return MediaItem()

    # Extract basic info
    item = MediaItem(
        id=payload.get('movieid') or payload.get('episodeid'),
        media_type='movie' if 'movieid' in payload else 'episode',
        title=_clean_text(payload.get('title', '')),
        year=_safe_int(payload.get('year', 0)),
        plot=_clean_text(payload.get('plot', '')),
        runtime=_safe_int(payload.get('runtime', 0)) * 60,  # Convert minutes to seconds
        rating=_safe_float(payload.get('rating', 0.0)),
        votes=_safe_int(payload.get('votes', 0)),
        studio=_clean_text(' / '.join(payload.get('studio', []) if isinstance(payload.get('studio'), list) else [payload.get('studio', '')])),
        country=_clean_text(' / '.join(payload.get('country', []) if isinstance(payload.get('country'), list) else [payload.get('country', '')])),
        play_path=_clean_text(payload.get('file', '')),
        is_folder=False
    )

    # Handle IMDb ID from multiple sources
    item.imdb = _extract_imdb_id(payload)

    # Handle TMDB ID
    uniqueid = payload.get('uniqueid', {})
    if isinstance(uniqueid, dict):
        item.tmdb = str(uniqueid.get('tmdb', ''))

    # Handle genres
    genres = payload.get('genre', [])
    if isinstance(genres, list):
        item.genres = [g.strip() for g in genres if g.strip()]
    elif isinstance(genres, str):
        item.genres = [g.strip() for g in genres.split('/') if g.strip()]

    # Handle art
    art = payload.get('art', {})
    if isinstance(art, dict):
        item.art = {
            'poster': art.get('poster', ''),
            'fanart': art.get('fanart', ''),
            'thumb': art.get('thumb', ''),
            'banner': art.get('banner', ''),
            'landscape': art.get('landscape', '')
        }

    # Handle cast
    cast_data = payload.get('cast', [])
    if isinstance(cast_data, list):
        item.cast = [
            Actor(
                name=_clean_text(actor.get('name', '')),
                role=_clean_text(actor.get('role', '')),
                order=_safe_int(actor.get('order', 0)),
                thumb=_clean_text(actor.get('thumbnail', ''))
            )
            for actor in cast_data
            if actor.get('name')
        ]

    # Handle stream details
    stream_details = payload.get('streamdetails', {})
    if isinstance(stream_details, dict):
        item.stream_details = stream_details

    return item

def from_remote_api(payload: Dict[str, Any]) -> MediaItem:
    """Normalize remote API payload to MediaItem"""
    if not payload:
        return MediaItem()

    item = MediaItem(
        id=payload.get('id'),
        media_type=payload.get('media_type', 'movie'),
        title=_clean_text(payload.get('title', '')),
        year=_safe_int(payload.get('year', 0)),
        plot=_clean_text(payload.get('plot', payload.get('overview', ''))),
        runtime=_safe_int(payload.get('runtime', 0)) * 60,  # Convert minutes to seconds
        rating=_safe_float(payload.get('rating', payload.get('vote_average', 0.0))),
        votes=_safe_int(payload.get('votes', payload.get('vote_count', 0))),
        play_path=_clean_text(payload.get('play_path', payload.get('file', ''))),
        is_folder=payload.get('is_folder', False)
    )

    # Handle IMDb ID
    item.imdb = _clean_text(payload.get('imdb_id', payload.get('imdb', '')))
    item.tmdb = _clean_text(str(payload.get('tmdb_id', payload.get('tmdb', ''))))

    # Handle genres
    genres = payload.get('genres', payload.get('genre', []))
    if isinstance(genres, list):
        item.genres = [g.get('name', g) if isinstance(g, dict) else str(g) for g in genres]
    elif isinstance(genres, str):
        item.genres = [g.strip() for g in genres.split('/') if g.strip()]

    # Handle art - map common API fields
    item.art = {
        'poster': payload.get('poster_path', payload.get('poster', '')),
        'fanart': payload.get('backdrop_path', payload.get('fanart', '')),
        'thumb': payload.get('poster_path', payload.get('thumb', '')),
        'banner': payload.get('banner', ''),
        'landscape': payload.get('backdrop_path', '')
    }

    # Handle production companies as studio
    companies = payload.get('production_companies', [])
    if companies:
        item.studio = ' / '.join([c.get('name', c) if isinstance(c, dict) else str(c) for c in companies[:3]])

    return item

def from_db(row: Dict[str, Any]) -> MediaItem:
    """
    Normalize database row data to MediaItem

    Args:
        row: Database row as dict

    Returns:
        MediaItem with normalized data
    """
    # Extract basic fields
    item_id = _safe_int(row.get('id') or row.get('movieid'))
    media_type = _clean_text(row.get('media_type', 'movie'))
    title = _clean_text(row.get('title', ''))

    # Handle year
    year = _safe_int(row.get('year'))

    # Extract IDs
    imdb = _extract_imdb_id(row)
    tmdb = _clean_text(row.get('tmdb') or row.get('tmdbnumber', ''))

    # Basic metadata
    plot = _clean_text(row.get('plot', ''))
    runtime = _safe_int(row.get('runtime') or row.get('duration'))
    rating = _safe_float(row.get('rating'))
    votes = _safe_int(row.get('votes'))

    # Handle genres
    genres = []
    if row.get('genre'):
        if isinstance(row['genre'], list):
            genres = [_clean_text(g) for g in row['genre']]
        else:
            genres = [g.strip() for g in str(row['genre']).split(',') if g.strip()]

    # Studio/Country  
    studio = _clean_text(row.get('studio', ''))
    country = _clean_text(row.get('country', ''))

    # Handle cast
    cast = []
    if row.get('cast'):
        if isinstance(row['cast'], list):
            cast = [_normalize_actor(actor) for actor in row['cast']]
        elif isinstance(row['cast'], str):
            try:
                import json
                cast_data = json.loads(row['cast'])
                if isinstance(cast_data, list):
                    cast = [_normalize_actor(actor) for actor in cast_data]
            except:
                pass

    # Handle art
    art = {}
    if row.get('art'):
        if isinstance(row['art'], dict):
            art = {k: _clean_text(v) for k, v in row['art'].items() if v}
        elif isinstance(row['art'], str):
            try:
                import json
                art_data = json.loads(row['art'])
                if isinstance(art_data, dict):
                    art = {k: _clean_text(v) for k, v in art_data.items() if v}
            except:
                pass

    # Set default art based on media type if none provided
    if not art:
        if media_type == 'folder':
            art = {
                'icon': 'DefaultFolder.png',
                'thumb': 'DefaultFolder.png'
            }
        elif media_type == 'playlist':
            art = {
                'icon': 'DefaultPlaylist.png', 
                'thumb': 'DefaultPlaylist.png'
            }
        else:
            art = {
                'poster': '',
                'fanart': '',
                'thumb': ''
            }

    # Paths
    play_path = _clean_text(row.get('play_path') or row.get('file') or row.get('path', ''))
    is_folder = bool(row.get('is_folder', media_type in ('folder', 'playlist')))

    # Stream details (placeholder)
    stream_details = {}

    # Context tags and extras
    context_tags = set()
    extras = row.get('extras', {}) if isinstance(row.get('extras'), dict) else {}

    # Sort keys
    sort_keys = {}

    return MediaItem(
        id=item_id,
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
        cast=cast,
        context_tags=context_tags,
        sort_keys=sort_keys,
        extras=extras
    )

def _normalize_actor(actor_data: Dict[str, Any]) -> Actor:
    """Helper to normalize actor data"""
    return Actor(
        name=_clean_text(actor_data.get('name', '')),
        role=_clean_text(actor_data.get('role', '')),
        order=_safe_int(actor_data.get('order', 0)),
        thumb=_clean_text(actor_data.get('thumbnail', ''))
    )


def _clean_text(text: str) -> str:
    """Clean text fields to ensure valid strings"""
    if not text or text in ('None', 'null'):
        return ""
    return str(text).strip()

def _safe_int(value: Any) -> int:
    """Safely convert to int"""
    try:
        return int(float(str(value))) if value else 0
    except (ValueError, TypeError):
        return 0

def _safe_float(value: Any) -> float:
    """Safely convert to float"""
    try:
        return float(str(value)) if value else 0.0
    except (ValueError, TypeError):
        return 0.0

def _extract_imdb_id(payload: Dict[str, Any]) -> str:
    """Extract IMDb ID from various payload formats"""
    # Try direct imdbnumber field
    imdb = payload.get('imdbnumber', '')
    if imdb and str(imdb).startswith('tt'):
        return str(imdb)

    # Try uniqueid dict
    uniqueid = payload.get('uniqueid', {})
    if isinstance(uniqueid, dict):
        imdb = uniqueid.get('imdb', '')
        if imdb and str(imdb).startswith('tt'):
            return str(imdb)

    return ""