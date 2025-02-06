
import xbmc
import json
from resources.lib import utils

class MediaManager:
    def get_media_info(self, media_type='movie'):
        """Get media info from Kodi"""
        info = {
            'kodi_id': xbmc.getInfoLabel('ListItem.DBID'),
            'title': xbmc.getInfoLabel('ListItem.Title'),
            'year': xbmc.getInfoLabel('ListItem.Year'),
            'plot': xbmc.getInfoLabel('ListItem.Plot'),
            'genre': xbmc.getInfoLabel('ListItem.Genre'),
            'director': xbmc.getInfoLabel('ListItem.Director'),
            'cast': self.get_cast_info(),
            'rating': xbmc.getInfoLabel('ListItem.Rating'),
            'file': xbmc.getInfoLabel('ListItem.FileNameAndPath'),
            'thumbnail': xbmc.getInfoLabel('ListItem.Art(thumb)') or xbmc.getInfoLabel('ListItem.Art(poster)'),
            'fanart': xbmc.getInfoLabel('ListItem.Art(fanart)'),
            'art': {
                'poster': xbmc.getInfoLabel('ListItem.Art(poster)'),
                'thumb': xbmc.getInfoLabel('ListItem.Art(thumb)'),
                'fanart': xbmc.getInfoLabel('ListItem.Art(fanart)'),
                'banner': xbmc.getInfoLabel('ListItem.Art(banner)')
            },
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
