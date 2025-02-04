""" /resources/lib/kodi_helper.py """
import sys
import json
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from resources.lib.jsonrpc_manager import JSONRPC
from resources.lib.utils import get_addon_handle
from resources.lib.listitem_infotagvideo import set_info, set_art

class KodiHelper:

    def __init__(self, addon_handle=None):
        self.addon_handle = addon_handle if addon_handle is not None else get_addon_handle()
        self.addon = xbmcaddon.Addon()
        self.addon_url = sys.argv[0] if len(sys.argv) > 0 else ""
        self.jsonrpc = JSONRPC()

    def list_items(self, items, content_type='video'):
        list_item = xbmcgui.ListItem()
        # Create an InfoTagVideo object
        info_tag = xbmc.InfoTagVideo()

        $ TODO, use jsonrpc data as-is to set listitems below
        media_info = xxxxxxxxxxxxxxxxx

        # Set the media info using the set_info function
        set_info(info_tag, media_info, 'movie')

        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url="", listitem=list_item, isFolder=False)
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
            xbmc.log(f"ListGenius: Adding folder URL - {url}", xbmc.LOGDEBUG)
            xbmcplugin.addDirectoryItem(
                handle=self.addon_handle,
                url=url,
                listitem=list_item,
                isFolder=True
            )
        for list_ in lists:
            list_item = xbmcgui.ListItem(label=list_['name'])
            url = f'{self.addon_url}?action=show_list&list_id={list_["id"]}'
            xbmc.log(f"ListGenius: Adding list URL - {url}", xbmc.LOGDEBUG)
            xbmcplugin.addDirectoryItem(
                handle=self.addon_handle,
                url=url,
                listitem=list_item,
                isFolder=True
            )
        xbmcplugin.endOfDirectory(self.addon_handle)

    def play_item(self, item, content_type='video'):
        list_item = xbmcgui.ListItem(label=item['title'])
        list_item.setInfo(content_type, item.get('info', {}))
        list_item.setPath(item.get('file', ''))  # Use the full path to play the item

        xbmcplugin.setResolvedUrl(self.addon_handle, True, listitem=list_item)

    def get_focused_item_basic_info(self):
        item_info = {
            'kodi_id': xbmc.getInfoLabel('ListItem.DBID'),
            'country': xbmc.getInfoLabel('ListItem.Country'),
            'dateadded': xbmc.getInfoLabel('ListItem.DateAdded'),
            'title': xbmc.getInfoLabel('ListItem.Title'),
            'year': xbmc.getInfoLabel('ListItem.Year'),
            'plot': xbmc.getInfoLabel('ListItem.Plot'),
            'genre': xbmc.getInfoLabel('ListItem.Genre'),
            'director': xbmc.getInfoLabel('ListItem.Director'),
            'cast': xbmc.getInfoLabel('ListItem.Cast'),
            'rating': xbmc.getInfoLabel('ListItem.Rating'),
            'thumbnail': xbmc.getInfoLabel('ListItem.Art(poster)'),  # Collect poster
            'fanart': xbmc.getInfoLabel('ListItem.Art(fanart)'),
            'duration': xbmc.getInfoLabel('ListItem.Duration'),
            'tagline': xbmc.getInfoLabel('ListItem.Tagline'),
            'writer': xbmc.getInfoLabel('ListItem.Writer'),
            'imdbnumber': xbmc.getInfoLabel('ListItem.IMDBNumber'),
            'premiered': xbmc.getInfoLabel('ListItem.Premiered'),
            'studio': xbmc.getInfoLabel('ListItem.Studio'),
            'mpaa': xbmc.getInfoLabel('ListItem.Mpaa'),
            'trailer': xbmc.getInfoLabel('ListItem.Trailer'),
            'file': xbmc.getInfoLabel('ListItem.FileNameAndPath'),  # Use full path and file name
            'is_playable': xbmc.getInfoLabel('ListItem.Property(IsPlayable)') == 'true',
            'play': xbmc.getInfoLabel('ListItem.Path')  # Set the play field to a valid value
        }

        xbmc.log(f"ListGenius: Basic item info gathered: {item_info}", xbmc.LOGDEBUG)
        return item_info

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

            xbmc.log(f"ListGenius: Fetching details via RPC - Method: {method}, Params: {params}", xbmc.LOGDEBUG)
            response = self.jsonrpc.execute(method, params)
            xbmc.log(f"ListGenius: RPC Response: {response}", xbmc.LOGDEBUG)
            details = response.get('result', {}).get('moviedetails' if method == 'VideoLibrary.GetMovieDetails' else 'episodedetails', {})

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
            xbmc.log(f"ListGenius: Final gathered item details: {details}", xbmc.LOGDEBUG)
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

        xbmc.log(f"ListGenius: Directly collected item details: {details}", xbmc.LOGDEBUG)
        return details

    def show_information(self):
        db_id = xbmc.getInfoLabel('ListItem.DBID')
        media_type = xbmc.getInfoLabel('ListItem.DBTYPE')
        media_type = 'movie'
        xbmc.log(f"ListGenius: Retrieved DBID: {db_id}, Media type: {media_type}", xbmc.LOGDEBUG)

        if db_id:
            if media_type == 'movie':
                xbmc.executebuiltin(f"ActivateWindow(movieinformation,{db_id})")
            elif media_type == 'episode':
                show_id = xbmc.getInfoLabel('ListItem.TVShowDBID')
                season = xbmc.getInfoLabel('ListItem.Season')
                episode = xbmc.getInfoLabel('ListItem.Episode')
                xbmc.executebuiltin(f"ActivateWindow(movieinformation,{show_id},{season},{episode},{db_id})")
            else:
                xbmc.log("ListGenius: Invalid media type or path", xbmc.LOGDEBUG)
        else:
            xbmc.log("ListGenius: No DBID found for the item", xbmc.LOGDEBUG)

    def get_cast_info(self):
        cast = []
        for i in range(1, 21):  # Assuming a maximum of 20 cast members
            name = xbmc.getInfoLabel(f'ListItem.CastAndRole.{i}.Name')
            role = xbmc.getInfoLabel(f'ListItem.CastAndRole.{i}.Role')
            order = i - 1  # Zero-based index
            thumbnail = xbmc.getInfoLabel(f'ListItem.CastAndRole.{i}.Thumb')
            if name:
                cast.append({
                    'name': name,
                    'role': role,
                    'order': order,
                    'thumbnail': thumbnail
                })
        return json.dumps(cast)

