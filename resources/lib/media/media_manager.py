import xbmc
import json
from resources.lib.config.config_manager import Config
from resources.lib.utils import utils
from resources.lib.integrations.jsonrpc.jsonrpc_manager import JSONRPC

class MediaManager:
    def __init__(self):
        self.jsonrpc = JSONRPC()
        from resources.lib.data.query_manager import QueryManager
        self.query_manager = QueryManager(Config().db_path)

    def get_media_info(self, media_type='movie'):
        """Extract media information from the currently focused Kodi item"""
        try:
            utils.log("=== MEDIA_MANAGER: Starting get_media_info ===", "DEBUG")

            # Get basic info that's always available
            title = xbmc.getInfoLabel('ListItem.Title') or ''
            year = xbmc.getInfoLabel('ListItem.Year') or ''
            plot = xbmc.getInfoLabel('ListItem.Plot') or ''

            # Get file path - try multiple sources
            file_path = (xbmc.getInfoLabel('ListItem.FileNameAndPath') or 
                        xbmc.getInfoLabel('ListItem.Path') or 
                        xbmc.getInfoLabel('ListItem.FolderPath') or '')

            utils.log(f"MEDIA_MANAGER: Basic info - Title: '{title}', Year: '{year}', File: '{file_path}'", "DEBUG")

            # Get additional metadata with fallbacks
            genre = xbmc.getInfoLabel('ListItem.Genre') or ''
            director = xbmc.getInfoLabel('ListItem.Director') or ''

            # Handle duration - convert to integer
            duration_str = xbmc.getInfoLabel('ListItem.Duration') or '0'
            try:
                duration = int(duration_str) if duration_str.isdigit() else 0
            except:
                duration = 0

            # Get art with multiple fallback sources
            thumbnail = (xbmc.getInfoLabel('ListItem.Thumb') or 
                        xbmc.getInfoLabel('ListItem.Art(thumb)') or '')
            poster = (xbmc.getInfoLabel('ListItem.Art(poster)') or 
                     xbmc.getInfoLabel('ListItem.Thumb') or '')
            fanart = (xbmc.getInfoLabel('ListItem.Art(fanart)') or 
                     xbmc.getInfoLabel('ListItem.Property(fanart_image)') or '')

            # Try to get IMDb ID from various sources
            imdb_id = ''
            try:
                # Try different IMDb ID sources
                imdb_sources = [
                    'ListItem.IMDBNumber',
                    'ListItem.Property(imdb_id)',
                    'ListItem.UniqueId(imdb)',
                    'ListItem.Property(imdb)',
                ]

                for source in imdb_sources:
                    imdb_candidate = xbmc.getInfoLabel(source)
                    if imdb_candidate and imdb_candidate.startswith('tt'):
                        imdb_id = imdb_candidate
                        utils.log(f"MEDIA_MANAGER: Found IMDb ID from {source}: {imdb_id}", "DEBUG")
                        break

            except Exception as e:
                utils.log(f"MEDIA_MANAGER: Error getting IMDb ID: {str(e)}", "DEBUG")

            # Enhance plot for plugin items
            if not imdb_id and file_path:
                # Determine source addon from file path
                source_addon = 'external addon'
                if 'plugin://' in file_path:
                    try:
                        plugin_part = file_path.split('plugin://')[1].split('/')[0]
                        source_addon = plugin_part
                    except:
                        pass

                if not plot:
                    plot = f"Item from {source_addon}"
                else:
                    plot = f"[{source_addon}] {plot}"

            # Build comprehensive media info
            media_info = {
                'title': title.strip() if title else 'Unknown Title',
                'year': year.strip() if year and year.isdigit() else '',
                'plot': plot.strip() if plot else 'No description available',
                'genre': genre.strip() if genre else '',
                'director': director.strip() if director else '',
                'duration': duration,
                'thumbnail': thumbnail.strip() if thumbnail else '',
                'poster': poster.strip() if poster else '',
                'fanart': fanart.strip() if fanart else '',
                'imdbnumber': imdb_id.strip() if imdb_id else '',
                'source': 'plugin_addon' if not imdb_id else 'library',
                'art': json.dumps({
                    'poster': poster,
                    'fanart': fanart,
                    'thumb': thumbnail
                }) if any([poster, fanart, thumbnail]) else '{}',
                'cast': '[]'  # Empty cast for plugin items
            }

            # Add file path to media info
            media_info['file'] = file_path

            utils.log("MEDIA_MANAGER: Final media info extracted:", "DEBUG")
            utils.log(f"  Title: '{media_info['title']}'", "DEBUG")
            utils.log(f"  Source: '{media_info['source']}'", "DEBUG")
            utils.log(f"  File: '{media_info['file']}'", "DEBUG")
            utils.log(f"  IMDb: '{media_info['imdbnumber']}'", "DEBUG")
            utils.log("=== MEDIA_MANAGER: get_media_info complete ===", "DEBUG")

            return media_info

        except Exception as e:
            utils.log(f"MEDIA_MANAGER: Error in get_media_info: {str(e)}", "ERROR")
            import traceback
            utils.log(f"MEDIA_MANAGER: Traceback: {traceback.format_exc()}", "ERROR")

            # Return minimal info as fallback
            fallback_title = xbmc.getInfoLabel('ListItem.Title') or 'Unknown'
            fallback_file = xbmc.getInfoLabel('ListItem.FileNameAndPath') or ''

            utils.log(f"MEDIA_MANAGER: Using fallback info - Title: '{fallback_title}', File: '{fallback_file}'", "DEBUG")

            return {
                'title': fallback_title,
                'year': '',
                'plot': 'Plugin item added via context menu',
                'file': fallback_file,
                'genre': '',
                'director': '',
                'duration': 0,
                'thumbnail': '',
                'poster': '',
                'fanart': '',
                'imdbnumber': '',
                'source': 'plugin_addon',
                'art': '{}',
                'cast': '[]'
            }

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