"""
ListItem Builder for LibraryGenie
Minimum supported Kodi version: 19 (Matrix)
This module does not support Kodi 18 (Leia) or earlier versions
"""
import json
import xbmcgui
import xbmc
from resources.lib.kodi.listitem_infotagvideo import set_info_tag, set_art
from resources.lib.utils import utils

from urllib.parse import quote, urlparse

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
    from resources.lib.config.addon_ref import get_addon
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

    # Class variable to track if we've logged IMDB_TRACE info
    _imdb_trace_logged = False
    _trace_end_logged = False # Added to ensure trace end is logged only once

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
    def build_video_item(item_data):
        """Build a video ListItem with comprehensive metadata using version-aware API"""
        if not item_data:
            utils.log("No item data provided to build_video_item", "WARNING")
            return xbmcgui.ListItem()

        try:
            # Extract basic info with safe defaults
            title = str(item_data.get('title', 'Unknown Title'))
            year = item_data.get('year', 0)

            # Create ListItem with proper label
            list_item = xbmcgui.ListItem(label=title)

            # Use version-specific API to avoid deprecation warnings
            if utils.is_kodi_v20_plus():
                # Use Kodi v20+ InfoTag API for comprehensive metadata
                info_tag = list_item.getVideoInfoTag()

                # Set basic metadata
                if title:
                    info_tag.setTitle(title)
                if year and year > 0:
                    info_tag.setYear(int(year))

                # Plot/description
                plot = item_data.get('plot', '')
                if plot:
                    info_tag.setPlot(plot)

                # Tagline
                tagline = item_data.get('tagline', '')
                if tagline:
                    info_tag.setTagLine(tagline)

                # Rating
                rating = item_data.get('rating', 0)
                if rating and rating > 0:
                    try:
                        info_tag.setRating(float(rating))
                    except (ValueError, TypeError):
                        pass

                # Runtime/Duration
                duration = item_data.get('duration', 0) or item_data.get('runtime', 0)
                if duration and duration > 0:
                    try:
                        info_tag.setDuration(int(duration))
                    except (ValueError, TypeError):
                        pass

                # Premiered date
                premiered = item_data.get('premiered', '')
                if premiered:
                    info_tag.setPremiered(premiered)

                # Date added
                dateadded = item_data.get('dateadded', '')
                if dateadded:
                    info_tag.setDateAdded(dateadded)

                # IMDb number
                imdbnumber = item_data.get('imdbnumber', '')
                if imdbnumber and str(imdbnumber).startswith('tt'):
                    info_tag.setIMDBNumber(imdbnumber)

                # MPAA rating
                mpaa = item_data.get('mpaa', '')
                if mpaa:
                    info_tag.setMpaa(mpaa)

                # Media type
                media_type = item_data.get('mediatype', item_data.get('media_type', 'movie'))
                info_tag.setMediaType(media_type)

                # Handle list fields (genre, director, writer, etc.)
                genre = item_data.get('genre', [])
                if isinstance(genre, str):
                    genre = [g.strip() for g in genre.split('/') if g.strip()]
                if genre:
                    info_tag.setGenres(genre)

                director = item_data.get('director', [])
                if isinstance(director, str):
                    director = [d.strip() for d in director.split('/') if d.strip()]
                if director:
                    info_tag.setDirectors(director)

                writer = item_data.get('writer', [])
                if isinstance(writer, str):
                    writer = [w.strip() for w in writer.split('/') if w.strip()]
                if writer:
                    info_tag.setWriters(writer)

                studio = item_data.get('studio', [])
                if isinstance(studio, str):
                    studio = [s.strip() for s in studio.split('/') if s.strip()]
                if studio:
                    info_tag.setStudios(studio)

                country = item_data.get('country', [])
                if isinstance(country, str):
                    country = [c.strip() for c in country.split('/') if c.strip()]
                if country:
                    info_tag.setCountries(country)

                # Cast information
                cast_data = item_data.get('cast', [])
                if cast_data:
                    if isinstance(cast_data, str):
                        try:
                            import json
                            cast_data = json.loads(cast_data)
                        except:
                            cast_data = []

                    if isinstance(cast_data, list) and cast_data:
                        cast_list = []
                        for actor in cast_data[:20]:  # Limit to 20 actors
                            if isinstance(actor, dict):
                                name = actor.get('name', '')
                                role = actor.get('role', '')
                                if name:
                                    cast_list.append(xbmc.Actor(name, role))
                        if cast_list:
                            info_tag.setCast(cast_list)

                success_count = len([x for x in [title, year, plot, rating, duration] if x])
                utils.log(f"V20+ InfoTag processing completed with {success_count} successful fields", "DEBUG")

            else:
                # Use legacy setInfo API for Kodi v19 and earlier to avoid warnings
                info_labels = {}

                if title:
                    info_labels['title'] = title
                if year and year > 0:
                    info_labels['year'] = int(year)

                plot = item_data.get('plot', '')
                if plot:
                    info_labels['plot'] = plot

                tagline = item_data.get('tagline', '')
                if tagline:
                    info_labels['tagline'] = tagline

                rating = item_data.get('rating', 0)
                if rating and rating > 0:
                    try:
                        info_labels['rating'] = float(rating)
                    except (ValueError, TypeError):
                        pass

                duration = item_data.get('duration', 0) or item_data.get('runtime', 0)
                if duration and duration > 0:
                    try:
                        info_labels['duration'] = int(duration)
                    except (ValueError, TypeError):
                        pass

                premiered = item_data.get('premiered', '')
                if premiered:
                    info_labels['premiered'] = premiered

                dateadded = item_data.get('dateadded', '')
                if dateadded:
                    info_labels['dateadded'] = dateadded

                imdbnumber = item_data.get('imdbnumber', '')
                if imdbnumber and str(imdbnumber).startswith('tt'):
                    info_labels['imdbnumber'] = imdbnumber

                mpaa = item_data.get('mpaa', '')
                if mpaa:
                    info_labels['mpaa'] = mpaa

                media_type = item_data.get('mediatype', item_data.get('media_type', 'movie'))
                info_labels['mediatype'] = media_type

                # Handle list fields as strings for v19
                genre = item_data.get('genre', [])
                if isinstance(genre, list):
                    genre = ' / '.join(genre)
                if genre:
                    info_labels['genre'] = genre

                director = item_data.get('director', [])
                if isinstance(director, list):
                    director = ' / '.join(director)
                if director:
                    info_labels['director'] = director

                writer = item_data.get('writer', [])
                if isinstance(writer, list):
                    writer = ' / '.join(writer)
                if writer:
                    info_labels['writer'] = writer

                studio = item_data.get('studio', [])
                if isinstance(studio, list):
                    studio = ' / '.join(studio)
                if studio:
                    info_labels['studio'] = studio

                country = item_data.get('country', [])
                if isinstance(country, list):
                    country = ' / '.join(country)
                if country:
                    info_labels['country'] = country

                # Cast information for v19
                cast_data = item_data.get('cast', [])
                if cast_data:
                    if isinstance(cast_data, str):
                        try:
                            import json
                            cast_data = json.loads(cast_data)
                        except:
                            cast_data = []

                    if isinstance(cast_data, list) and cast_data:
                        cast_list = []
                        for actor in cast_data[:20]:  # Limit to 20 actors
                            if isinstance(actor, dict):
                                name = actor.get('name', '')
                                role = actor.get('role', '')
                                if name and role:
                                    cast_list.append({'name': name, 'role': role})
                        if cast_list:
                            info_labels['cast'] = cast_list

                # Apply all info labels at once for v19
                list_item.setInfo('video', info_labels)

                success_count = len(info_labels)
                utils.log(f"V19 setInfo processing completed with {success_count} successful fields", "DEBUG")

            # Art and images (same for both versions)
            art_dict = {}

            # Poster/thumbnail
            poster = item_data.get('poster') or item_data.get('thumbnail', '')
            if poster:
                art_dict['poster'] = poster
                art_dict['thumb'] = poster

            # Fanart
            fanart = item_data.get('fanart', '')
            if fanart:
                art_dict['fanart'] = fanart

            # Set art if we have any
            if art_dict:
                list_item.setArt(art_dict)

            # Properties for playback
            list_item.setProperty('IsPlayable', 'true')

            # Add search score as property if present
            search_score = item_data.get('search_score', 0)
            if search_score and search_score > 0:
                list_item.setProperty('search_score', str(search_score))

            return list_item

        except Exception as e:
            utils.log(f"Error building video item: {str(e)}", "ERROR")
            # Fallback to basic ListItem
            title = str(item_data.get('title', 'Unknown Title'))
            list_item = xbmcgui.ListItem(label=title)
            list_item.setProperty('IsPlayable', 'true')
            return list_item


    @staticmethod
    def build_folder_item(name, is_folder=True, item_type='folder', plot=''):
        """Build a folder ListItem with addon artwork

        Args:
            name: Display name for the item
            is_folder: Whether this is a folder item
            item_type: Type of item ('folder', 'playlist', 'list') to determine icon
            plot: Plot/description text for the item
        """
        from resources.lib.config.addon_ref import get_addon
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