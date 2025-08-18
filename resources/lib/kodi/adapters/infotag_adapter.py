"""
InfoTag Adapter for LibraryGenie
Handles InfoTag application with version-specific behavior
"""
import xbmc
import xbmcgui
from typing import List, Dict, Any
from ...data.models import MediaItem, Actor
from ...utils import utils


def apply_infotag(item: MediaItem, li: xbmcgui.ListItem) -> None:
    """Apply InfoTag data to ListItem with version-specific handling"""
    try:
        # Get Kodi version once
        kodi_version = _get_kodi_version()
        utils.log(f"InfoTag adapter using Kodi version path: {kodi_version}", "DEBUG")

        # Get video info tag
        info_tag = li.getVideoInfoTag()

        # Set basic metadata
        if item.title:
            info_tag.setTitle(item.title)

        if item.plot:
            info_tag.setPlot(item.plot)

        if item.year and item.year > 0:
            info_tag.setYear(item.year)

        if item.rating and item.rating > 0:
            info_tag.setRating(item.rating)

        if item.votes and item.votes > 0:
            info_tag.setVotes(item.votes)

        if item.runtime and item.runtime > 0:
            info_tag.setDuration(item.runtime)

        if item.studio:
            info_tag.setStudios([item.studio])

        if item.country:
            info_tag.setCountries([item.country])

        # Set genres
        if item.genres:
            info_tag.setGenres(item.genres)

        # Set media type
        if item.media_type and item.media_type != 'unknown':
            info_tag.setMediaType(item.media_type)

        # Handle unique IDs (version-specific)
        _set_unique_ids(info_tag, item, kodi_version)

        # Handle cast (version-specific)
        _set_cast(info_tag, item.cast, kodi_version)

        # Handle ratings (version-specific)
        _set_ratings(info_tag, item, kodi_version)

        # Handle stream details if available
        if item.stream_details:
            _set_stream_details(info_tag, item.stream_details)

    except Exception as e:
        utils.log(f"Error applying InfoTag for '{item.title}': {str(e)}", "ERROR")
        # Fallback to basic setInfo for compatibility
        try:
            basic_info = {
                'title': item.title,
                'plot': item.plot,
                'year': item.year,
                'rating': item.rating,
                'votes': item.votes,
                'duration': item.runtime,
                'genre': item.genres,
                'studio': item.studio,
                'country': item.country,
                'mediatype': item.media_type
            }
            # Filter out empty values
            basic_info = {k: v for k, v in basic_info.items() if v}
            li.setInfo('video', basic_info)
        except Exception as fallback_error:
            utils.log(f"Fallback InfoTag also failed for '{item.title}': {str(fallback_error)}", "ERROR")


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