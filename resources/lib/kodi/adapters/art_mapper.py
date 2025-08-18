
from typing import TYPE_CHECKING
from ...utils.utils import log

if TYPE_CHECKING:
    from ...data.models import MediaItem

def apply_art(item: 'MediaItem', list_item) -> None:
    """Map MediaItem art to Kodi ListItem art with safe fallbacks"""
    try:
        art_dict = {}
        
        # Map standard art types
        if item.art.get('poster'):
            art_dict['poster'] = item.art['poster']
        
        if item.art.get('fanart'):
            art_dict['fanart'] = item.art['fanart']
        
        if item.art.get('thumb'):
            art_dict['thumb'] = item.art['thumb']
        else:
            # Fallback: use poster as thumb
            art_dict['thumb'] = item.art.get('poster', '')
        
        if item.art.get('banner'):
            art_dict['banner'] = item.art['banner']
        
        if item.art.get('landscape'):
            art_dict['landscape'] = item.art['landscape']
        else:
            # Fallback: use fanart as landscape
            art_dict['landscape'] = item.art.get('fanart', '')
        
        # Additional Kodi art types with fallbacks
        if item.art.get('clearlogo'):
            art_dict['clearlogo'] = item.art['clearlogo']
            
        if item.art.get('clearart'):
            art_dict['clearart'] = item.art['clearart']
        
        # Set icon to poster if available
        if item.art.get('poster'):
            art_dict['icon'] = item.art['poster']
        
        # Apply art to ListItem
        if art_dict:
            list_item.setArt(art_dict)
            log(f"Applied art: {list(art_dict.keys())}", "DEBUG")
        else:
            log("No art available to apply", "DEBUG")
            
    except Exception as e:
        log(f"Error applying art: {str(e)}", "ERROR")
