""" /resources/lib/kodi_helper.py """
import sys
import json
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from resources.lib.jsonrpc_manager import JSONRPC
from resources.lib.utils import get_addon_handle
from resources.lib import utils
from resources.lib.listitem_infotagvideo import set_info_tag, set_art

class KodiHelper:

    def __init__(self, addon_handle=None):
        self.addon_handle = addon_handle if addon_handle is not None else get_addon_handle()
        self.addon = xbmcaddon.Addon()
        self.addon_url = sys.argv[0] if len(sys.argv) > 0 else ""
        self.jsonrpc = JSONRPC()

    def list_items(self, items, content_type='video'):
        from resources.lib.listitem_builder import ListItemBuilder

        # Set content type for proper display
        xbmcplugin.setContent(self.addon_handle, content_type)

        for item in items:
            list_item = ListItemBuilder.build_video_item(item)
            url = f'{self.addon_url}?action=play_item&id={item.get("id")}'

            xbmcplugin.addDirectoryItem(
                handle=self.addon_handle,
                url=url,
                listitem=list_item,
                isFolder=False
            )

        # Enable media flags and sorting
        xbmcplugin.setContent(self.addon_handle, content_type)
        xbmcplugin.addSortMethod(self.addon_handle, xbmcplugin.SORT_METHOD_TITLE)
        xbmcplugin.addSortMethod(self.addon_handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)

        xbmcplugin.endOfDirectory(self.addon_handle)

    def list_folders(self, folders):
        for folder in folders:
            list_item = xbmcgui.ListItem(label=folder['name'])
            url = f'{self.addon_url}?action=show_list&list_id={folder["id"]}'

            xbmcplugin.addDirectoryItem(
                handle=self.addon_handle,
                url=url,
                listitem=list_item,
                isFolder=True
            )

        xbmcplugin.endOfDirectory(self.addon_handle)

    def list_folders_and_lists(self, folders, lists):
        for folder in folders:
            list_item = xbmcgui.ListItem(label=folder['name'])
            url = f'{self.addon_url}?action=show_folder&folder_id={folder["id"]}'
            utils.log(f"Adding folder: {folder['name']} with URL - {url}", "INFO")
            xbmcplugin.addDirectoryItem(
                handle=self.addon_handle,
                url=url,
                listitem=list_item,
                isFolder=True
            )
        for list_ in lists:
            list_item = xbmcgui.ListItem(label=list_['name'])
            url = f'{self.addon_url}?action=show_list&list_id={list_["id"]}'
            utils.log(f"Adding list: {list_['name']} with URL - {url}", "INFO")
            xbmcplugin.addDirectoryItem(
                handle=self.addon_handle,
                url=url,
                listitem=list_item,
                isFolder=True
            )
        xbmcplugin.endOfDirectory(self.addon_handle)

    def play_item(self, item_id, content_type='video'):
        try:
            # Query the database for item
            query = """SELECT media_items.* FROM media_items 
                      JOIN list_items ON list_items.media_item_id = media_items.id 
                      WHERE list_items.media_item_id = ?"""
            
            from resources.lib.database_manager import DatabaseManager
            from resources.lib.config_manager import Config
            config = Config()
            db = DatabaseManager(config.db_path)
            
            # Handle item_id from various input types and ensure valid integer
            if isinstance(item_id, (list, tuple)):
                item_id = item_id[0]
            elif isinstance(item_id, dict):
                item_id = item_id.get('id')
            
            if not item_id:
                utils.log("Invalid item_id received", "ERROR")
                return False
                
            try:
                item_id = int(item_id)
            except (ValueError, TypeError):
                utils.log(f"Could not convert item_id to integer: {item_id}", "ERROR")
                return False
                
            db.cursor.execute(query, (item_id,))
            result = db.cursor.fetchone()
            
            if not result:
                utils.log(f"Item not found for id: {item_id_value}", "ERROR")
                return False

            # Convert result to dict 
            field_names = [field.split()[0] for field in db.config.FIELDS]
            item_data = dict(zip(['id'] + field_names, result))
                
            # Create list item with title and setup basic properties
            list_item = xbmcgui.ListItem(label=result.get('title', ''))
            
            # Get play URL and check validity
            play_url = result.get('play') or result.get('file', '')
            if not play_url:
                utils.log("No play URL found", "ERROR") 
                return False
            
            # Set path and mime type based on URL
            list_item.setPath(play_url)
            utils.log(f"Setting play URL: {play_url}", "DEBUG")
            
            # Determine mime type from URL
            if play_url.endswith('.mp4'):
                mime_type = 'video/mp4'
            elif play_url.endswith(('.mkv', '.avi')):
                mime_type = 'video/x-matroska'
            elif play_url.endswith('.m3u8'):
                mime_type = 'application/x-mpegURL'
            else:
                mime_type = 'video/mp4'  # Default fallback
                
            # Set content and properties
            xbmcplugin.setContent(self.addon_handle, content_type)
            list_item.setProperty('IsPlayable', 'true')
            list_item.setMimeType(mime_type)
            list_item.setProperty('inputstream', 'inputstream.adaptive')
            
            # Set additional properties if available
            if result.get('duration'):
                list_item.addStreamInfo('video', {'duration': int(result['duration'])})
            
            # Resolve URL for playback
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
            return True
            
        except Exception as e:
            utils.log(f"Error playing item: {str(e)}", "ERROR")
            return False

    def get_focused_item_basic_info(self):
        from resources.lib.media_manager import MediaManager
        media_manager = MediaManager()
        return media_manager.get_media_info()

    def get_focused_item_details(self):
        db_id = xbmc.getInfoLabel('ListItem.DBID')

        if db_id:
            # Fetch details via JSON-RPC
            media_type = xbmc.getInfoLabel('ListItem.DBTYPE')
            method = 'VideoLibrary.GetMovieDetails' if media_type == 'movie' else 'VideoLibrary.GetEpisodeDetails'
            params = {
                'properties': [
                    'title', 'genre', 'year', 'director', 'cast', 'plot', 'rating',
                    'file', 'thumbnail', 'fanart', 'runtime', 'tagline',
                    'writer', 'imdbnumber', 'premiered', 'mpaa', 'trailer', "votes",
                    "country", "dateadded", "studio"
                ]
            }
            if method == 'VideoLibrary.GetMovieDetails':
                params['movieid'] = int(db_id)
            else:
                params['episodeid'] = int(db_id)

            utils.log(f"Fetching details via RPC - Method: {method}, Params: {params}", "DEBUG")
            response = self.jsonrpc.execute(method, params)
            utils.log(f"RPC Response: {response}", "DEBUG")
            details = response.get('result', {}).get('moviedetails' if method == 'VideoLibrary.GetMovieDetails' else 'episodedetails', {})
            utils.log(f"Extracted details for media type: {media_type}", "INFO")

            # Parse cast details
            cast_list = details.get('cast', [])
            cast = [{'name': actor.get('name'), 'role': actor.get('role'), 'order': actor.get('order'), 'thumbnail': actor.get('thumbnail')} for actor in cast_list]
            details['cast'] = cast

            # Convert list fields to comma-separated strings
            if 'genre' in details:
                details['genre'] = ' / '.join(details['genre'])
            if 'director' in details:
                details['director'] = ' / '.join(details['director'])
            if 'writer' in details:
                details['writer'] = ' / '.join(details['writer'])
            if 'country' in details:
                details['country'] = ' / '.join(details['country'])
            if 'studio' in details:
                details['studio'] = ' / '.join(details['studio'])

            details['file'] = xbmc.getInfoLabel('ListItem.FileNameAndPath')
            details['kodi_id'] = int(db_id)  # Ensure dbid is included
            details['play'] = details['file']  # Set the play field to a valid value
            utils.log(f"Final gathered item details: {details}", "DEBUG")
            return details

        # Fallback: Gather details directly from ListItem labels
        details = {
            'kodi_id': db_id,
            'title': xbmc.getInfoLabel('ListItem.Title'),
            'country': xbmc.getInfoLabel('ListItem.Country'),
            'dateadded': xbmc.getInfoLabel('ListItem.DateAdded'),
            'genre': xbmc.getInfoLabel('ListItem.Genre'),
            'year': xbmc.getInfoLabel('ListItem.Year'),
            'director': xbmc.getInfoLabel('ListItem.Director'),
            'cast': self.get_cast_info(),
            'plot': xbmc.getInfoLabel('ListItem.Plot'),
            'rating': xbmc.getInfoLabel('ListItem.Rating'),
            'file': xbmc.getInfoLabel('ListItem.FileNameAndPath'),
            'thumbnail': xbmc.getInfoLabel('ListItem.Art(poster)'),
            'fanart': xbmc.getInfoLabel('ListItem.Art(fanart)'),
            'duration': xbmc.getInfoLabel('ListItem.Duration'),
            'tagline': xbmc.getInfoLabel('ListItem.Tagline'),
            'writer': xbmc.getInfoLabel('ListItem.Writer'),
            'imdbnumber': xbmc.getInfoLabel('ListItem.IMDBNumber'),
            'premiered': xbmc.getInfoLabel('ListItem.Premiered'),
            'studio': xbmc.getInfoLabel('ListItem.Studio'),
            'mpaa': xbmc.getInfoLabel('ListItem.Mpaa'),
            'trailer': xbmc.getInfoLabel('ListItem.Trailer'),
            'status': xbmc.getInfoLabel('ListItem.Status'),
            'votes': xbmc.getInfoLabel('ListItem.Votes'),
            'path': xbmc.getInfoLabel('ListItem.Path'),
            'mediatype': xbmc.getInfoLabel('ListItem.MediaType'),
            'uniqueid': xbmc.getInfoLabel('ListItem.UniqueID'),
            'is_playable': xbmc.getInfoLabel('ListItem.Property(IsPlayable)') == 'true',
            'dbid': db_id,
            'play': xbmc.getInfoLabel('ListItem.Path')  # Set the play field to a valid value
        }

        utils.log(f"Directly collected item details: {details}")
        return details

    def show_information(self):
        db_id = xbmc.getInfoLabel('ListItem.DBID')
        media_type = xbmc.getInfoLabel('ListItem.DBTYPE')
        media_type = 'movie'
        utils.log(f"Retrieved DBID: {db_id}, Media type: {media_type}", "INFO")

        if db_id:
            if media_type == 'movie':
                utils.log(f"Opening movie information window for ID: {db_id}", "DEBUG")
                xbmc.executebuiltin(f"ActivateWindow(movieinformation,{db_id})")
            elif media_type == 'episode':
                show_id = xbmc.getInfoLabel('ListItem.TVShowDBID')
                season = xbmc.getInfoLabel('ListItem.Season')
                episode = xbmc.getInfoLabel('ListItem.Episode')
                utils.log(f"Opening episode information window for Show: {show_id}, S{season}E{episode}", "DEBUG")
                xbmc.executebuiltin(f"ActivateWindow(movieinformation,{show_id},{season},{episode},{db_id})")
            else:
                utils.log("Invalid media type or path", "WARNING")
        else:
            utils.log("No DBID found for the item", "WARNING")

    def get_cast_info(self):
        try:
            utils.log("Gathering cast information", "DEBUG")
            cast = []
            for i in range(1, 21):  # Assuming a maximum of 20 cast members
                name = xbmc.getInfoLabel(f'ListItem.CastAndRole.{i}.Name')
                if not name:
                    continue
                role = xbmc.getInfoLabel(f'ListItem.CastAndRole.{i}.Role')
                order = i - 1  # Zero-based index
                utils.log(f"Cast member {i}: {name} as {role}", "DEBUG")
                thumbnail = xbmc.getInfoLabel(f'ListItem.CastAndRole.{i}.Thumb')
                cast.append({
                    'name': name,
                    'role': role,
                    'order': order,
                    'thumbnail': thumbnail
                })
            return json.dumps(cast) if isinstance(cast, list) else cast
        except Exception as e:
            utils.log(f"Error getting cast info: {str(e)}", "ERROR")
            return "[]"