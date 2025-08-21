
import xbmcgui
from resources.lib.utils import utils
from resources.lib.config.config_manager import Config
from resources.lib.data.query_manager import QueryManager
from resources.lib.integrations.remote_api.remote_api_client import RemoteAPIClient
import time
import datetime

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
        
        # Calculate percentage
        imdb_percentage = (items_with_imdb / total_library_items * 100) if total_library_items > 0 else 0
        
        # Get server upload status
        server_status = "Not configured"
        server_count = 0
        last_upload_info = "Never"
        
        try:
            if remote_client.test_connection():
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
            else:
                server_status = "Not configured or unreachable"
                
        except Exception as e:
            utils.log(f"Error checking server status: {str(e)}", "WARNING")
            server_status = "Error checking server status"
        
        # Build status message
        status_lines = [
            "=== ADDON LIBRARY STATUS ===",
            "",
            f"📚 LOCAL LIBRARY:",
            f"  • Total library items: {total_library_items:,}",
            f"  • Items with IMDb ID: {items_with_imdb:,} ({imdb_percentage:.1f}%)",
            f"  • Items without IMDb: {total_library_items - items_with_imdb:,}",
            "",
            f"🌐 SERVER STATUS:",
            f"  • Status: {server_status}",
            f"  • Last upload: {last_upload_info}",
            "",
        ]
        
        # Add sync status comparison if we have both local and server data
        if server_count > 0 and items_with_imdb > 0:
            sync_percentage = (server_count / items_with_imdb * 100) if items_with_imdb > 0 else 0
            status_lines.extend([
                f"🔄 SYNC STATUS:",
                f"  • Server has {server_count:,} of {items_with_imdb:,} local movies ({sync_percentage:.1f}%)",
                f"  • Difference: {abs(items_with_imdb - server_count):,} movies",
            ])
            
            if server_count < items_with_imdb:
                status_lines.append(f"  • ⚠️  Server is missing {items_with_imdb - server_count:,} movies")
            elif server_count > items_with_imdb:
                status_lines.append(f"  • ℹ️  Server has {server_count - items_with_imdb:,} more movies than local")
            else:
                status_lines.append(f"  • ✅ Server and local library are in sync")
        
        status_text = "\n".join(status_lines)
        
        utils.log("LIBRARY_STATUS: Status summary generated successfully", "INFO")
        utils.log(f"LIBRARY_STATUS: Total: {total_library_items}, IMDb: {items_with_imdb}, Server: {server_count}", "INFO")
        
        # Show the dialog
        xbmcgui.Dialog().textviewer('Addon Library Status', status_text)
        
    except Exception as e:
        utils.log(f"Error showing library status: {str(e)}", "ERROR")
        import traceback
        utils.log(f"Library status traceback: {traceback.format_exc()}", "ERROR")
        
        # Show error dialog
        xbmcgui.Dialog().ok(
            'Library Status Error', 
            f'Error gathering library status:\n{str(e)}'
        )
