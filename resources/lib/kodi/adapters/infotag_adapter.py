"""
InfoTag Adapter for LibraryGenie
Handles InfoTag application with version-specific behavior
"""
import xbmc
import xbmcgui
from typing import List, Dict, Any
from ...data.models import MediaItem, Actor
from ...utils import utils


def apply_infotag(item: MediaItem, list_item: xbmcgui.ListItem) -> None:
    """Apply InfoTag data to ListItem with version-specific handling"""
    try:
        utils.log(f"=== INFOTAG_ADAPTER: Starting for '{item.title}' (type: {item.media_type}) ===", "DEBUG")
        utils.log(f"=== INFOTAG_ADAPTER: Item plot length: {len(item.plot)}, rating: {item.rating} ===", "DEBUG")
        utils.log(f"=== INFOTAG_ADAPTER: Item extras keys: {list(item.extras.keys())[:10]} ===", "DEBUG")

        kodi_version = _get_kodi_version()
        utils.log(f"=== INFOTAG_ADAPTER: Using Kodi version: {kodi_version} ===", "DEBUG")

        if kodi_version >= 20:
            _apply_matrix_plus_infotag(item, list_item)
        else:
            _apply_legacy_infotag(item, list_item)

        utils.log(f"=== INFOTAG_ADAPTER: Completed for '{item.title}' ===", "DEBUG")

    except Exception as e:
        utils.log(f"Error applying InfoTag for '{item.title}': {str(e)}", "ERROR")


def _get_kodi_version() -> str:
    """Get Kodi version for routing to appropriate handlers"""
    try:
        version_string = xbmc.getInfoLabel('System.BuildVersion')
        if version_string:
            major_version = int(version_string.split('.')[0])
            if major_version >= 21:
                return "v21+"
            elif major_version >= 20:
                return "v20"
            elif major_version >= 19:
                return "v19"
        return "v19"  # Default fallback
    except:
        return "v19"  # Safe fallback


def _set_unique_ids(info_tag, item: MediaItem, version: str) -> None:
    """Set unique IDs with version-specific handling"""
    try:
        unique_ids = {}

        if item.imdb and item.imdb.startswith('tt'):
            unique_ids['imdb'] = item.imdb

        if item.tmdb:
            unique_ids['tmdb'] = item.tmdb

        if unique_ids:
            if version in ["v20", "v21+"]:
                info_tag.setUniqueIDs(unique_ids)
            else:
                # v19 fallback
                if item.imdb:
                    info_tag.setIMDBNumber(item.imdb)

    except Exception as e:
        utils.log(f"Error setting unique IDs: {str(e)}", "DEBUG")


def _set_cast(info_tag, cast_list: List[Actor], version: str) -> None:
    """Set cast with version-specific handling"""
    try:
        if not cast_list:
            return

        if version == "v21+":
            # Use xbmcgui.Actor objects for v21+
            actors = []
            for actor in cast_list:
                try:
                    kodi_actor = xbmcgui.Actor(
                        name=actor.name or '',
                        role=actor.role or '',
                        order=actor.order or 0,
                        thumbnail=actor.thumb or ''
                    )
                    actors.append(kodi_actor)
                except Exception as actor_error:
                    utils.log(f"Error creating Actor object: {str(actor_error)}", "DEBUG")
                    continue

            if actors:
                info_tag.setCast(actors)
        else:
            # Use list of dicts for v19/v20
            cast_dicts = []
            for actor in cast_list:
                cast_dict = {
                    'name': actor.name or '',
                    'role': actor.role or '',
                    'order': actor.order or 0
                }
                if actor.thumb:
                    cast_dict['thumbnail'] = actor.thumb
                cast_dicts.append(cast_dict)

            if cast_dicts:
                info_tag.setCast(cast_dicts)

    except Exception as e:
        utils.log(f"Error setting cast: {str(e)}", "DEBUG")


def _set_ratings(info_tag, item: MediaItem, version: str) -> None:
    """Set ratings with version-specific handling"""
    try:
        if not item.rating or item.rating <= 0:
            return

        if version in ["v20", "v21+"]:
            # Use ratings dict for v20+
            ratings = {
                'default': {
                    'rating': item.rating,
                    'votes': item.votes or 0
                }
            }

            # Add IMDb rating if available
            if item.imdb:
                ratings['imdb'] = {
                    'rating': item.rating,
                    'votes': item.votes or 0
                }

            info_tag.setRatings(ratings)
        else:
            # v19 uses individual calls
            info_tag.setRating(item.rating)
            if item.votes:
                info_tag.setVotes(item.votes)

    except Exception as e:
        utils.log(f"Error setting ratings: {str(e)}", "DEBUG")


def _set_stream_details(info_tag, stream_details: Dict[str, Any]) -> None:
    """Set stream details if available"""
    try:
        if not isinstance(stream_details, dict):
            return

        # Video stream details
        video = stream_details.get('video', [])
        if video and isinstance(video, list) and len(video) > 0:
            video_info = video[0]
            if isinstance(video_info, dict):
                if video_info.get('width'):
                    info_tag.addVideoStream(xbmcgui.VideoStreamDetail(
                        width=int(video_info.get('width', 0)),
                        height=int(video_info.get('height', 0)),
                        codec=video_info.get('codec', ''),
                        duration=int(video_info.get('duration', 0))
                    ))

        # Audio stream details
        audio = stream_details.get('audio', [])
        if audio and isinstance(audio, list):
            for audio_info in audio:
                if isinstance(audio_info, dict):
                    info_tag.addAudioStream(xbmcgui.AudioStreamDetail(
                        channels=int(audio_info.get('channels', 0)),
                        codec=audio_info.get('codec', ''),
                        language=audio_info.get('language', '')
                    ))

    except Exception as e:
        utils.log(f"Error setting stream details: {str(e)}", "DEBUG")

def _apply_matrix_plus_infotag(item: MediaItem, list_item: xbmcgui.ListItem) -> None:
    """Apply InfoTag for Kodi 20+ (Matrix and later)"""
    try:
        if item.media_type == 'movie':
            info_tag = list_item.getVideoInfoTag()

            # Basic movie info
            info_tag.setTitle(item.title)
            if item.year > 0:
                info_tag.setYear(item.year)
            if item.plot:
                info_tag.setPlot(item.plot)
            if item.rating > 0:
                info_tag.setRating(item.rating)
            if item.votes > 0:
                info_tag.setVotes(item.votes)
            if item.runtime > 0:
                info_tag.setDuration(item.runtime)
            if item.genres:
                info_tag.setGenres(item.genres)
            if item.studio:
                info_tag.setStudios([item.studio])
            if item.country:
                info_tag.setCountries([item.country])

            # IDs
            if item.imdb:
                info_tag.setIMDBNumber(item.imdb)
            if item.tmdb:
                info_tag.setUniqueIDs({'tmdb': item.tmdb}, 'tmdb')

            # Cast
            if item.cast:
                cast_list = []
                for actor in item.cast:
                    cast_info = xbmc.Actor()
                    cast_info.setName(actor.name)
                    if actor.role:
                        cast_info.setRole(actor.role)
                    if actor.order:
                        cast_info.setOrder(actor.order)
                    if actor.thumb:
                        cast_info.setThumbnail(actor.thumb)
                    cast_list.append(cast_info)
                info_tag.setCast(cast_list)

            # Additional metadata from extras
            if 'director' in item.extras and item.extras['director']:
                directors = item.extras['director']
                if isinstance(directors, str):
                    directors = [d.strip() for d in directors.split('/') if d.strip()]
                elif not isinstance(directors, list):
                    directors = [str(directors)]
                info_tag.setDirectors(directors)

            if 'writer' in item.extras and item.extras['writer']:
                writers = item.extras['writer']
                if isinstance(writers, str):
                    writers = [w.strip() for w in writers.split('/') if w.strip()]
                elif not isinstance(writers, list):
                    writers = [str(writers)]
                info_tag.setWriters(writers)

            if 'tagline' in item.extras and item.extras['tagline']:
                info_tag.setTagLine(item.extras['tagline'])

            if 'mpaa' in item.extras and item.extras['mpaa']:
                info_tag.setMpaa(item.extras['mpaa'])

            if 'premiered' in item.extras and item.extras['premiered']:
                info_tag.setPremiered(item.extras['premiered'])

            if 'dateadded' in item.extras and item.extras['dateadded']:
                info_tag.setDateAdded(item.extras['dateadded'])

            if 'lastplayed' in item.extras and item.extras['lastplayed']:
                info_tag.setLastPlayed(item.extras['lastplayed'])

            if 'playcount' in item.extras and item.extras['playcount']:
                try:
                    playcount = int(item.extras['playcount'])
                    info_tag.setPlaycount(playcount)
                except (ValueError, TypeError):
                    pass

            utils.log(f"=== INFOTAG_ADAPTER: Applied Matrix+ video info for '{item.title}' ===", "DEBUG")

        elif item.media_type == 'folder':
            # For folders, set basic info only
            list_item.setInfo('video', {
                'title': item.title,
                'plot': item.plot or f"Folder: {item.title}"
            })
            utils.log(f"=== INFOTAG_ADAPTER: Applied Matrix+ folder info for '{item.title}' ===", "DEBUG")

    except Exception as e:
        utils.log(f"Error applying Matrix+ InfoTag: {str(e)}", "ERROR")


def _apply_legacy_infotag(item: MediaItem, list_item: xbmcgui.ListItem) -> None:
    """Apply InfoTag for Kodi 19 and earlier (legacy setInfo method)"""
    try:
        info_dict = {
            'title': item.title,
            'plot': item.plot,
            'year': item.year if item.year > 0 else None,
            'rating': item.rating if item.rating > 0 else None,
            'votes': item.votes if item.votes > 0 else None,
            'duration': item.runtime if item.runtime > 0 else None,
            'genre': item.genres,
            'studio': item.studio,
            'country': item.country,
            'imdbnumber': item.imdb
        }

        # Add additional metadata from extras
        if 'director' in item.extras and item.extras['director']:
            info_dict['director'] = item.extras['director']

        if 'writer' in item.extras and item.extras['writer']:
            info_dict['writer'] = item.extras['writer']

        if 'tagline' in item.extras and item.extras['tagline']:
            info_dict['tagline'] = item.extras['tagline']

        if 'mpaa' in item.extras and item.extras['mpaa']:
            info_dict['mpaa'] = item.extras['mpaa']

        if 'premiered' in item.extras and item.extras['premiered']:
            info_dict['premiered'] = item.extras['premiered']

        if 'dateadded' in item.extras and item.extras['dateadded']:
            info_dict['dateadded'] = item.extras['dateadded']

        if 'lastplayed' in item.extras and item.extras['lastplayed']:
            info_dict['lastplayed'] = item.extras['lastplayed']

        if 'playcount' in item.extras and item.extras['playcount']:
            try:
                info_dict['playcount'] = int(item.extras['playcount'])
            except (ValueError, TypeError):
                pass

        # Remove None values
        info_dict = {k: v for k, v in info_dict.items() if v is not None}

        if item.media_type == 'movie':
            list_item.setInfo('video', info_dict)

            # Set cast separately for legacy versions
            if item.cast:
                cast_list = []
                for actor in item.cast:
                    cast_entry = {'name': actor.name}
                    if actor.role:
                        cast_entry['role'] = actor.role
                    if actor.order:
                        cast_entry['order'] = actor.order
                    if actor.thumb:
                        cast_entry['thumbnail'] = actor.thumb
                    cast_list.append(cast_entry)
                list_item.setCast(cast_list)

        elif item.media_type == 'folder':
            list_item.setInfo('video', {
                'title': item.title,
                'plot': item.plot or f"Folder: {item.title}"
            })

        utils.log(f"=== INFOTAG_ADAPTER: Applied legacy video info for '{item.title}' ===", "DEBUG")

    except Exception as e:
        utils.log(f"Error applying legacy InfoTag: {str(e)}", "ERROR")