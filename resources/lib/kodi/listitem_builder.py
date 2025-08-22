"""
ListItem Builder for LibraryGenie
Minimum supported Kodi version: 19 (Matrix)
This module does not support Kodi 18 (Leia) or earlier versions
"""
import json
import xbmcgui
import threading
from resources.lib.kodi.listitem_infotagvideo import set_info_tag, set_art
from resources.lib.utils import utils

from urllib.parse import quote, urlparse

# Global sync state tracking
_sync_state_lock = threading.Lock()
_active_sync_operations = set()

def set_sync_active(operation_id):
    """Mark a sync operation as active"""
    with _sync_state_lock:
        _active_sync_operations.add(operation_id)
        utils.log(f"SYNC_STATE: Added active sync operation: {operation_id}", "DEBUG")

def set_sync_inactive(operation_id):
    """Mark a sync operation as complete"""
    with _sync_state_lock:
        _active_sync_operations.discard(operation_id)
        utils.log(f"SYNC_STATE: Removed active sync operation: {operation_id}", "DEBUG")

def is_sync_active():
    """Check if any sync operations are currently active"""
    with _sync_state_lock:
        return len(_active_sync_operations) > 0

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
    def build_video_item(item_dict, is_search_history=False):
        """Build a video ListItem from item dictionary"""
        # Get call stack information for debugging
        import inspect
        import threading
        
        current_thread = threading.current_thread()
        stack_frames = inspect.stack()
        caller_info = []
        
        # Collect meaningful caller information (skip current frame)
        for i, frame in enumerate(stack_frames[1:8], 1):  # Check up to 7 levels up
            func_name = frame.function
            file_name = frame.filename.split('/')[-1]  # Just the filename
            line_no = frame.lineno
            caller_info.append(f"{file_name}:{func_name}():{line_no}")
        
        caller_chain = " -> ".join(caller_info)
        title = item_dict.get('title', 'Unknown') if isinstance(item_dict, dict) else 'Unknown'
        source = item_dict.get('source', 'unknown') if isinstance(item_dict, dict) else 'unknown'
        
        utils.log(f"=== LISTITEM_BUILD_VIDEO: Starting for '{title}' (source: {source}) ===", "INFO")
        utils.log(f"LISTITEM_BUILD_VIDEO: Thread: {current_thread.name} (ID: {current_thread.ident})", "INFO")
        utils.log(f"LISTITEM_BUILD_VIDEO: Call chain: {caller_chain}", "INFO")
        utils.log(f"LISTITEM_BUILD_VIDEO: is_search_history: {is_search_history}", "INFO")
        
        # Log if this is happening on a different thread than expected
        main_thread_names = ['MainThread', 'Thread-1', 'CApplication']
        thread_id = current_thread.ident
        
        # Check if this matches the thread from deprecation warnings (T:26384)
        if thread_id == 26384:
            utils.log(f"LISTITEM_BUILD_VIDEO: DEPRECATION_THREAD_DETECTED - This is thread {thread_id} which caused deprecation warnings!", "ERROR")
            utils.log(f"LISTITEM_BUILD_VIDEO: DEPRECATION_THREAD_DETECTED - Call chain: {caller_chain}", "ERROR")
            utils.log(f"LISTITEM_BUILD_VIDEO: DEPRECATION_THREAD_DETECTED - Item source: {source}, title: {title}", "ERROR")
        
        if current_thread.name not in main_thread_names and 'T:' not in current_thread.name:
            utils.log(f"LISTITEM_BUILD_VIDEO: WARNING - Building on unexpected thread: {current_thread.name} (ID: {thread_id})", "WARNING")
            
        # Check for sync-related stack frames and log them specifically
        sync_related_frames = []
        for frame in stack_frames:
            frame_file = frame.filename.split('/')[-1]
            if any(sync_term in frame.function.lower() for sync_term in ['sync', 'favorite', 'import']):
                sync_related_frames.append(f"{frame_file}:{frame.function}():{frame.lineno}")
        
        if sync_related_frames:
            utils.log(f"LISTITEM_BUILD_VIDEO: SYNC_CONTEXT detected in call stack: {' -> '.join(sync_related_frames)}", "WARNING")
        
        # Prevent ListItem building during sync operations
        if item_dict.get('_sync_operation') or item_dict.get('_no_listitem_building') or item_dict.get('_background_sync'):
            utils.log(f"LISTITEM_BUILD_VIDEO: SYNC_PREVENTION - Preventing ListItem building for '{title}' - sync flags detected", "WARNING")
            utils.log(f"LISTITEM_BUILD_VIDEO: SYNC_PREVENTION - Flags: sync={item_dict.get('_sync_operation')}, no_listitem={item_dict.get('_no_listitem_building')}, background={item_dict.get('_background_sync')}", "WARNING")
            return None

        # Check for global sync state first
        if is_sync_active():
            utils.log(f"LISTITEM_BUILD_VIDEO: GLOBAL_SYNC_PREVENTION - Preventing ListItem building for '{title}' - active sync operation detected", "WARNING")
            utils.log(f"LISTITEM_BUILD_VIDEO: GLOBAL_SYNC_PREVENTION - Thread {current_thread.name} (ID: {current_thread.ident}) blocked during sync", "WARNING")
            return None

        # Check thread name for sync operations
        if 'FavoritesSync' in current_thread.name or 'Sync' in current_thread.name:
            utils.log(f"LISTITEM_BUILD_VIDEO: SYNC_PREVENTION - Preventing ListItem building for '{title}' - sync thread detected: {current_thread.name}", "WARNING")
            return None

        # Check call stack for sync functions
        frame_names = [frame.function for frame in stack_frames]
        sync_functions = ['sync_favorites', '_apply_database_changes', 'sync_only_store_media_item_to_list', '_create_media_dict_from_favorite', 'FavoritesSync', 'insert_or_get_media_item']
        detected_sync_functions = [func for func in sync_functions if func in frame_names]
        if detected_sync_functions:
            utils.log(f"LISTITEM_BUILD_VIDEO: SYNC_PREVENTION - CRITICAL - Preventing ListItem building for '{title}' - sync operation in call stack: {detected_sync_functions}", "ERROR")
            utils.log(f"LISTITEM_BUILD_VIDEO: SYNC_PREVENTION - This should have been prevented by sync flags - investigate why flags were bypassed", "ERROR")
            utils.log(f"LISTITEM_BUILD_VIDEO: SYNC_PREVENTION - Full call chain: {caller_chain}", "ERROR")
            return None

        # Additional check for any database operations that might be sync-related
        db_operations = ['execute_query', 'insert_data', 'update_data', 'fetch_list_items_with_details']
        detected_db_ops = [func for func in db_operations if func in frame_names]
        if detected_db_ops and any(sync_term in ' '.join(frame_names).lower() for sync_term in ['sync', 'favorite']):
            utils.log(f"LISTITEM_BUILD_VIDEO: SYNC_PREVENTION - Database operation detected during potential sync: {detected_db_ops}", "ERROR")
            utils.log(f"LISTITEM_BUILD_VIDEO: SYNC_PREVENTION - Frames with sync terms: {[f for f in frame_names if any(sync_term in f.lower() for sync_term in ['sync', 'favorite'])]}", "ERROR")
            return None


        if not isinstance(item_dict, dict):
            item_dict = {}

        # Basic info extraction
        title = str(item_dict.get('title', 'Unknown'))
        source = item_dict.get('source')

        # Create ListItem with proper string title (remove emoji characters)
        formatted_title = ListItemBuilder._clean_title(title)

        # Apply color coding based on search score only for Search History lists
        search_score = item_dict.get('search_score')
        if is_search_history and search_score and search_score > 0:
            # Color the title based on score without showing the numeric value
            formatted_title = ListItemBuilder._colorize_title_by_score(formatted_title, search_score)

        # Create the ListItem
        li = xbmcgui.ListItem(label=formatted_title)

        # Handle plot - prefer plot over tagline, only use title fallback if no other data available
        plot = item_dict.get('plot', '') or item_dict.get('tagline', '')
        if not plot:
            # Only use "Movie:" prefix for items without any plot/tagline data
            if source in ['favorites_import', 'lib', 'kodi_library']:
                # For library-sourced items, just use the title without "Movie:" prefix
                plot = title
            else:
                # For other sources, use the "Movie:" prefix
                plot = f"Movie: {title}"

        # For search history items, enhance plot with match status and score
        if source == 'lib' and item_dict.get('search_score'):
            search_score = item_dict.get('search_score', 0)
            if item_dict.get('is_library_match'):
                plot = f"⭐ IN YOUR LIBRARY (Score: {search_score:.1f})\n\n{plot}"
            else:
                plot = f"📍 Not in library (Score: {search_score:.1f})\n\n{plot}"

        # Prepare artwork dictionary
        art_dict = {}

        # Get poster URL with priority order
        poster_url = None
        for src_func in [
            lambda: item_dict.get('poster'),
            lambda: item_dict.get('art', {}).get('poster') if isinstance(item_dict.get('art'), dict) else None,
            lambda: item_dict.get('thumbnail')
        ]:
            try:
                url = src_func()
                if url and str(url) != 'None':
                    poster_url = url
                    break
            except Exception:

                continue

        # Handle art data from different sources
        if item_dict.get('art'):
            try:
                if isinstance(item_dict['art'], str):
                    art_data = json.loads(item_dict['art'])
                else:
                    art_data = item_dict['art']
                art_dict.update(art_data)
            except (json.JSONDecodeError, AttributeError, TypeError):
                pass

        # Get art dictionary from info if available
        if isinstance(item_dict.get('info', {}).get('art'), dict):
            art_dict.update(item_dict['info']['art'])

        # Set poster with fallbacks
        if poster_url and str(poster_url) != 'None':
            art_dict['poster'] = poster_url
            art_dict['thumb'] = poster_url
            art_dict['icon'] = poster_url

        # Set fanart
        fanart = item_dict.get('fanart') or item_dict.get('info', {}).get('fanart')
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
            'plot': plot, # Use the potentially enhanced plot
            'tagline': item_dict.get('tagline', ''),
            'country': item_dict.get('country', ''),
            'director': item_dict.get('director', ''),
            'genre': item_dict.get('genre', ''),
            'mpaa': item_dict.get('mpaa', ''),
            'premiered': item_dict.get('premiered', ''),
            'studio': item_dict.get('studio', ''),
            'trailer': item_dict.get('trailer', ''),
            'writer': item_dict.get('writer', ''),
            'mediatype': (item_dict.get('media_type') or item_dict.get('mediatype') or 'movie').lower()
        }

        # Handle numeric fields with proper conversion
        if item_dict.get('year'):
            try:
                year_val = item_dict['year']
                # Handle both integer and string years
                if isinstance(year_val, str) and year_val.isdigit():
                    info_dict['year'] = int(year_val)
                elif isinstance(year_val, (int, float)) and year_val > 0:
                    info_dict['year'] = int(year_val)
            except (ValueError, TypeError):
                pass

        if item_dict.get('rating'):
            try:
                info_dict['rating'] = float(item_dict['rating'])
            except (ValueError, TypeError):
                pass

        if item_dict.get('votes'):
            try:
                info_dict['votes'] = int(item_dict['votes'])
            except (ValueError, TypeError):
                pass

        # Handle runtime/duration
        if item_dict.get('runtime'):
            try:
                info_dict['duration'] = int(item_dict['runtime'])
            except (ValueError, TypeError):
                pass

        # Handle user rating
        if item_dict.get('userrating'):
            try:
                info_dict['userrating'] = float(item_dict['userrating'])
            except (ValueError, TypeError):
                pass

        # Handle top250 ranking
        if item_dict.get('top250'):
            try:
                info_dict['top250'] = int(item_dict['top250'])
            except (ValueError, TypeError):
                pass

        # Handle playcount
        if item_dict.get('playcount'):
            try:
                info_dict['playcount'] = int(item_dict['playcount'])
            except (ValueError, TypeError):
                pass

        # Handle date fields
        for date_field in ['dateadded', 'lastplayed', 'premiered']:
            if item_dict.get(date_field):
                info_dict[date_field] = str(item_dict[date_field])

        # Handle set information
        if item_dict.get('set'):
            info_dict['set'] = str(item_dict['set'])
        if item_dict.get('setid'):
            try:
                info_dict['setid'] = int(item_dict['setid'])
            except (ValueError, TypeError):
                pass

        # Handle multiple ratings (v19+)
        if item_dict.get('ratings') and isinstance(item_dict['ratings'], dict):
            # Use the default rating or first available rating
            for rating_source in ['default', 'imdb', 'themoviedb', 'thetvdb']:
                if rating_source in item_dict['ratings']:
                    rating_data = item_dict['ratings'][rating_source]
                    if isinstance(rating_data, dict) and 'rating' in rating_data:
                        try:
                            info_dict['rating'] = float(rating_data['rating'])
                            if 'votes' in rating_data:
                                info_dict['votes'] = int(rating_data['votes'])
                        except (ValueError, TypeError):
                            pass
                        break

        # Handle cast data
        cast = item_dict.get('cast', [])
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

            except Exception:
                info_dict['cast'] = []

        # Handle other heavy metadata fields for search results
        if source == 'search' or source == 'lib':
            # Process ratings from heavy metadata
            ratings = item_dict.get('ratings', {})
            if isinstance(ratings, str):
                try:
                    ratings = json.loads(ratings)
                except json.JSONDecodeError:
                    ratings = {}
            if isinstance(ratings, dict) and ratings:
                info_dict['ratings'] = ratings

            # Process streamdetails from heavy metadata
            streamdetails = item_dict.get('streamdetails', {})
            if isinstance(streamdetails, str):
                try:
                    streamdetails = json.loads(streamdetails)
                except json.JSONDecodeError:
                    streamdetails = {}
            if isinstance(streamdetails, dict) and streamdetails:
                info_dict['streamdetails'] = streamdetails

            # Process uniqueid from heavy metadata
            uniqueid = item_dict.get('uniqueid', {})
            if isinstance(uniqueid, str):
                try:
                    uniqueid = json.loads(uniqueid)
                except json.JSONDecodeError:
                    uniqueid = {}
            if isinstance(uniqueid, dict) and uniqueid:
                info_dict['uniqueid'] = uniqueid

        # Process plot information
        if item_dict.get('plot'):
            pass

        # Add IMDb ID to info_dict if available - version-aware handling
        source1 = item_dict.get('imdbnumber', '')
        source2 = item_dict.get('uniqueid', {}).get('imdb', '') if isinstance(item_dict.get('uniqueid'), dict) else ''
        source3 = item_dict.get('info', {}).get('imdbnumber', '') if item_dict.get('info') else ''
        source4 = item_dict.get('imdb_id', '')

        # For search results, prioritize the stored imdbnumber field
        if source == 'search' and source1:
            source4 = source1  # Use imdbnumber as primary for search results

        # Prioritize uniqueid.imdb over other sources for v19 compatibility
        final_imdb_id = ''
        if source2 and str(source2).startswith('tt'):  # uniqueid.imdb
            final_imdb_id = source2
        else:
            # Fallback to other sources, but only if they start with 'tt'
            for source_name, source_value in [('imdbnumber', source1), ('info.imdbnumber', source3), ('imdb_id', source4)]:
                if source_value and str(source_value).startswith('tt'):
                    final_imdb_id = source_value
                    break

        if final_imdb_id and str(final_imdb_id).startswith('tt'):
            info_dict['imdbnumber'] = final_imdb_id

            # For Kodi v19+, also set uniqueid properly
            if not info_dict.get('uniqueid'):
                info_dict['uniqueid'] = {'imdb': final_imdb_id}
            elif isinstance(info_dict.get('uniqueid'), dict):
                info_dict['uniqueid']['imdb'] = final_imdb_id

        # Use the specialized set_info_tag function that handles Kodi version compatibility
        set_info_tag(li, info_dict, 'video')

        # Handle resume data with v20+ compatibility
        resume_data = item_dict.get('resume', {})
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


        # Handle stream details with v20+ compatibility - completely skip for favorites_import to avoid any deprecated calls
        if source == 'favorites_import':
            # Skip all stream processing for favorites imports to avoid deprecation warnings
            utils.log(f"Skipping stream details processing for favorites_import item: {item_dict.get('title', 'Unknown')}", "DEBUG")
        else:
            stream_details = item_dict.get('streamdetails', {})
            if isinstance(stream_details, dict) and stream_details:
                try:
                    if utils.is_kodi_v19():
                        # v19 - use deprecated methods since InfoTag is unreliable
                        utils.log(f"LISTITEM_BUILD_VIDEO: About to call deprecated stream methods for '{title}' on thread {current_thread.name}", "INFO")
                        ListItemBuilder._add_stream_info_deprecated(li, stream_details)
                    else:
                        # v20+ - skip deprecated stream methods to avoid warnings
                        # Stream details are handled by InfoTag internally when possible
                        # Only set essential stream properties if needed
                        video_streams = stream_details.get('video', [])
                        if video_streams and isinstance(video_streams[0], dict):
                            codec = video_streams[0].get('codec', '')
                            if codec:
                                li.setProperty('VideoCodec', codec)

                        audio_streams = stream_details.get('audio', [])
                        if audio_streams and isinstance(audio_streams[0], dict):
                            codec = audio_streams[0].get('codec', '')
                            if codec:
                                li.setProperty('AudioCodec', codec)
                except Exception:
                    pass

        # Set content properties - handle non-playable items  
        is_playable = True  # Default to playable

        # For favorites imports without valid file paths, mark as non-playable
        if source == 'favorites_import':
            file_path = item_dict.get('file') or item_dict.get('path') or item_dict.get('play')
            if not file_path or not str(file_path).strip():
                is_playable = False

        li.setProperty('IsPlayable', 'true' if is_playable else 'false')

        # Set LibraryGenie marker to exclude from native context menu
        li.setProperty('LibraryGenie.Item', 'true')

        # Set media_id for context menu access (used for removing from lists)
        media_id = item_dict.get('media_id') or item_dict.get('id')
        if media_id:
            li.setProperty('media_id', str(media_id))

        # Set DBID for Kodi Information dialog support
        kodi_id = item_dict.get('kodi_id') or item_dict.get('movieid') or item_dict.get('id')
        if kodi_id:
            li.setProperty('DBID', str(kodi_id))

        # Set MediaType property for Kodi recognition
        media_type = info_dict.get('mediatype', 'movie')
        li.setProperty('MediaType', media_type)

        # Use centralized context menu builder
        from resources.lib.kodi.context_menu_builder import get_context_menu_builder
        context_builder = get_context_menu_builder()

        # Build context based on available information
        context = {}
        if isinstance(item_dict, dict) and '_context_info' in item_dict:
            context = item_dict['_context_info']

        # If this item is from a list view, ensure we have the list context
        if item_dict.get('_viewing_list_id'):
            context['current_list_id'] = item_dict['_viewing_list_id']
            utils.log(f"Setting context for list viewing: list_id={item_dict['_viewing_list_id']}, media_id={item_dict.get('media_id')}", "DEBUG")

        # Get context menu items from centralized builder
        context_menu_items = context_builder.build_video_context_menu(item_dict, context)

        # Add context menu to ListItem with v19 compatibility fix
        if utils.is_kodi_v19():
            # v19 requires replaceItems=True for reliable context menu display
            li.addContextMenuItems(context_menu_items, replaceItems=True)
        else:
            # v20+ can use replaceItems=False to preserve existing items
            li.addContextMenuItems(context_menu_items, replaceItems=False)

        # Try to get play URL from different possible locations
        play_url = None

        # For search results, don't set invalid info:// URLs
        if source == 'search':
            # Search results are non-playable by design - they're for discovery
            play_url = item_dict.get('play')
            if play_url and not str(play_url).startswith('info://'):
                li.setPath(play_url)
                utils.log(f"Set valid ListItem path for search result '{title}': {play_url}", "DEBUG")
            else:
                # Don't set invalid URLs that Kodi can't handle
                utils.log(f"Search result '{title}' - skipping invalid play URL: {play_url}", "DEBUG")
        # For favorites imports, only set path if it's playable and has valid URL
        elif source == 'favorites_import':
            if is_playable:
                play_url = item_dict.get('file') or item_dict.get('path') or item_dict.get('play')
                if play_url and str(play_url).strip():
                    # Don't set path here - it's already set in the URL by ResultsManager
                    utils.log(f"Favorites import '{title}' has playable path: {play_url}", "DEBUG")
                else:
                    utils.log(f"Favorites import '{title}' marked non-playable - no path available", "DEBUG")
            else:
                utils.log(f"Favorites import '{title}' is non-playable - no path set", "DEBUG")
        elif source == 'plugin_addon' and item_dict.get('file'):
            play_url = item_dict.get('file')
            if play_url and isinstance(play_url, str):
                li.setPath(play_url)
                utils.log(f"Set ListItem path for plugin addon '{title}': {play_url}", "DEBUG")
            else:
                utils.log(f"No valid play URL string found for plugin addon '{title}'", "DEBUG")
        else:
            # For other items, use the standard priority order
            play_url = item_dict.get('info', {}).get('play') or item_dict.get('play') or item_dict.get('file')
            if play_url:
                li.setPath(play_url)
                utils.log(f"Set ListItem path for '{title}': {play_url}", "DEBUG")
            else:
                utils.log(f"No play URL found for '{title}'", "DEBUG")


        # Store IMDb ID as a property on the ListItem itself for context menu access
        # Use the same IMDb ID we processed above for consistency
        final_imdb_id = info_dict.get('imdbnumber', '')
        if not ListItemBuilder._imdb_trace_logged:
            utils.log(f"=== IMDB_TRACE: Setting ListItem properties for '{title}' (first movie only) ===", "INFO")
            utils.log(f"IMDB_TRACE: final_imdb_id from info_dict = '{final_imdb_id}'", "INFO")
            ListItemBuilder._imdb_trace_logged = True

        if final_imdb_id and str(final_imdb_id).startswith('tt'):
            # Set multiple properties for maximum compatibility
            li.setProperty('LibraryGenie.IMDbID', str(final_imdb_id))
            li.setProperty('imdb_id', str(final_imdb_id))  # Additional fallback property
            li.setProperty('imdbnumber', str(final_imdb_id))  # Additional fallback property
            if not ListItemBuilder._imdb_trace_logged or ListItemBuilder._imdb_trace_logged:
                # Log only for first movie
                pass
        else:
            if not hasattr(ListItemBuilder, '_imdb_trace_logged') or not ListItemBuilder._imdb_trace_logged:
                utils.log(f"IMDB_TRACE: No valid IMDb ID found for '{title}' - cannot set properties", "INFO")

        if not hasattr(ListItemBuilder, '_trace_end_logged'):
            utils.log(f"=== END IMDB_TRACE: ListItem properties for '{title}' (first movie only) ===", "INFO")
            ListItemBuilder._trace_end_logged = True

        utils.log(f"=== LISTITEM_BUILD_VIDEO: Successfully created ListItem for '{title}' ===", "INFO")
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
        # Get call stack information for debugging
        import inspect
        import threading
        
        current_thread = threading.current_thread()
        stack_frames = inspect.stack()
        caller_info = []
        
        # Collect meaningful caller information (skip current frame)
        for i, frame in enumerate(stack_frames[1:6], 1):  # Check up to 5 levels up
            func_name = frame.function
            file_name = frame.filename.split('/')[-1]  # Just the filename
            line_no = frame.lineno
            caller_info.append(f"{file_name}:{func_name}():{line_no}")
        
        caller_chain = " -> ".join(caller_info)
        
        utils.log(f"=== LISTITEM_BUILD_FOLDER: Starting for '{name}' (type: {item_type}) ===", "INFO")
        utils.log(f"LISTITEM_BUILD_FOLDER: Thread: {current_thread.name}", "INFO")
        utils.log(f"LISTITEM_BUILD_FOLDER: Call chain: {caller_chain}", "INFO")
        utils.log(f"LISTITEM_BUILD_FOLDER: is_folder: {is_folder}, plot: {bool(plot)}", "INFO")
        
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

        utils.log(f"=== LISTITEM_BUILD_FOLDER: Successfully created folder ListItem for '{clean_name}' ===", "INFO")
        return list_item

    @staticmethod
    def add_context_menu(list_item, menu_items):
        """Add context menu items to ListItem"""
        list_item.addContextMenuItems(menu_items, replaceItems=True)

    @staticmethod
    def _add_stream_info_deprecated(list_item, stream_details):
        """Adds stream details using deprecated methods for compatibility with older Kodi versions."""
        import threading
        current_thread = threading.current_thread()
        utils.log(f"=== DEPRECATED_STREAM_INFO: Called on thread {current_thread.name} (ID: {current_thread.ident}) ===", "INFO")
        
        # Get call stack to see what led to this deprecated call
        import inspect
        stack_frames = inspect.stack()
        caller_info = []
        for i, frame in enumerate(stack_frames[1:8], 1):
            func_name = frame.function
            file_name = frame.filename.split('/')[-1]
            line_no = frame.lineno
            caller_info.append(f"{file_name}:{func_name}():{line_no}")
        
        caller_chain = " -> ".join(caller_info)
        utils.log(f"DEPRECATED_STREAM_INFO: Call chain: {caller_chain}", "INFO")
        
        # This method is a fallback for versions where setVideoStream, setAudioStream, setSubtitleStream are deprecated
        # or not available. It aims to set properties that might be recognized by older Kodi clients or skins.
        video_streams = stream_details.get('video', [])
        audio_streams = stream_details.get('audio', [])
        subtitle_streams = stream_details.get('subtitle', [])

        if video_streams:
            utils.log(f"DEPRECATED_STREAM_INFO: Processing {len(video_streams)} video streams", "INFO")
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
            utils.log(f"DEPRECATED_STREAM_INFO: Processing {len(audio_streams)} audio streams", "INFO")
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