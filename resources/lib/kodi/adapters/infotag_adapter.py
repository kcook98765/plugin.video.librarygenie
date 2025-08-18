
import xbmcgui
from typing import TYPE_CHECKING
from ...utils.utils import get_kodi_version, log

if TYPE_CHECKING:
    from ...data.models import MediaItem

def apply_infotag(item: 'MediaItem', list_item: xbmcgui.ListItem) -> None:
    """Apply InfoTag data to ListItem with version-specific handling"""
    try:
        kodi_version = get_kodi_version()
        log(f"Applying InfoTag for Kodi v{kodi_version}", "DEBUG")
        
        # Get InfoTag object
        info = list_item.getVideoInfoTag()
        
        # Apply common fields
        _apply_common_fields(item, info)
        
        # Apply version-specific fields
        if kodi_version >= 21:
            _apply_v21_fields(item, info, list_item)
        elif kodi_version >= 20:
            _apply_v20_fields(item, info, list_item)
        else:
            _apply_v19_fields(item, info, list_item)
            
    except Exception as e:
        log(f"Error applying InfoTag: {str(e)}", "ERROR")
        # Fallback to basic setInfo for older compatibility
        _apply_fallback_info(item, list_item)

def _apply_common_fields(item: 'MediaItem', info) -> None:
    """Apply fields common across all Kodi versions"""
    try:
        info.setTitle(item.title)
        info.setPlot(item.plot)
        info.setYear(item.year)
        info.setRating(item.rating)
        info.setVotes(item.votes)
        
        if item.runtime > 0:
            info.setDuration(item.runtime)
        
        if item.genres:
            info.setGenres(item.genres)
            
        if item.studio:
            info.setStudios([item.studio])
            
        if item.country:
            info.setCountries([item.country])
            
        info.setMediaType(item.media_type)
        
    except Exception as e:
        log(f"Error in _apply_common_fields: {str(e)}", "WARNING")

def _apply_v21_fields(item: 'MediaItem', info, list_item: xbmcgui.ListItem) -> None:
    """Apply v21+ specific fields including new cast handling"""
    try:
        # Handle unique IDs (v20+ feature)
        if item.imdb:
            info.setUniqueIDs({'imdb': item.imdb})
        if item.tmdb:
            unique_ids = {'tmdb': item.tmdb}
            if item.imdb:
                unique_ids['imdb'] = item.imdb
            info.setUniqueIDs(unique_ids)
        
        # v21+ cast handling with Actor objects
        if item.cast and hasattr(info, 'setCast') and hasattr(xbmcgui, 'Actor'):
            actors = []
            for actor_data in item.cast:
                if actor_data.name:
                    try:
                        actor_obj = xbmcgui.Actor(
                            name=actor_data.name,
                            role=actor_data.role,
                            order=actor_data.order,
                            thumbnail=actor_data.thumb
                        )
                        actors.append(actor_obj)
                    except Exception as e:
                        log(f"Error creating Actor object: {str(e)}", "WARNING")
                        continue
            
            if actors:
                info.setCast(actors)
        
        # Stream details for v21+
        if item.stream_details:
            try:
                # Apply video stream details if available
                video_streams = item.stream_details.get('video', [])
                if video_streams:
                    video = video_streams[0]
                    if 'width' in video and 'height' in video:
                        info.addVideoStream(xbmcgui.VideoStreamDetail(
                            width=video.get('width', 0),
                            height=video.get('height', 0),
                            codec=video.get('codec', ''),
                            duration=video.get('duration', item.runtime)
                        ))
            except Exception as e:
                log(f"Error applying stream details: {str(e)}", "WARNING")
                
    except Exception as e:
        log(f"Error in _apply_v21_fields: {str(e)}", "WARNING")

def _apply_v20_fields(item: 'MediaItem', info, list_item: xbmcgui.ListItem) -> None:
    """Apply v20 specific fields"""
    try:
        # Handle unique IDs (v20+ feature)
        if item.imdb or item.tmdb:
            unique_ids = {}
            if item.imdb:
                unique_ids['imdb'] = item.imdb
            if item.tmdb:
                unique_ids['tmdb'] = item.tmdb
            info.setUniqueIDs(unique_ids)
        
        # v20 cast handling - use list_item.setCast with dicts
        if item.cast:
            cast_list = []
            for actor_data in item.cast:
                if actor_data.name:
                    cast_list.append({
                        'name': actor_data.name,
                        'role': actor_data.role,
                        'order': actor_data.order,
                        'thumbnail': actor_data.thumb
                    })
            
            if cast_list:
                try:
                    list_item.setCast(cast_list)
                except Exception as e:
                    log(f"Error setting cast in v20: {str(e)}", "WARNING")
                    
    except Exception as e:
        log(f"Error in _apply_v20_fields: {str(e)}", "WARNING")

def _apply_v19_fields(item: 'MediaItem', info, list_item: xbmcgui.ListItem) -> None:
    """Apply v19 specific fields and workarounds"""
    try:
        # v19 doesn't have setUniqueIDs, use setIMDBNumber
        if item.imdb:
            info.setIMDBNumber(item.imdb)
        
        # v19 cast handling - use list_item.setCast with dicts
        if item.cast:
            cast_list = []
            for actor_data in item.cast:
                if actor_data.name:
                    cast_list.append({
                        'name': actor_data.name,
                        'role': actor_data.role,
                        'order': actor_data.order,
                        'thumbnail': actor_data.thumb
                    })
            
            if cast_list:
                try:
                    list_item.setCast(cast_list)
                except Exception as e:
                    log(f"Error setting cast in v19: {str(e)}", "WARNING")
                    
    except Exception as e:
        log(f"Error in _apply_v19_fields: {str(e)}", "WARNING")

def _apply_fallback_info(item: 'MediaItem', list_item: xbmcgui.ListItem) -> None:
    """Fallback method using deprecated setInfo for maximum compatibility"""
    try:
        info_dict = {
            'title': item.title,
            'plot': item.plot,
            'year': item.year,
            'rating': item.rating,
            'votes': item.votes,
            'mediatype': item.media_type
        }
        
        if item.runtime > 0:
            info_dict['duration'] = item.runtime
            
        if item.genres:
            info_dict['genre'] = item.genres
            
        if item.studio:
            info_dict['studio'] = item.studio
            
        if item.country:
            info_dict['country'] = item.country
            
        if item.imdb:
            info_dict['imdbnumber'] = item.imdb
            
        list_item.setInfo('video', info_dict)
        log("Used fallback setInfo method", "WARNING")
        
    except Exception as e:
        log(f"Error in fallback info application: {str(e)}", "ERROR")
