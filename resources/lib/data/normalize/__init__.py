
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

def from_db(row: tuple) -> MediaItem:
    """Normalize database row to MediaItem"""
    if not row:
        return MediaItem()
    
    # Map database fields - adjust based on your schema
    field_names = ['id', 'title', 'year', 'plot', 'rating', 'votes', 'runtime', 
                   'genre', 'director', 'writer', 'cast', 'country', 'studio', 
                   'mpaa', 'imdb_id', 'tmdb_id', 'poster', 'fanart', 'thumbnail',
                   'file', 'path', 'media_type', 'search_score']
    
    # Create dict from row
    data = dict(zip(field_names, row))
    
    item = MediaItem(
        id=data.get('id'),
        media_type=data.get('media_type', 'movie'),
        title=_clean_text(data.get('title', '')),
        year=_safe_int(data.get('year', 0)),
        plot=_clean_text(data.get('plot', '')),
        runtime=_safe_int(data.get('runtime', 0)),
        rating=_safe_float(data.get('rating', 0.0)),
        votes=_safe_int(data.get('votes', 0)),
        studio=_clean_text(data.get('studio', '')),
        country=_clean_text(data.get('country', '')),
        play_path=_clean_text(data.get('file', data.get('path', ''))),
        is_folder=False
    )
    
    # Handle IDs
    item.imdb = _clean_text(data.get('imdb_id', ''))
    item.tmdb = _clean_text(str(data.get('tmdb_id', '')))
    
    # Handle genres
    genre_str = data.get('genre', '')
    if genre_str:
        item.genres = [g.strip() for g in genre_str.split('/') if g.strip()]
    
    # Handle art
    item.art = {
        'poster': data.get('poster', ''),
        'fanart': data.get('fanart', ''),
        'thumb': data.get('thumbnail', ''),
        'banner': '',
        'landscape': data.get('fanart', '')
    }
    
    # Handle cast from JSON string
    cast_str = data.get('cast', '')
    if cast_str:
        try:
            cast_data = json.loads(cast_str) if isinstance(cast_str, str) else cast_str
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
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Add search score to extras if present
    search_score = data.get('search_score', 0)
    if search_score:
        item.extras['search_score'] = search_score
    
    return item

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
