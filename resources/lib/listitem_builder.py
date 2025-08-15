"""
ListItem Builder for LibraryGenie
Minimum supported Kodi version: 19 (Matrix)
This module does not support Kodi 18 (Leia) or earlier versions
"""
import json
import xbmcgui
import xbmc
from resources.lib import utils
from resources.lib.listitem_infotagvideo import set_info_tag, set_art
from typing import Dict
from urllib.parse import quote, urlparse, quote_plus
import os


__all__ = ['set_info_tag', 'set_art']

VALID_SCHEMES = {'image', 'http', 'https', 'file', 'smb', 'nfs', 'ftp', 'ftps', 'plugin', 'special'}

def _is_valid_art_url(u: str) -> bool:
    if not u:
        return False
    # Accept Kodi image wrapper directly
    if u.startswith("image://"):
        return True
    # Accept special:// paths (including PNG files)
    if u.startswith("special://"):
        return True
    p = urlparse(u)
    return p.scheme in VALID_SCHEMES

def _wrap_for_kodi_image(u: str) -> str:
    """
    If already 'image://', return as-is.
    Otherwise wrap raw URL/path into Kodi's image://<percent-encoded>/
    Avoid double-encoding by keeping '%' safe when source is already encoded.
    """
    if not u:
        return u
    if u.startswith("image://"):
        # Ensure trailing slash; Kodi expects it
        return u if u.endswith("/") else (u + "/")
    # Keep '%' to avoid double-encoding already-encoded inputs;
    # keep common URL reserved chars safe so URLs remain valid.
    enc = quote(u, safe=":/%?&=#,+@;[]()!*._-")
    return f"image://{enc}/"

def _get_addon_artwork_fallbacks() -> dict:
    """Return addon artwork that can be used as fallbacks"""
    from resources.lib.addon_ref import get_addon
    addon = get_addon()
    addon_path = addon.getAddonInfo("path")
    media = f"{addon_path}/resources/media"

    return {
        'icon': f"{media}/icon.jpg",
        'thumb': f"{media}/thumb.jpg",
        'poster': f"{media}/icon.jpg",
        'fanart': f"{media}/fanart.jpg",
        'banner': f"{media}/banner.jpg",
        'landscape': f"{media}/landscape.jpg",
        'clearart': f"{media}/clearart.jpg",
        'clearlogo': f"{media}/clearlogo.png",
        'folder': f"{media}/list_folder.png",
        'playlist': f"{media}/list_playlist.png"
    }

def _normalize_art_dict(art: dict, use_fallbacks: bool = False) -> dict:
    out = {}
    if not isinstance(art, dict):
        art = {}

    # Add addon artwork as fallbacks if requested
    if use_fallbacks:
        fallbacks = _get_addon_artwork_fallbacks()
        for k, v in fallbacks.items():
            if k not in art or not art[k]:
                art[k] = v

    # Use paths directly - let Kodi handle them
    for k, v in art.items():
        if not v:
            continue
        vv = str(v).strip()
        if vv:
            out[k] = vv

    return out


class ListItemBuilder:

    # Color map for score indication (AARRGGBB format) - bleached/lighter versions
    SCORE_COLORS = {
        "green":  "FF7BC99A",  # High scores (7.0+) - lighter green
        "yellow": "FFF0DC8A",  # Good scores (6.0-6.9) - lighter yellow
        "orange": "FFF4BC7B",  # Average scores (5.0-5.9) - lighter orange
        "red":    "FFECA9A7",  # Low scores (below 5.0) - lighter red
    }

    @staticmethod
    def _get_score_bucket(score: float) -> str:
        """Map score to color bucket"""
        if score >= 7.0:
            return "green"
        elif score >= 6.0:
            return "yellow"
        elif score >= 5.0:
            return "orange"
        else:
            return "red"

    @staticmethod
    def _colorize_title_by_score(title: str, score: float) -> str:
        """Apply Kodi color formatting to title based on score"""
        color_bucket = ListItemBuilder._get_score_bucket(score)
        color_hex = ListItemBuilder.SCORE_COLORS[color_bucket]
        return f"[COLOR {color_hex}]{title}[/COLOR]"

    @staticmethod
    def _clean_title(title):
        """Remove emoji characters and other problematic Unicode that Kodi can't render"""
        import re
        if not title:
            return title

        # Remove emoji characters (covers most emoji ranges)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"  # dingbats
            "\U000024C2-\U0001F251"  # enclosed characters
            "]+",
            flags=re.UNICODE
        )

        # Remove emojis and clean up extra spaces
        cleaned = emoji_pattern.sub('', title).strip()

        # Remove multiple spaces and clean up
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned

    @staticmethod
    def build_video_item(media_info, is_search_history=False):
        """Build a complete video ListItem with all available metadata"""
        if not isinstance(media_info, dict):
            media_info = {}

        # Basic info extraction
        title = str(media_info.get('title', 'Unknown'))


        # Create ListItem with proper string title (remove emoji characters)
        formatted_title = ListItemBuilder._clean_title(title)

        # Apply color coding based on search score only for Search History lists
        search_score = media_info.get('search_score')
        if is_search_history and search_score and search_score > 0:
            # Color the title based on score without showing the numeric value
            formatted_title = ListItemBuilder._colorize_title_by_score(formatted_title, search_score)

        # Create the ListItem
        li = xbmcgui.ListItem(label=formatted_title)



        # Prepare artwork dictionary
        art_dict = {}

        # Get poster URL with priority order
        poster_url = None
        for source in [
            lambda: media_info.get('poster'),
            lambda: media_info.get('art', {}).get('poster') if isinstance(media_info.get('art'), dict) else None,
            lambda: media_info.get('info', {}).get('poster'),
            lambda: media_info.get('thumbnail')
        ]:
            try:
                url = source()
                if url and str(url) != 'None':
                    poster_url = url
                    break
            except Exception:
                # utils.log(f"Error getting poster URL: {str(e)}", "ERROR")
                continue

        # Handle art data from different sources
        if media_info.get('art'):
            try:
                if isinstance(media_info['art'], str):
                    art_data = json.loads(media_info['art'])
                else:
                    art_data = media_info['art']
                art_dict.update(art_data)
            except (json.JSONDecodeError, AttributeError, TypeError):
                pass

        # Get art dictionary from info if available
        if isinstance(media_info.get('info', {}).get('art'), dict):
            art_dict.update(media_info['info']['art'])

        # Set poster with fallbacks
        if poster_url and str(poster_url) != 'None':
            art_dict['poster'] = poster_url
            art_dict['thumb'] = poster_url
            art_dict['icon'] = poster_url

        # Set fanart
        fanart = media_info.get('fanart') or media_info.get('info', {}).get('fanart')
        if fanart and str(fanart) != 'None':
            art_dict['fanart'] = fanart

        # Use the specialized set_art function with improved normalization and fallbacks
        art_dict = _normalize_art_dict(art_dict, use_fallbacks=True)
        # Set art from art_dict
        if art_dict:
            set_art(li, art_dict)

        # Create info dictionary for InfoTag
        info_dict = {
            'title': formatted_title,
            'plot': media_info.get('plot', ''),
            'tagline': media_info.get('tagline', ''),
            'country': media_info.get('country', ''),
            'director': media_info.get('director', ''),
            'genre': media_info.get('genre', ''),
            'mpaa': media_info.get('mpaa', ''),
            'premiered': media_info.get('premiered', ''),
            'studio': media_info.get('studio', ''),
            'trailer': media_info.get('trailer', ''),
            'writer': media_info.get('writer', ''),
            'mediatype': (media_info.get('media_type') or media_info.get('mediatype') or 'movie').lower()
        }

        # Handle numeric fields with proper conversion
        if media_info.get('year'):
            try:
                year_val = media_info['year']
                # Handle both integer and string years
                if isinstance(year_val, str) and year_val.isdigit():
                    info_dict['year'] = int(year_val)
                elif isinstance(year_val, (int, float)) and year_val > 0:
                    info_dict['year'] = int(year_val)
            except (ValueError, TypeError):
                pass

        if media_info.get('rating'):
            try:
                info_dict['rating'] = float(media_info['rating'])
            except (ValueError, TypeError):
                pass

        if media_info.get('votes'):
            try:
                info_dict['votes'] = int(media_info['votes'])
            except (ValueError, TypeError):
                pass

        # Handle runtime/duration
        if media_info.get('runtime'):
            try:
                info_dict['duration'] = int(media_info['runtime'])
            except (ValueError, TypeError):
                pass

        # Handle user rating
        if media_info.get('userrating'):
            try:
                info_dict['userrating'] = float(media_info['userrating'])
            except (ValueError, TypeError):
                pass

        # Handle top250 ranking
        if media_info.get('top250'):
            try:
                info_dict['top250'] = int(media_info['top250'])
            except (ValueError, TypeError):
                pass

        # Handle playcount
        if media_info.get('playcount'):
            try:
                info_dict['playcount'] = int(media_info['playcount'])
            except (ValueError, TypeError):
                pass

        # Handle date fields
        for date_field in ['dateadded', 'lastplayed', 'premiered']:
            if media_info.get(date_field):
                info_dict[date_field] = str(media_info[date_field])

        # Handle set information
        if media_info.get('set'):
            info_dict['set'] = str(media_info['set'])
        if media_info.get('setid'):
            try:
                info_dict['setid'] = int(media_info['setid'])
            except (ValueError, TypeError):
                pass

        # Handle multiple ratings (v19+)
        if media_info.get('ratings') and isinstance(media_info['ratings'], dict):
            # Use the default rating or first available rating
            for rating_source in ['default', 'imdb', 'themoviedb', 'thetvdb']:
                if rating_source in media_info['ratings']:
                    rating_data = media_info['ratings'][rating_source]
                    if isinstance(rating_data, dict) and 'rating' in rating_data:
                        try:
                            info_dict['rating'] = float(rating_data['rating'])
                            if 'votes' in rating_data:
                                info_dict['votes'] = int(rating_data['votes'])
                        except (ValueError, TypeError):
                            pass
                        break

        # Handle cast data
        cast = media_info.get('cast', [])
        if cast:
            try:
                # Handle string-encoded cast data
                if isinstance(cast, str):
                    try:
                        cast = json.loads(cast)
                    except json.JSONDecodeError:
                        cast = []

                # Ensure cast is a list
                if not isinstance(cast, list):
                    cast = []

                info_dict['cast'] = cast

            except Exception as e:
                info_dict['cast'] = []

        # Process plot information
        if media_info.get('plot'):
            pass

        # Use the specialized set_info_tag function that handles Kodi version compatibility
        set_info_tag(li, info_dict, 'video')

        # Handle resume data with v20+ compatibility
        resume_data = media_info.get('resume', {})
        if isinstance(resume_data, dict) and any(resume_data.values()):
            try:
                position = float(resume_data.get('position', 0))
                total = float(resume_data.get('total', 0))

                if position > 0:
                    if utils.is_kodi_v20_plus():
                        # Use v20+ InfoTag method to avoid deprecation warnings
                        try:
                            info_tag = li.getVideoInfoTag()
                            if hasattr(info_tag, 'setResumePoint'):
                                info_tag.setResumePoint(position, total)
                            else:
                                # Fallback to deprecated method
                                li.setProperty('resumetime', str(position))
                                if total > 0:
                                    li.setProperty('totaltime', str(total))
                        except Exception:
                            # Fallback to deprecated method
                            li.setProperty('resumetime', str(position))
                            if total > 0:
                                li.setProperty('totaltime', str(total))
                    else:
                        # v19 - use deprecated methods
                        li.setProperty('resumetime', str(position))
                        if total > 0:
                            li.setProperty('totaltime', str(total))
            except (ValueError, TypeError):
                pass


        # Handle stream details with v20+ compatibility
        stream_details = media_info.get('streamdetails', {})
        if isinstance(stream_details, dict):
            try:
                if utils.is_kodi_v20_plus():
                    # Use v20+ InfoTag methods to avoid deprecation warnings
                    try:
                        info_tag = li.getVideoInfoTag()
                        # Skip stream detail methods as they are not reliably handled by v20+ InfoTag
                        # Use property fallback instead
                        _add_stream_info_deprecated(li, stream_details)
                    except Exception:
                        # Fallback to deprecated methods
                        _add_stream_info_deprecated(li, stream_details)
                else:
                    # v19 - use deprecated methods
                    _add_stream_info_deprecated(li, stream_details)
            except Exception as e:
                pass

        # Set content properties
        li.setProperty('IsPlayable', 'true')

        # Set DBID for Kodi Information dialog support
        kodi_id = media_info.get('kodi_id') or media_info.get('movieid') or media_info.get('id')
        if kodi_id:
            li.setProperty('DBID', str(kodi_id))

        # Set MediaType property for Kodi recognition
        media_type = info_dict.get('mediatype', 'movie')
        li.setProperty('MediaType', media_type)

        # Add Information context menu item
        context_menu_items = []
        # Original line: context_menu_items.append(('Show Details', f'RunPlugin(plugin://script.librarygenie/?action=show_item_details&title={quote(title)}&item_id={media_info.get("id", "")})')))
        # Updated line:
        context_menu_items.append(('Show Details', f'RunPlugin(plugin://script.librarygenie/?action=show_item_details&title={quote_plus(formatted_title)}&item_id={media_info.get("id", "")})'))
        context_menu_items.append(('Information', 'Action(Info)'))

        # Add context menu to ListItem
        li.addContextMenuItems(context_menu_items, replaceItems=False)



        # Try to get play URL from different possible locations
        play_url = media_info.get('info', {}).get('play') or media_info.get('play') or media_info.get('file')
        if play_url:
            li.setPath(play_url)

        return li

    @staticmethod
    def build_folder_item(name, is_folder=True, item_type='folder', plot=''):
        """Build a folder ListItem with addon artwork

        Args:
            name: Display name for the item
            is_folder: Whether this is a folder item
            item_type: Type of item ('folder', 'playlist', 'list') to determine icon
            plot: Plot/description text for the item
        """
        from resources.lib.addon_ref import get_addon
        from resources.lib import utils
        addon = get_addon()
        addon_path = addon.getAddonInfo("path")
        media = f"{addon_path}/resources/media"

        # Clean the title to remove emoji and get base name
        clean_name = ListItemBuilder._clean_title(name)

        list_item = xbmcgui.ListItem(label=clean_name)
        list_item.setIsFolder(is_folder)

        # Choose appropriate icon based on item type
        if item_type in ['playlist', 'list']:
            icon_path = f"{media}/list_playlist.png"
        else:
            icon_path = f"{media}/list_folder.png"

        # Set folder-appropriate artwork using direct paths
        folder_art = {
            'icon': icon_path,
            'thumb': icon_path,
            'poster': icon_path,
            'fanart': f"{media}/fanart.jpg"
        }

        # Set artwork directly without complex processing
        set_art(list_item, folder_art)

        # Set plot information if provided
        if plot:
            info_dict = {
                'plot': plot,
                'mediatype': 'video'
            }
            set_info_tag(list_item, info_dict, 'video')

        return list_item

    @staticmethod
    def add_context_menu(list_item, menu_items):
        """Add context menu items to ListItem"""
        list_item.addContextMenuItems(menu_items, replaceItems=True)

    @staticmethod
    def _add_stream_info_deprecated(list_item, stream_details):
        """Adds stream details using deprecated methods for compatibility with older Kodi versions."""
        # This method is a fallback for versions where setVideoStream, setAudioStream, setSubtitleStream are deprecated
        # or not available. It aims to set properties that might be recognized by older Kodi clients or skins.
        video_streams = stream_details.get('video', [])
        audio_streams = stream_details.get('audio', [])
        subtitle_streams = stream_details.get('subtitle', [])

        if video_streams:
            for stream in video_streams:
                if isinstance(stream, dict):
                    codec = stream.get('codec', '')
                    resolution = stream.get('resolution', '')
                    aspect_ratio = stream.get('aspect_ratio', '')
                    lang = stream.get('language', '')

                    # Construct a string that might be interpretable by skins/players
                    stream_str = f"Video: Codec({codec}), Res({resolution}), Aspect({aspect_ratio}), Lang({lang})"
                    # Using generic properties as specific ones are deprecated
                    list_item.setProperty('VideoCodec', codec)
                    list_item.setProperty('VideoResolution', resolution)
                    list_item.setProperty('VideoAspectRatio', aspect_ratio)
                    list_item.setProperty('VideoLanguage', lang)

        if audio_streams:
            for stream in audio_streams:
                if isinstance(stream, dict):
                    codec = stream.get('codec', '')
                    channels = stream.get('channels', '')
                    language = stream.get('language', '')
                    bitrate = stream.get('bitrate', '')

                    list_item.setProperty('AudioCodec', codec)
                    list_item.setProperty('AudioChannels', str(channels))
                    list_item.setProperty('AudioLanguage', language)
                    list_item.setProperty('AudioBitrate', str(bitrate))

        if subtitle_streams:
            for stream in subtitle_streams:
                if isinstance(stream, dict):
                    language = stream.get('language', '')
                    codec = stream.get('codec', '')
                    forced = stream.get('forced', False)

                    list_item.setProperty('SubtitleLanguage', language)
                    list_item.setProperty('SubtitleCodec', codec)
                    list_item.setProperty('SubtitleForced', str(forced).lower())