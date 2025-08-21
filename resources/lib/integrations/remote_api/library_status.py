
import xbmcgui
from resources.lib.utils import utils
from resources.lib.config.config_manager import Config
from resources.lib.data.query_manager import QueryManager
from resources.lib.integrations.remote_api.remote_api_client import RemoteAPIClient
import time
import datetime

def show_scrollable_status_dialog(title, status_lines):
    """Show status information in a scrollable dialog with keyboard navigation support"""
    try:
        # Convert status lines to display format for select dialog
        display_lines = []
        for line in status_lines:
            if line.strip():  # Skip empty lines for cleaner display
                display_lines.append(line)
            else:
                display_lines.append("─" * 20)  # Visual separator for empty lines
        
        # Show as select dialog which supports better keyboard navigation
        selected = xbmcgui.Dialog().select(
            title, 
            display_lines
        )
        
        # Dialog returns -1 when cancelled, which is expected behavior
        utils.log(f"LIBRARY_STATUS: Status dialog closed (selection: {selected})", "DEBUG")
        
    except Exception as e:
        utils.log(f"Error showing scrollable status dialog: {str(e)}", "ERROR")
        # Fallback to simple OK dialog with summary
        summary = f"Library: {len([l for l in status_lines if 'Total library items:' in l])}"
        xbmcgui.Dialog().ok('Library Status', f'Status generated successfully.\n{summary}\nCheck log for details.')

def show_library_status():
    """Show comprehensive library status dialog"""
    try:
        utils.log("=== LIBRARY_STATUS: Starting library status check ===", "INFO")
        
        # Initialize components
        config = Config()
        query_manager = QueryManager(config.db_path)
        remote_client = RemoteAPIClient()
        
        # Get total library items count from media_items (now contains all library items)
        total_result = query_manager.execute_query(
            "SELECT COUNT(*) as count FROM media_items WHERE source = 'lib'",
            fetch_one=True
        )
        total_library_items = total_result['count'] if total_result else 0
        
        # Get items with valid IMDb IDs (starting with 'tt') from media_items
        imdb_result = query_manager.execute_query(
            "SELECT COUNT(*) as count FROM media_items WHERE source = 'lib' AND imdbnumber IS NOT NULL AND imdbnumber != '' AND imdbnumber LIKE 'tt%'",
            fetch_one=True
        )
        items_with_imdb = imdb_result['count'] if imdb_result else 0
        
        # Get unique IMDb IDs count from media_items
        unique_imdb_result = query_manager.execute_query(
            "SELECT COUNT(DISTINCT imdbnumber) as count FROM media_items WHERE source = 'lib' AND imdbnumber IS NOT NULL AND imdbnumber != '' AND imdbnumber LIKE 'tt%'",
            fetch_one=True
        )
        unique_imdb_count = unique_imdb_result['count'] if unique_imdb_result else 0
        
        # Calculate duplicates
        duplicate_imdb_count = items_with_imdb - unique_imdb_count
        
        # Get imdb_exports table stats
        exports_result = query_manager.execute_query(
            "SELECT COUNT(*) as total, COUNT(DISTINCT imdb_id) as unique_exports FROM imdb_exports WHERE imdb_id IS NOT NULL AND imdb_id != '' AND imdb_id LIKE 'tt%'",
            fetch_one=True
        )
        exports_total = exports_result['total'] if exports_result else 0
        exports_unique = exports_result['unique_exports'] if exports_result else 0
        exports_duplicates = exports_total - exports_unique
        
        # Calculate percentage
        imdb_percentage = (items_with_imdb / total_library_items * 100) if total_library_items > 0 else 0
        
        # Check if user is authenticated for server features
        is_authenticated = False
        server_status = "Not configured"
        server_count = 0
        last_upload_info = "Never"
        
        try:
            # Check if remote API is configured and accessible
            if remote_client.test_connection():
                is_authenticated = True
                # Get current movie count on server
                movie_list = remote_client.get_movie_list(per_page=1)
                if movie_list and movie_list.get('success'):
                    server_count = movie_list.get('user_movie_count', 0)
                    
                    # Get last upload info from batch history
                    batches = remote_client.get_batch_history()
                    if batches and len(batches) > 0:
                        last_batch = batches[0]  # Most recent batch
                        upload_count = last_batch.get('successful_imports', 0)
                        upload_date = last_batch.get('started_at', 'Unknown')
                        batch_type = last_batch.get('batch_type', 'unknown')
                        
                        # Parse and format the date
                        try:
                            if upload_date and upload_date != 'Unknown':
                                # Assuming ISO format date string
                                parsed_date = datetime.datetime.fromisoformat(upload_date.replace('Z', '+00:00'))
                                formatted_date = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
                                last_upload_info = f"{upload_count} movies ({batch_type})\nDate: {formatted_date}"
                            else:
                                last_upload_info = f"{upload_count} movies ({batch_type})"
                        except:
                            last_upload_info = f"{upload_count} movies ({batch_type})\nDate: {upload_date}"
                    
                    server_status = f"Connected - {server_count} movies on server"
                else:
                    server_status = "Connected but unable to get movie count"
                    
        except Exception as e:
            utils.log(f"Error checking server status: {str(e)}", "WARNING")
            is_authenticated = False
        
        # Build status message
        status_lines = [
            "=== ADDON LIBRARY STATUS ===",
            "",
            f"📚 LOCAL LIBRARY (media_items):",
            f"  • Total library items: {total_library_items:,}",
            f"  • Items with IMDb ID: {items_with_imdb:,} ({imdb_percentage:.1f}%)",
            f"  • Unique IMDb IDs: {unique_imdb_count:,}",
            f"  • Duplicate IMDb entries: {duplicate_imdb_count:,}",
            f"  • Items without IMDb: {total_library_items - items_with_imdb:,}",
            "",
            f"📊 EXPORT TABLE (imdb_exports):",
            f"  • Total export records: {exports_total:,}",
            f"  • Unique IMDb IDs: {exports_unique:,}",
            f"  • Duplicate export records: {exports_duplicates:,}",
            "",
        ]
        
        # Add server status only if authenticated
        if is_authenticated:
            status_lines.extend([
                f"🌐 SERVER STATUS:",
                f"  • Status: {server_status}",
                f"  • Last upload: {last_upload_info}",
                "",
            ])
        else:
            status_lines.extend([
                f"🤖 AI FEATURES:",
                f"  • Status: Not available (authentication required)",
                f"  • Configure remote API in addon settings for AI search",
                "",
            ])
        
        # Add sync status comparison only if authenticated and we have server data
        if is_authenticated and server_count > 0 and unique_imdb_count > 0:
            sync_percentage = (server_count / unique_imdb_count * 100) if unique_imdb_count > 0 else 0
            status_lines.extend([
                f"🔄 SYNC STATUS (using unique IMDb counts):",
                f"  • Server has {server_count:,} of {unique_imdb_count:,} unique local movies ({sync_percentage:.1f}%)",
                f"  • Difference: {abs(unique_imdb_count - server_count):,} movies",
                f"  • Export table has {exports_unique:,} unique IMDb IDs for upload",
            ])
            
            if server_count < unique_imdb_count:
                status_lines.append(f"  • ⚠️  Server is missing {unique_imdb_count - server_count:,} unique movies")
            elif server_count > unique_imdb_count:
                status_lines.append(f"  • ℹ️  Server has {server_count - unique_imdb_count:,} more movies than local unique")
            else:
                status_lines.append(f"  • ✅ Server and local unique library are in sync")
        
        
        
        utils.log("LIBRARY_STATUS: Status summary generated successfully", "INFO")
        utils.log(f"LIBRARY_STATUS: Total: {total_library_items}, IMDb: {items_with_imdb}, Unique IMDb: {unique_imdb_count}, Duplicates: {duplicate_imdb_count}, Authenticated: {is_authenticated}, Server: {server_count if is_authenticated else 'N/A'}", "INFO")
        
        # Show scrollable dialog using select method for better keyboard navigation
        show_scrollable_status_dialog('Addon Library Status', status_lines)
        
    except Exception as e:
        utils.log(f"Error showing library status: {str(e)}", "ERROR")
        import traceback
        utils.log(f"Library status traceback: {traceback.format_exc()}", "ERROR")
        
        # Show error dialog
        xbmcgui.Dialog().ok(
            'Library Status Error', 
            f'Error gathering library status:\n{str(e)}'
        )
