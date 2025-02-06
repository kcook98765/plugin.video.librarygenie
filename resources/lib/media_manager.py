import xbmc
import json
from resources.lib import utils
from resources.lib.jsonrpc_manager import JSONRPC

class MediaManager:
    def __init__(self):
        self.jsonrpc = JSONRPC()

    def get_media_info(self, media_type='movie'):
        """Get media info from Kodi"""
        kodi_id = xbmc.getInfoLabel('ListItem.DBID')

        # If we have a valid database ID, use JSONRPC
        if kodi_id and kodi_id.isdigit() and int(kodi_id) > 0:
            utils.log(f"Getting library item details via JSONRPC for ID: {kodi_id}", "DEBUG")
            method = 'VideoLibrary.GetMovieDetails'
            params = {
                'movieid': int(kodi_id),
                'properties': [
                    'title', 'genre', 'year', 'director', 'cast', 'plot', 'rating',
                    'file', 'thumbnail', 'fanart', 'runtime', 'tagline',
                    'writer', 'imdbnumber', 'premiered', 'mpaa', 'trailer', 'votes',
                    'country', 'dateadded', 'studio', 'art'
                ]
            }

            response = self.jsonrpc.execute(method, params)
            details = response.get('result', {}).get('moviedetails', {})

            if details:
                # Convert cast to expected format and JSON string
                cast_list = details.get('cast', [])
                cast = [{'name': actor.get('name'), 'role': actor.get('role'), 
                        'order': actor.get('order'), 'thumbnail': actor.get('thumbnail')} 
                       for actor in cast_list]

                # Get art dictionary once
                art_dict = details.get('art', {})
                poster_url = art_dict.get('poster', '')
                utils.log(f"Got art dictionary: {art_dict}", "DEBUG")
                utils.log(f"Extracted poster URL: {poster_url}", "DEBUG")
                utils.log(f"Full art keys available: {list(art_dict.keys())}", "DEBUG")
                
                media_info = {
                    'kodi_id': kodi_id,
                    'title': details.get('title', ''),
                    'poster': poster_url,
                    'art': art_dict.copy(),  # Make a copy to prevent reference issues
                    'thumbnail': art_dict.get('thumb', poster_url),
                    'year': details.get('year', ''),
                    'plot': details.get('plot', ''),
                    'genre': ' / '.join(details.get('genre', [])),
                    'director': ' / '.join(details.get('director', [])),
                    'cast': json.dumps(cast),
                    'rating': details.get('rating', ''),
                    'file': details.get('file', ''),
                    'fanart': art_dict.get('fanart', ''),
                    'duration': details.get('runtime', ''),
                    'type': media_type
                }

        # Fallback to current method for non-library items
        utils.log("Using fallback method for non-library item", "DEBUG")
        info = {
            'kodi_id': kodi_id,
            'title': xbmc.getInfoLabel('ListItem.Title'),
            'year': xbmc.getInfoLabel('ListItem.Year'),
            'plot': xbmc.getInfoLabel('ListItem.Plot'),
            'genre': xbmc.getInfoLabel('ListItem.Genre'),
            'director': xbmc.getInfoLabel('ListItem.Director'),
            'cast': self.get_cast_info(),
            'rating': xbmc.getInfoLabel('ListItem.Rating'),
            'file': xbmc.getInfoLabel('ListItem.FileNameAndPath'),
            'thumbnail': xbmc.getInfoLabel('ListItem.Art(poster)'),
            'fanart': xbmc.getInfoLabel('ListItem.Art(fanart)'),
            'poster': xbmc.getInfoLabel('ListItem.Art(poster)'),  # Store poster URL explicitly
            'duration': xbmc.getInfoLabel('ListItem.Duration'),
            'type': media_type
        }
        return {k: v for k, v in info.items() if v}

    def get_cast_info(self):
        """Get cast information for current media"""
        cast = []
        i = 1
        while True:
            name = xbmc.getInfoLabel(f'ListItem.CastAndRole.{i}.Name')
            if not name:
                break
            cast.append({
                'name': name,
                'role': xbmc.getInfoLabel(f'ListItem.CastAndRole.{i}.Role'),
                'order': i - 1,
                'thumbnail': xbmc.getInfoLabel(f'ListItem.CastAndRole.{i}.Thumb')
            })
            i += 1
        return json.dumps(cast)