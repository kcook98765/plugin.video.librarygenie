
"""
InfoTag Adapter for LibraryGenie
Handles all InfoTag operations with Kodi version-specific behavior
Minimum supported Kodi version: 19 (Matrix)
"""
import xbmc
import xbmcgui
from typing import Dict, Any, List
from ...data.models import MediaItem
from ...utils import utils


def apply_infotag(item: MediaItem, li: xbmcgui.ListItem) -> None:
    """Apply InfoTag data to ListItem with version-specific handling"""
    try:
        # Get Kodi version for routing
        kodi_version = utils.get_kodi_version()
        
        if kodi_version >= 21:
            _apply_infotag_v21(item, li)
        elif kodi_version >= 20:
            _apply_infotag_v20(item, li)
        else:
            _apply_infotag_v19(item, li)
            
        utils.log(f"Applied InfoTag using v{kodi_version} path for '{item.title}'", "DEBUG")
        
    except Exception as e:
        utils.log(f"InfoTag application failed for '{item.title}': {str(e)}", "ERROR")
        # Fallback to basic info
        try:
            li.setInfo('video', {'title': item.title, 'plot': item.plot})
        except Exception:
            pass


def _apply_infotag_v21(item: MediaItem, li: xbmcgui.ListItem) -> None:
    """Apply InfoTag for Kodi v21+ using new Actor objects"""
    info_tag = li.getVideoInfoTag()
    
    # Basic fields
    if item.title:
        info_tag.setTitle(item.title)
    if item.plot:
        info_tag.setPlot(item.plot)
    if item.year:
        info_tag.setYear(item.year)
    if item.runtime:
        info_tag.setDuration(item.runtime)
    if item.rating:
        info_tag.setRating(item.rating)
    if item.votes:
        info_tag.setVotes(item.votes)
    if item.studio:
        info_tag.setStudios([item.studio])
    if item.country:
        info_tag.setCountries([item.country])
    if item.genres:
        info_tag.setGenres(item.genres)
    
    # Media type
    if item.media_type:
        info_tag.setMediaType(item.media_type)
    
    # Unique IDs
    unique_ids = {}
    if item.imdb and item.imdb.startswith('tt'):
        unique_ids['imdb'] = item.imdb
    if item.tmdb:
        unique_ids['tmdb'] = item.tmdb
    if unique_ids:
        info_tag.setUniqueIDs(unique_ids)
    
    # Cast using v21 Actor objects
    if item.cast:
        actors = []
        for actor_data in item.cast:
            try:
                if isinstance(actor_data, dict):
                    actor = xbmcgui.Actor(
                        actor_data.get('name', ''),
                        actor_data.get('role', ''),
                        actor_data.get('order', 0),
                        actor_data.get('thumb', '')
                    )
                    actors.append(actor)
            except Exception as e:
                utils.log(f"Failed to create Actor object: {e}", "WARNING")
                continue
        
        if actors:
            info_tag.setCast(actors)
    
    # Stream details
    if item.stream_details:
        _apply_stream_details_v21(info_tag, item.stream_details)


def _apply_infotag_v20(item: MediaItem, li: xbmcgui.ListItem) -> None:
    """Apply InfoTag for Kodi v20 using InfoTag methods"""
    info_tag = li.getVideoInfoTag()
    
    # Basic fields
    if item.title:
        info_tag.setTitle(item.title)
    if item.plot:
        info_tag.setPlot(item.plot)
    if item.year:
        info_tag.setYear(item.year)
    if item.runtime:
        info_tag.setDuration(item.runtime)
    if item.rating:
        info_tag.setRating(item.rating)
    if item.votes:
        info_tag.setVotes(item.votes)
    if item.studio:
        info_tag.setStudios([item.studio])
    if item.country:
        info_tag.setCountries([item.country])
    if item.genres:
        info_tag.setGenres(item.genres)
    
    # Media type
    if item.media_type:
        info_tag.setMediaType(item.media_type)
    
    # Unique IDs
    unique_ids = {}
    if item.imdb and item.imdb.startswith('tt'):
        unique_ids['imdb'] = item.imdb
    if item.tmdb:
        unique_ids['tmdb'] = item.tmdb
    if unique_ids:
        info_tag.setUniqueIDs(unique_ids)
    
    # Cast using v20 methods
    if item.cast:
        cast_list = []
        for actor_data in item.cast:
            if isinstance(actor_data, dict):
                cast_entry = {
                    'name': actor_data.get('name', ''),
                    'role': actor_data.get('role', ''),
                    'order': actor_data.get('order', 0),
                    'thumb': actor_data.get('thumb', '')
                }
                cast_list.append(cast_entry)
        
        if cast_list:
            try:
                info_tag.setCast(cast_list)
            except Exception as e:
                utils.log(f"Failed to set cast in v20: {e}", "WARNING")
    
    # Stream details
    if item.stream_details:
        _apply_stream_details_v20(info_tag, item.stream_details)


def _apply_infotag_v19(item: MediaItem, li: xbmcgui.ListItem) -> None:
    """Apply InfoTag for Kodi v19 using setInfo method"""
    info_dict = {}
    
    # Basic fields
    if item.title:
        info_dict['title'] = item.title
    if item.plot:
        info_dict['plot'] = item.plot
    if item.year:
        info_dict['year'] = item.year
    if item.runtime:
        info_dict['duration'] = item.runtime
    if item.rating:
        info_dict['rating'] = item.rating
    if item.votes:
        info_dict['votes'] = item.votes
    if item.studio:
        info_dict['studio'] = item.studio
    if item.country:
        info_dict['country'] = item.country
    if item.genres:
        info_dict['genre'] = item.genres
    
    # Media type
    if item.media_type:
        info_dict['mediatype'] = item.media_type
    
    # IMDb ID for v19
    if item.imdb and item.imdb.startswith('tt'):
        info_dict['imdbnumber'] = item.imdb
    
    # Cast for v19
    if item.cast:
        cast_list = []
        for actor_data in item.cast:
            if isinstance(actor_data, dict):
                cast_entry = {
                    'name': actor_data.get('name', ''),
                    'role': actor_data.get('role', ''),
                    'order': actor_data.get('order', 0),
                    'thumb': actor_data.get('thumb', '')
                }
                cast_list.append(cast_entry)
        info_dict['cast'] = cast_list
    
    # Apply the info dict
    li.setInfo('video', info_dict)
    
    # Stream details for v19
    if item.stream_details:
        _apply_stream_details_v19(li, item.stream_details)


def _apply_stream_details_v21(info_tag, stream_details: Dict[str, Any]) -> None:
    """Apply stream details for v21+"""
    try:
        video_streams = stream_details.get('video', [])
        if video_streams and isinstance(video_streams, list):
            for stream in video_streams:
                if isinstance(stream, dict):
                    if stream.get('codec'):
                        info_tag.addVideoStream(stream)
                        break  # Usually only need first video stream
        
        audio_streams = stream_details.get('audio', [])
        if audio_streams and isinstance(audio_streams, list):
            for stream in audio_streams:
                if isinstance(stream, dict):
                    info_tag.addAudioStream(stream)
        
        subtitle_streams = stream_details.get('subtitle', [])
        if subtitle_streams and isinstance(subtitle_streams, list):
            for stream in subtitle_streams:
                if isinstance(stream, dict):
                    info_tag.addSubtitleStream(stream)
                    
    except Exception as e:
        utils.log(f"Failed to apply stream details v21: {e}", "WARNING")


def _apply_stream_details_v20(info_tag, stream_details: Dict[str, Any]) -> None:
    """Apply stream details for v20"""
    try:
        video_streams = stream_details.get('video', [])
        if video_streams and isinstance(video_streams, list):
            for stream in video_streams:
                if isinstance(stream, dict):
                    info_tag.addVideoStream(stream)
                    break  # Usually only need first video stream
        
        audio_streams = stream_details.get('audio', [])
        if audio_streams and isinstance(audio_streams, list):
            for stream in audio_streams:
                if isinstance(stream, dict):
                    info_tag.addAudioStream(stream)
        
        subtitle_streams = stream_details.get('subtitle', [])
        if subtitle_streams and isinstance(subtitle_streams, list):
            for stream in subtitle_streams:
                if isinstance(stream, dict):
                    info_tag.addSubtitleStream(stream)
                    
    except Exception as e:
        utils.log(f"Failed to apply stream details v20: {e}", "WARNING")


def _apply_stream_details_v19(li: xbmcgui.ListItem, stream_details: Dict[str, Any]) -> None:
    """Apply stream details for v19 using deprecated methods"""
    try:
        video_streams = stream_details.get('video', [])
        if video_streams and isinstance(video_streams, list):
            for stream in video_streams:
                if isinstance(stream, dict):
                    try:
                        li.addStreamInfo('video', stream)
                        break  # Usually only need first video stream
                    except Exception:
                        pass
        
        audio_streams = stream_details.get('audio', [])
        if audio_streams and isinstance(audio_streams, list):
            for stream in audio_streams:
                if isinstance(stream, dict):
                    try:
                        li.addStreamInfo('audio', stream)
                    except Exception:
                        pass
        
        subtitle_streams = stream_details.get('subtitle', [])
        if subtitle_streams and isinstance(subtitle_streams, list):
            for stream in subtitle_streams:
                if isinstance(stream, dict):
                    try:
                        li.addStreamInfo('subtitle', stream)
                    except Exception:
                        pass
                        
    except Exception as e:
        utils.log(f"Failed to apply stream details v19: {e}", "WARNING")


# Legacy functions for backward compatibility during migration
def set_info_tag(li: xbmcgui.ListItem, info_dict: Dict[str, Any], content_type: str = 'video') -> None:
    """Legacy function - use apply_infotag with MediaItem instead"""
    utils.log("Using legacy set_info_tag - consider migrating to apply_infotag", "WARNING")
    
    try:
        kodi_version = utils.get_kodi_version()
        
        if kodi_version >= 20:
            # Use InfoTag methods for v20+
            info_tag = li.getVideoInfoTag()
            
            # Map common fields
            if 'title' in info_dict:
                info_tag.setTitle(info_dict['title'])
            if 'plot' in info_dict:
                info_tag.setPlot(info_dict['plot'])
            if 'year' in info_dict:
                info_tag.setYear(info_dict['year'])
            if 'duration' in info_dict:
                info_tag.setDuration(info_dict['duration'])
            if 'rating' in info_dict:
                info_tag.setRating(info_dict['rating'])
            if 'votes' in info_dict:
                info_tag.setVotes(info_dict['votes'])
            if 'genre' in info_dict:
                genres = info_dict['genre'] if isinstance(info_dict['genre'], list) else [info_dict['genre']]
                info_tag.setGenres(genres)
            if 'studio' in info_dict:
                studios = info_dict['studio'] if isinstance(info_dict['studio'], list) else [info_dict['studio']]
                info_tag.setStudios(studios)
            if 'country' in info_dict:
                countries = info_dict['country'] if isinstance(info_dict['country'], list) else [info_dict['country']]
                info_tag.setCountries(countries)
            if 'mediatype' in info_dict:
                info_tag.setMediaType(info_dict['mediatype'])
            
            # Handle unique IDs
            unique_ids = {}
            if 'imdbnumber' in info_dict and info_dict['imdbnumber']:
                unique_ids['imdb'] = info_dict['imdbnumber']
            if 'uniqueid' in info_dict and isinstance(info_dict['uniqueid'], dict):
                unique_ids.update(info_dict['uniqueid'])
            if unique_ids:
                info_tag.setUniqueIDs(unique_ids)
            
            # Handle cast
            if 'cast' in info_dict and info_dict['cast']:
                cast_list = info_dict['cast']
                if kodi_version >= 21:
                    # Use Actor objects for v21+
                    actors = []
                    for cast_member in cast_list:
                        if isinstance(cast_member, dict):
                            try:
                                actor = xbmcgui.Actor(
                                    cast_member.get('name', ''),
                                    cast_member.get('role', ''),
                                    cast_member.get('order', 0),
                                    cast_member.get('thumb', '')
                                )
                                actors.append(actor)
                            except Exception:
                                continue
                    if actors:
                        info_tag.setCast(actors)
                else:
                    # Use dict format for v20
                    info_tag.setCast(cast_list)
        else:
            # Use setInfo for v19
            li.setInfo(content_type, info_dict)
            
    except Exception as e:
        utils.log(f"Failed to set info tag: {e}", "ERROR")
        # Fallback to basic setInfo
        try:
            li.setInfo(content_type, info_dict)
        except Exception:
            pass


def set_art(li: xbmcgui.ListItem, art_dict: Dict[str, str]) -> None:
    """Legacy function - use apply_art with MediaItem instead"""
    utils.log("Using legacy set_art - consider migrating to apply_art", "WARNING")
    
    try:
        if art_dict:
            li.setArt(art_dict)
    except Exception as e:
        utils.log(f"Failed to set art: {e}", "ERROR")
