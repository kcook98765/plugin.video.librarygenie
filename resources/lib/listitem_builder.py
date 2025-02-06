"""Helper class for building ListItems with proper metadata"""
import json
import xbmcgui
import xbmc
from resources.lib import utils
from resources.lib.listitem_infotagvideo import set_info_tag

class ListItemBuilder:
    _item_cache = {}

    @staticmethod
    def build_video_item(media_info):
        """Build a complete video ListItem with all available metadata"""
        if not isinstance(media_info, dict):
            media_info = {}

        # Generate cache key from stable fields
        cache_key = str(media_info.get('title', '')) + str(media_info.get('year', '')) + str(media_info.get('kodi_id', ''))
        if cache_key in ListItemBuilder._item_cache:
            return ListItemBuilder._item_cache[cache_key]

        utils.log(f"Building video item with media info: {media_info}", "DEBUG")

        # Create ListItem with proper string title
        title = str(media_info.get('title', ''))
        list_item = xbmcgui.ListItem(label=title)
        utils.log(f"Created ListItem with title: {title}", "DEBUG")

        # Set artwork
        art_dict = media_info.get('art', {}).copy()  # Start with stored art dictionary
        utils.log(f"Setting artwork for item: {media_info.get('title', 'Unknown')}", "DEBUG")
        utils.log(f"Initial art dictionary type: {type(art_dict)}", "DEBUG")
        utils.log(f"Initial art dictionary: {art_dict}", "DEBUG")
        utils.log(f"Available art keys: {list(art_dict.keys()) if isinstance(art_dict, dict) else 'Not a dictionary'}", "DEBUG")
        
        # Get poster URL from multiple possible locations with detailed logging
        utils.log(f"POSTER TRACE - ListItemBuilder 1 - Direct poster: {media_info.get('poster')}", "DEBUG")
        utils.log(f"POSTER TRACE - ListItemBuilder 2 - Art dict poster: {art_dict.get('poster')}", "DEBUG")
        utils.log(f"POSTER TRACE - ListItemBuilder 3 - Raw media info: {media_info}", "DEBUG")
        utils.log(f"POSTER TRACE - ListItemBuilder 4 - Art dict type: {type(art_dict)}", "DEBUG")
        utils.log(f"POSTER TRACE - ListItemBuilder 5 - Art dict content: {art_dict}", "DEBUG")
        utils.log(f"Info dictionary poster: {media_info.get('info', {}).get('poster')}", "DEBUG")
        utils.log(f"Thumbnail: {media_info.get('thumbnail')}", "DEBUG")
        
        # Get poster URL with priority order
        poster_url = None
        for source in [
            lambda: media_info.get('poster'),
            lambda: media_info.get('art', {}).get('poster'),
            lambda: media_info.get('info', {}).get('poster'),
            lambda: media_info.get('thumbnail')
        ]:
            try:
                url = source()
                if url and str(url) != 'None':
                    poster_url = url
                    break
            except Exception as e:
                utils.log(f"Error getting poster URL: {str(e)}", "ERROR")
                continue

        utils.log(f"LISTITEM POSTER 1 - Found URL: {poster_url}", "DEBUG")
        utils.log(f"LISTITEM POSTER 2 - Full media info: {media_info}", "DEBUG")
        utils.log(f"LISTITEM POSTER 3 - Art dict content: {art_dict}", "DEBUG")
        utils.log(f"LISTITEM POSTER 4 - Info dict art: {media_info.get('info', {}).get('art')}", "DEBUG")
        
        if poster_url:
            utils.log(f"Final selected poster URL: {poster_url}", "DEBUG")
            utils.log(f"POSTER TRACE - ListItemBuilder art sources:", "DEBUG")
            utils.log(f"POSTER TRACE - ListItemBuilder final url: {poster_url}", "DEBUG") 
            utils.log(f"POSTER TRACE - ListItemBuilder media info art: {media_info.get('art')}", "DEBUG")
            utils.log(f"POSTER TRACE - ListItemBuilder info dict art: {media_info.get('info', {}).get('art')}", "DEBUG")
            utils.log(f"POSTER TRACE - ListItemBuilder art dict before set: {art_dict}", "DEBUG")
        else:
            utils.log("WARNING: No poster URL found from any source", "WARNING")
            utils.log(f"POSTER TRACE - ListItemBuilder missing poster debug:", "DEBUG")
            utils.log(f"POSTER TRACE - ListItemBuilder media info dump: {media_info}", "DEBUG")
            art_dict['poster'] = poster_url
            art_dict['thumb'] = poster_url
            art_dict['icon'] = poster_url

        # Set up initial art dictionary
        art_dict = {}
        poster = media_info.get('poster') or media_info.get('thumbnail')
        fanart = media_info.get('fanart')

        if poster and str(poster) != 'None':
            art_dict['poster'] = poster
            art_dict['thumb'] = poster
            art_dict['icon'] = poster
            utils.log(f"Setting art with poster: {poster}", "DEBUG")
            utils.log(f"Setting poster paths: {poster}", "DEBUG")

        if fanart and str(fanart) != 'None':
            art_dict['fanart'] = fanart
            utils.log(f"Setting fanart path: {fanart}", "DEBUG")

        if fanart and str(fanart) != 'None':
            art_dict['fanart'] = fanart
            utils.log(f"Setting fanart path: {fanart}", "DEBUG")

        # Handle video thumbnails
        if poster and 'video@' in str(poster):
            pass


        if poster:
            art_dict['thumb'] = poster
            art_dict['poster'] = poster
            art_dict['icon'] = poster

        # Check both direct and nested fanart paths    
        fanart = media_info.get('fanart') or media_info.get('info', {}).get('fanart')
        if fanart:
            art_dict['fanart'] = fanart

        list_item.setArt(art_dict)

        # Prepare info dictionary from nested info structure
        info = media_info.get('info', {})
        info_dict = {
            'title': title,
            'plot': info.get('plot', ''),
            'tagline': info.get('tagline', ''),
            'cast': json.loads(info.get('cast', '[]')) if isinstance(info.get('cast'), str) else info.get('cast', []),
            'country': info.get('country', ''),
            'director': info.get('director', ''),
            'genre': info.get('genre', ''),
            'mpaa': info.get('mpaa', ''),
            'premiered': info.get('premiered', ''),
            'rating': float(info.get('rating', 0.0)),
            'studio': info.get('studio', ''),
            'trailer': info.get('trailer', ''),
            'votes': info.get('votes', '0'),
            'writer': info.get('writer', ''),
            'year': info.get('year', ''),
            'mediatype': (info.get('media_type') or 'movie').lower()
        }

        utils.log(f"Prepared info dictionary: {info_dict}", "DEBUG")

        # Set video info using the compatibility helper
        set_info_tag(list_item, info_dict, 'video')
        utils.log("Set info tag completed", "DEBUG")

        # Set resume point if available
        if 'resumetime' in info and 'totaltime' in info:
            list_item.setProperty('ResumeTime', str(info['resumetime']))
            list_item.setProperty('TotalTime', str(info['totaltime']))

        # Set content properties
        list_item.setProperty('IsPlayable', 'true')

        # Process cast separately if it exists
        cast = info.get('cast', [])
        try:
            # Handle string-encoded cast data
            if isinstance(cast, str):
                try:
                    cast = json.loads(cast)
                except json.JSONDecodeError:
                    utils.log("Failed to decode cast JSON string", "ERROR")
                    cast = []
            
            # Ensure cast is a list
            if not isinstance(cast, list):
                cast = []
                
            # Create actor objects
            actors = []
            for cast_member in cast:
                if not isinstance(cast_member, dict):
                    continue
                    
                # Process thumbnail URL
                thumbnail = cast_member.get('thumbnail', '')
                if thumbnail and not thumbnail.startswith('image://'):
                    from urllib.parse import quote
                    thumbnail = f'image://{quote(thumbnail)}/'
                
                # Create actor with proper type conversion and defaults
                try:
                    actor = xbmc.Actor(
                        name=str(cast_member.get('name', 'Unknown')),
                        role=str(cast_member.get('role', '')),
                        order=int(cast_member.get('order', 999)),
                        thumbnail=str(thumbnail)
                    )
                    actors.append(actor)
                except Exception as e:
                    utils.log(f"Error creating actor object: {str(e)}", "ERROR")
                    continue
                    
            # Handle cast setting based on Kodi version
            kodi_version = xbmc.getInfoLabel("System.BuildVersion").split('.')[0]
            try:
                kodi_version = int(kodi_version)
            except (ValueError, TypeError):
                kodi_version = 0
                
            if kodi_version >= 20:
                # Use InfoTagVideo for Kodi 20+
                video_tag = list_item.getVideoInfoTag()
                video_tag.setCast(actors)
            else:
                # Use legacy method for older versions
                list_item.setCast(actors)
                
            utils.log(f"Set cast with {len(actors)} actors for Kodi version {kodi_version}", "DEBUG")
            
        except Exception as e:
            utils.log(f"Error processing cast: {str(e)}", "ERROR")
            list_item.setCast([])


        # Try to get play URL from different possible locations
        play_url = media_info.get('info', {}).get('play') or media_info.get('play') or media_info.get('file')
        if play_url:
            list_item.setPath(play_url)
            utils.log(f"Setting play URL: {play_url}", "DEBUG")
        else:
            utils.log("No valid play URL found", "WARNING")

        ListItemBuilder._item_cache[cache_key] = list_item
        return list_item

    @staticmethod
    def build_folder_item(name, is_folder=True):
        """Build a folder ListItem"""
        list_item = xbmcgui.ListItem(label=name)
        list_item.setIsFolder(is_folder)
        return list_item

    @staticmethod 
    def add_context_menu(list_item, menu_items):
        """Add context menu items to ListItem"""
        list_item.addContextMenuItems(menu_items, replaceItems=True)