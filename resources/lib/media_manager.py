import xbmc
import json
from .config_manager import Config
from . import utils
from .jsonrpc_manager import JSONRPC

class MediaManager:
    def __init__(self):
        self.jsonrpc = JSONRPC()
        from resources.lib.query_manager import QueryManager
        self.query_manager = QueryManager(Config().db_path)

    def get_media_info(self, media_type='movie'):
        """Get media info from Kodi"""
        from resources.lib.query_manager import QueryManager
        self.query_manager = QueryManager(Config().db_path)
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

                # Get art dictionary with detailed logging
                art_dict = details.get('art', {})
                poster_url = art_dict.get('poster', '')

                if not poster_url:
                    poster_url = details.get('thumbnail', '')
                    utils.log(f"Poster fallback to thumbnail: {poster_url}", "DEBUG")

                # Ensure art dictionary has all required fields
                art_dict = {
                    'poster': poster_url,
                    'thumb': poster_url,
                    'icon': poster_url,
                    'fanart': art_dict.get('fanart', '')
                }

                media_info = {
                    'kodi_id': kodi_id,
                    'title': details.get('title', ''),
                    'art': json.dumps(art_dict),  # Store art as JSON string
                    'thumbnail': poster_url,  # Keep thumbnail for compatibility
                    'poster': poster_url,  # Explicitly store poster URL
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
                
                # Assuming ListItemBuilder is imported and available in this scope
                from resources.lib.listitem_builder import ListItemBuilder
                movie_data = media_info
                list_item = ListItemBuilder.build_video_item(movie_data, is_search_history=False)


        # Fallback to current method for non-library items
        utils.log("Using fallback method for non-library item", "DEBUG")
        
        # Get basic info from current ListItem
        title = xbmc.getInfoLabel('ListItem.Title')
        year = xbmc.getInfoLabel('ListItem.Year')
        plot = xbmc.getInfoLabel('ListItem.Plot')
        
        # Try to get IMDb ID from various sources
        imdb_candidates = [
            xbmc.getInfoLabel('ListItem.IMDBNumber'),
            xbmc.getInfoLabel('ListItem.UniqueID(imdb)'),
            xbmc.getInfoLabel('ListItem.Property(LibraryGenie.IMDbID)'),
            xbmc.getInfoLabel('ListItem.Property(imdb_id)'),
            xbmc.getInfoLabel('ListItem.Property(imdbnumber)')
        ]
        
        imdb_id = None
        for candidate in imdb_candidates:
            if candidate and str(candidate).startswith('tt'):
                imdb_id = candidate
                break
        
        info = {
            'kodi_id': kodi_id if kodi_id and kodi_id.isdigit() else None,
            'title': title,
            'year': year,
            'plot': plot,
            'genre': xbmc.getInfoLabel('ListItem.Genre'),
            'director': xbmc.getInfoLabel('ListItem.Director'),
            'cast': self.get_cast_info(),
            'rating': xbmc.getInfoLabel('ListItem.Rating'),
            'file': xbmc.getInfoLabel('ListItem.FileNameAndPath'),
            'thumbnail': xbmc.getInfoLabel('ListItem.Art(poster)'),
            'fanart': xbmc.getInfoLabel('ListItem.Art(fanart)'),
            'poster': xbmc.getInfoLabel('ListItem.Art(poster)'),
            'duration': xbmc.getInfoLabel('ListItem.Duration'),
            'type': media_type,
            'imdbnumber': imdb_id,
            'source': 'plugin_addon'  # Mark as coming from plugin addon
        }
        
        # Clean up empty values but keep essential fields
        cleaned_info = {}
        for k, v in info.items():
            if k in ['title', 'source', 'type']:  # Always keep these essential fields
                cleaned_info[k] = v or ('Unknown' if k == 'title' else v)
            elif v:  # Keep non-empty values
                cleaned_info[k] = v
        
        utils.log(f"Fallback media info extracted: title='{cleaned_info.get('title')}', imdb='{cleaned_info.get('imdbnumber')}', source='{cleaned_info.get('source')}'", "DEBUG")
        
        return cleaned_info


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