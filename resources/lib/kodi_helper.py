import sys
import json
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib.addon_ref import get_addon
from resources.lib.jsonrpc_manager import JSONRPC
from resources.lib.utils import get_addon_handle
from resources.lib import utils
from resources.lib.listitem_infotagvideo import set_info_tag, set_art

class KodiHelper:

    def __init__(self, addon_handle=None):
        self.addon_handle = addon_handle if addon_handle is not None else get_addon_handle()
        self.addon = get_addon()
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

        # Enable all relevant sort methods for better view options
        xbmcplugin.addSortMethod(self.addon_handle, xbmcplugin.SORT_METHOD_LABEL)
        xbmcplugin.addSortMethod(self.addon_handle, xbmcplugin.SORT_METHOD_TITLE)
        xbmcplugin.addSortMethod(self.addon_handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(self.addon_handle, xbmcplugin.SORT_METHOD_GENRE)
        xbmcplugin.addSortMethod(self.addon_handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(self.addon_handle, xbmcplugin.SORT_METHOD_DATEADDED)

        # Force content type and views with debugging
        utils.log(f"Setting content type to: {content_type}", "DEBUG")
        xbmcplugin.setContent(self.addon_handle, content_type)

        # Try different view modes
        view_modes = {
            'list': 50,
            'poster': 51,
            'icon': 52,
            'wide': 55,
            'wall': 500,
            'fanart': 502,
            'media': 504
        }

        # Set default view mode to poster
        default_mode = view_modes['poster']
        utils.log(f"Setting default view mode: {default_mode}", "DEBUG")

        # Set skin view modes
        for mode_name, mode_id in view_modes.items():
            xbmc.executebuiltin(f'Container.SetViewMode({mode_id})')

        # Force views mode
        xbmc.executebuiltin('SetProperty(ForcedViews,1,Home)')
        xbmcplugin.setProperty(self.addon_handle, 'ForcedView', 'true')

        # Enable skin forced views
        xbmc.executebuiltin('Skin.SetBool(ForcedViews)')
        xbmc.executebuiltin('Container.SetForceViewMode(true)')

        xbmcplugin.endOfDirectory(self.addon_handle)

    def list_folders(self, folders):
        from resources.lib.listitem_builder import ListItemBuilder
        for folder in folders:
            list_item = ListItemBuilder.build_folder_item(folder['name'], is_folder=True, item_type='folder')
            url = f'{self.addon_url}?action=show_list&list_id={folder["id"]}'

            xbmcplugin.addDirectoryItem(
                handle=self.addon_handle,
                url=url,
                listitem=list_item,
                isFolder=True
            )

        xbmcplugin.endOfDirectory(self.addon_handle)

    def list_folders_and_lists(self, folders, lists):
        from resources.lib.listitem_builder import ListItemBuilder
        for folder in folders:
            list_item = ListItemBuilder.build_folder_item(folder['name'], is_folder=True, item_type='folder')
            url = f'{self.addon_url}?action=show_folder&folder_id={folder["id"]}'
            utils.log(f"Adding folder: {folder['name']} with URL - {url}", "DEBUG")
            xbmcplugin.addDirectoryItem(
                handle=self.addon_handle,
                url=url,
                listitem=list_item,
                isFolder=True
            )
        for list_ in lists:
            list_item = ListItemBuilder.build_folder_item(list_['name'], is_folder=True, item_type='playlist')
            url = f'{self.addon_url}?action=show_list&list_id={list_["id"]}'
            utils.log(f"Adding list: {list_['name']} with URL - {url}", "DEBUG")
            xbmcplugin.addDirectoryItem(
                handle=self.addon_handle,
                url=url,
                listitem=list_item,
                isFolder=True
            )
        xbmcplugin.endOfDirectory(self.addon_handle)

    def show_list(self, list_id):
        """Display items in a list"""
        utils.log(f"Showing list with ID: {list_id}", "DEBUG")
        from resources.lib.database_manager import DatabaseManager
        from resources.lib.config_manager import get_config
        from resources.lib.listitem_builder import ListItemBuilder
        config = get_config()
        db_manager = DatabaseManager(config.db_path)
        items = db_manager.fetch_list_items(list_id)

        # Set content type and force views
        xbmcplugin.setContent(self.addon_handle, 'movies')

        # Check if items have search scores to determine sorting approach
        has_scores = any(item.get('search_score', 0) > 0 for item in items)

        if has_scores:
            # Sort items by search score before displaying (highest first)
            items.sort(key=lambda x: x.get('search_score', 0), reverse=True)
            utils.log("Sorted items by search score", "DEBUG")

        # Always enable sort methods so users can override the default order
        xbmcplugin.addSortMethod(self.addon_handle, xbmcplugin.SORT_METHOD_LABEL)
        xbmcplugin.addSortMethod(self.addon_handle, xbmcplugin.SORT_METHOD_TITLE)
        xbmcplugin.addSortMethod(self.addon_handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(self.addon_handle, xbmcplugin.SORT_METHOD_GENRE)
        xbmcplugin.addSortMethod(self.addon_handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(self.addon_handle, xbmcplugin.SORT_METHOD_DATEADDED)

        if has_scores:
            # Set the default sort method to unsorted to preserve our score-based order
            # but still allow users to change it via skin options
            xbmcplugin.addSortMethod(self.addon_handle, xbmcplugin.SORT_METHOD_UNSORTED)
            utils.log("Enabled all sort methods with score-based default order", "DEBUG")

        # Set view modes
        view_modes = {
            'list': 50,
            'poster': 51,
            'icon': 52,
            'wide': 55,
            'wall': 500,
            'fanart': 502,
            'media': 504
        }

        # Set default view mode to poster
        default_mode = view_modes['poster']
        utils.log(f"Setting default view mode: {default_mode}", "DEBUG")

        # Set skin view modes
        for mode_name, mode_id in view_modes.items():
            xbmc.executebuiltin(f'Container.SetViewMode({mode_id})')

        # Force views mode
        xbmcplugin.setProperty(self.addon_handle, 'ForcedView', 'true')
        xbmc.executebuiltin('Container.SetForceViewMode(true)')

        # Add items and end directory
        for item in items:
            list_item = ListItemBuilder.build_video_item(item)
            url = f'{self.addon_url}?action=play_item&id={item.get("id")}'
            xbmcplugin.addDirectoryItem(
                handle=self.addon_handle,
                url=url,
                listitem=list_item,
                isFolder=False
            )
        xbmcplugin.endOfDirectory(self.addon_handle)

    def play_item(self, item_id, content_type='video'):
        try:
            utils.log(f"Play item called with item_id: {item_id} (type: {type(item_id)})", "DEBUG")

            # Query the database for item
            query = """SELECT media_items.* FROM media_items
                      JOIN list_items ON list_items.media_item_id = media_items.id
                      WHERE list_items.media_item_id = ?"""

            from resources.lib.database_manager import DatabaseManager
            from resources.lib.config_manager import get_config
            config = get_config()
            db = DatabaseManager(config.db_path)

            # Handle item_id from various input types and ensure valid integer
            utils.log(f"Original item_id: {item_id}", "DEBUG")
            # Extract first item if list/tuple
            if isinstance(item_id, (list, tuple)):
                utils.log(f"Converting from list/tuple: {item_id}", "DEBUG")
                item_id = item_id[0] if item_id else None
            # Extract id if dict
            elif isinstance(item_id, dict):
                utils.log(f"Converting from dict: {item_id}", "DEBUG")
                item_id = item_id.get('id')

            utils.log(f"After type conversion: {item_id}", "DEBUG")

            if not item_id:
                utils.log("Invalid item_id received (empty/None)", "ERROR")
                return False

            try:
                item_id = int(str(item_id).strip())
                utils.log(f"Converted to integer: {item_id}", "DEBUG")
            except (ValueError, TypeError) as e:
                utils.log(f"Could not convert item_id to integer: {item_id}, Error: {str(e)}", "ERROR")
                return False

            db.cursor.execute(query, (item_id,))
            result = db.cursor.fetchone()

            if not result:
                utils.log(f"Item not found for id: {item_id}", "ERROR")
                return False

            # Convert result tuple to dict
            field_names = [field.split()[0] for field in db.config.FIELDS]
            item_data = dict(zip(['id'] + field_names, result))

            # Create list item with proper metadata using ListItemBuilder if it's a video item
            if item_data.get('mediatype') == 'movie' or item_data.get('media_type') == 'movie':
                from resources.lib.listitem_builder import ListItemBuilder
                list_item = ListItemBuilder.build_video_item(item_data)
            else:
                # For non-video items, create basic ListItem using ListItemBuilder
                from resources.lib.listitem_builder import ListItemBuilder
                info_dict = {
                    'title': item_data.get('title', ''),
                    'plot': item_data.get('plot', ''),
                    'mediatype': item_data.get('mediatype', item_data.get('media_type', 'video'))
                }
                list_item = ListItemBuilder.build_video_item(info_dict)

            # Get play URL and check validity
            folder_path = item_data.get('path', '')
            play_url = None

            # Try to get play URL from different fields
            if 'play' in item_data and item_data['play']:
                play_url = item_data['play']
            elif 'file' in item_data and item_data['file']:
                play_url = item_data['file']
            elif folder_path:
                play_url = folder_path

            if not play_url:
                utils.log("No play URL found", "ERROR")
                return False

            utils.log(f"Using play URL: {play_url}", "DEBUG")
            list_item.setPath(play_url)

            # Determine content type and playback method
            if folder_path and xbmc.getCondVisibility('Window.IsVisible(MyVideoNav.xml)'):
                # Handle as video library navigation
                xbmc.executebuiltin(f'Container.Update({folder_path})')
                return True

            # Setup direct playback
            mime_type = self._get_mime_type(play_url)
            xbmcplugin.setContent(self.addon_handle, content_type)
            list_item.setProperty('IsPlayable', 'true')
            list_item.setMimeType(mime_type)
            list_item.setProperty('inputstream', 'inputstream.adaptive')

            # Set additional properties if available
            if 'duration' in item_data and item_data['duration']:
                try:
                    duration = int(item_data['duration'])
                    duration = str(duration)
                    list_item.addStreamInfo('video', {'duration': duration})
                except (ValueError, TypeError):
                    pass

            # Resolve URL for playback
            xbmcplugin.setResolvedUrl(self.addon_handle, True, list_item)
            return True

        except Exception as e:
            utils.log(f"Error playing item: {str(e)}", "ERROR")
            return False

    def _get_mime_type(self, url):
        """Helper method to determine mime type from URL"""
        if url.endswith('.mp4'):
            return 'video/mp4'
        elif url.endswith(('.mkv', '.avi')):
            return 'video/x-matroska'
        elif url.endswith('.m3u8'):
            return 'application/x-mpegURL'
        return 'video/mp4'  # Default fallback

    def get_focused_item_basic_info(self):
        from resources.lib.media_manager import MediaManager
        media_manager = MediaManager()
        return media_manager.get_media_info()

    def get_focused_item_details(self):
        db_id = xbmc.getInfoLabel('ListItem.DBID')

        if db_id:
            # Fetch details via JSON-RPC using comprehensive properties
            media_type = xbmc.getInfoLabel('ListItem.DBTYPE')
            key = 'movieid' if media_type == 'movie' else 'episodeid'
            method = 'VideoLibrary.GetMovieDetails' if media_type == 'movie' else 'VideoLibrary.GetEpisodeDetails'

            if media_type == 'movie':
                # Use comprehensive properties for movies
                properties = self.jsonrpc.get_comprehensive_properties()
            else:
                # Use existing properties for episodes (can be enhanced later)
                properties = [
                    'title', 'plot', 'rating', 'writer', 'firstaired', 'playcount',
                    'runtime', 'director', 'season', 'episode', 'originaltitle',
                    'showtitle', 'cast', 'streamdetails', 'lastplayed', 'fanart',
                    'thumbnail', 'file', 'resume', 'tvshowid', 'dateadded', 'uniqueid', 'art'
                ]

            params = {
                'properties': properties,
                key: int(db_id)  # dynamically assign the correct key
            }

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

            # Ensure IMDb ID is properly extracted for v19 compatibility
            if not details.get('imdbnumber') or not str(details.get('imdbnumber')).startswith('tt'):
                # Try to get IMDb ID from uniqueid field
                uniqueid = details.get('uniqueid', {})
                if isinstance(uniqueid, dict) and 'imdb' in uniqueid:
                    details['imdbnumber'] = uniqueid['imdb']

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
        from resources.lib.query_manager import QueryManager
        from resources.lib.config_manager import get_config

        db_id = xbmc.getInfoLabel('ListItem.DBID')
        media_type = xbmc.getInfoLabel('ListItem.DBTYPE') or 'movie'
        utils.log(f"Retrieved DBID: {db_id}, Media type: {media_type}", "INFO")

        config = get_config()
        self.query_manager = QueryManager(config.db_path)

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

    def get_imdb_from_item(self):
        """Extract IMDb ID from the currently focused item using multiple methods"""
        try:
            # Try multiple InfoLabel approaches
            imdb_candidates = [
                ('LibraryGenie.IMDbID', xbmc.getInfoLabel('ListItem.Property(LibraryGenie.IMDbID)')),
                ('ListItem.IMDBNumber', xbmc.getInfoLabel('ListItem.IMDBNumber')),
                ('ListItem.UniqueID(imdb)', xbmc.getInfoLabel('ListItem.UniqueID(imdb)')),
                ('ListItem.Property(imdb_id)', xbmc.getInfoLabel('ListItem.Property(imdb_id)')),
                ('ListItem.Property(imdbnumber)', xbmc.getInfoLabel('ListItem.Property(imdbnumber)'))
            ]

            for source_name, candidate in imdb_candidates:
                if candidate and str(candidate).startswith('tt'):
                    return candidate

            # Try getting from DBID if it's a library item
            dbid = xbmc.getInfoLabel('ListItem.DBID')
            if dbid and dbid.isdigit():
                try:
                    # Use JSON-RPC to get movie details including IMDb ID
                    from resources.lib.jsonrpc_manager import JSONRPC
                    jsonrpc = JSONRPC()
                    response = jsonrpc.execute('VideoLibrary.GetMovieDetails', {
                        'movieid': int(dbid),
                        'properties': ['imdbnumber', 'uniqueid']
                    })

                    if 'result' in response and 'moviedetails' in response['result']:
                        details = response['result']['moviedetails']
                        
                        # Try imdbnumber first
                        imdb_from_details = details.get('imdbnumber', '')
                        if imdb_from_details and str(imdb_from_details).startswith('tt'):
                            return imdb_from_details

                        # Try uniqueid
                        uniqueid = details.get('uniqueid', {})
                        if isinstance(uniqueid, dict) and 'imdb' in uniqueid:
                            imdb_from_uniqueid = uniqueid['imdb']
                            if imdb_from_uniqueid and str(imdb_from_uniqueid).startswith('tt'):
                                return imdb_from_uniqueid

                except Exception as e:
                    xbmc.log(f"LibraryGenie: Error getting IMDb from DBID: {str(e)}", xbmc.LOGDEBUG)

            return None

        except Exception as e:
            xbmc.log(f"LibraryGenie: Error in get_imdb_from_item: {str(e)}", xbmc.LOGDEBUG)
            return None

    def get_playable_url(self, item_info):
        """Get a playable URL from item information"""
        if not item_info:
            return None
            
        # Try to get URL from different possible fields
        for field in ['play', 'file', 'path', 'stream_url']:
            url = item_info.get(field)
            if url and str(url).strip():
                return str(url).strip()
                
        return None