"""
Legacy InfoTag functions - now delegates to infotag_adapter
Maintained for backward compatibility during migration
"""
from typing import Dict, Any
from resources.lib.kodi.adapters.infotag_adapter import apply_infotag
from resources.lib.data.models import MediaItem
from resources.lib.utils import utils


class ListItemInfoTagVideo:
    """Legacy wrapper - delegates to new infotag adapter"""

    def __init__(self):
        utils.log("Legacy InfoTag handler - use infotag_adapter.py instead", "WARNING")

    def set_video_infotag(self, listitem, media_dict):
        """Set video InfoTag data on a ListItem - delegates to new adapter"""
        try:
            # Convert media_dict to MediaItem for adapter
            media_item = MediaItem(
                id=media_dict.get('id', 0),
                media_type=media_dict.get('media_type', 'movie'),
                title=media_dict.get('title', ''),
                year=media_dict.get('year'),
                imdb=media_dict.get('imdb') or media_dict.get('imdbnumber', ''),
                tmdb=media_dict.get('tmdb', ''),
                plot=media_dict.get('plot', ''),
                genres=media_dict.get('genres', []),
                runtime=media_dict.get('runtime'),
                rating=media_dict.get('rating'),
                votes=media_dict.get('votes'),
                studio=media_dict.get('studio', ''),
                country=media_dict.get('country', ''),
                cast=media_dict.get('cast', [])
            )

            # Use new adapter to apply InfoTag
            apply_infotag(media_item, listitem)

        except Exception as e:
            utils.log(f"Error in legacy InfoTag handler: {str(e)}", "ERROR")