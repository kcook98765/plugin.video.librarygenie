"""Helper class for building ListItems with proper metadata"""
import json
import xbmc
import xbmcgui
from urllib.parse import quote
from resources.lib import utils
from resources.lib.listitem_infotagvideo import set_info_tag

def format_art(url):
    """Format art URLs for Kodi display"""
    if not url:
        return ''
    if url.startswith('image://'):
        return url
    if url.startswith('smb://'):
        return f'image://video@{quote(url)}/'
    return f'image://{quote(url)}/'


class ListItemBuilder:
    @staticmethod
    def build_video_item(media_info):
        title = media_info.get('title', '')
        list_item = xbmcgui.ListItem(label=title)

        # Handle artwork with proper formatting and validation
        art = {}
        media_art = media_info.get('art', {})

        def format_art_url(url):
            if not url:
                return ''
            if url.startswith('image://'):
                return url
            elif url.startswith('http'):
                return f"image://{quote(url)}/"
            return f"image://{url}/"

        # Process artwork with proper fallbacks
        art_types = {
            'poster': ['poster', 'thumb', 'thumbnail'],
            'thumb': ['thumb', 'poster', 'thumbnail'],
            'fanart': ['fanart', 'landscape'],
            'banner': ['banner'],
            'clearlogo': ['clearlogo', 'logo'],
            'clearart': ['clearart'],
            'landscape': ['landscape'],
            'icon': ['icon', 'poster', 'thumb']
        }

        # Log available art for debugging
        utils.log(f"Available art from media_info: {media_art}", "DEBUG")

        # Process each art type with fallbacks
        for art_type, fallbacks in art_types.items():
            art_url = None
            # Check media_art dictionary first
            for fallback in fallbacks:
                if fallback in media_art and media_art[fallback]:
                    art_url = media_art[fallback]
                    break
            # Then check top-level media_info
            if not art_url:
                for fallback in fallbacks:
                    if fallback in media_info and media_info[fallback]:
                        art_url = media_info[fallback]
                        break

            if art_url:
                formatted_url = format_art_url(art_url)
                art[art_type] = formatted_url
                utils.log(f"Set {art_type} art: {formatted_url}", "DEBUG")

        # Ensure at least empty strings for required art types
        for required in ['poster', 'thumb', 'fanart', 'icon']:
            if required not in art:
                art[required] = ''

        # Set artwork after preparing complete dictionary
        try:
            list_item.setArt(art)
            utils.log(f"Set final art dictionary: {art}", "DEBUG")
        except Exception as e:
            utils.log(f"Error setting art: {str(e)}", "ERROR")

        # Set video info tag
        set_info_tag(list_item, media_info)

        # Handle cast with images if present
        if 'cast' in media_info:
            try:
                cast_list = []
                for actor in media_info['cast']:
                    if isinstance(actor, dict):
                        name = actor.get('name', '')
                        role = actor.get('role', '')
                        order = actor.get('order', 0)
                        thumb = format_art_url(actor.get('thumbnail', ''))
                        cast_member = {'name': name, 'role': role, 'order': order, 'thumbnail': thumb}
                        cast_list.append(cast_member)
                if cast_list:
                    info_tag = list_item.getVideoInfoTag()
                    info_tag.setCast(cast_list)
            except Exception as e:
                utils.log(f"Error setting cast: {str(e)}", "ERROR")

        return list_item

    @staticmethod
    def build_folder_item(name, is_folder=True):
        """Build a folder ListItem."""
        list_item = xbmcgui.ListItem(label=name)
        list_item.setIsFolder(is_folder)
        return list_item

    @staticmethod
    def add_context_menu(list_item, menu_items):
        """Add context menu items to ListItem."""
        list_item.addContextMenuItems(menu_items, replaceItems=True)