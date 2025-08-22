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
        total_library_items = total_result.get('count', 0) if total_result and isinstance(total_result, dict) else 0

        # Get items with valid IMDb IDs (starting with 'tt') from media_items
        imdb_result = query_manager.execute_query(
            "SELECT COUNT(*) as count FROM media_items WHERE source = 'lib' AND imdbnumber IS NOT NULL AND imdbnumber != '' AND imdbnumber LIKE 'tt%'",
            fetch_one=True
        )
        items_with_imdb = imdb_result.get('count', 0) if imdb_result and isinstance(imdb_result, dict) else 0

        # Get unique IMDb IDs count from media_items
        unique_imdb_result = query_manager.execute_query(
            "SELECT COUNT(DISTINCT imdbnumber) as count FROM media_items WHERE source = 'lib' AND imdbnumber IS NOT NULL AND imdbnumber != '' AND imdbnumber LIKE 'tt%'",
            fetch_one=True
        )
        unique_imdb_count = unique_imdb_result.get('count', 0) if unique_imdb_result and isinstance(unique_imdb_result, dict) else 0

        # Calculate duplicates
        # duplicate_imdb_count = items_with_imdb - unique_imdb_count # Removed as per instruction

        # Get imdb_exports table stats
        exports_result = query_manager.execute_query(
            "SELECT COUNT(*) as total, COUNT(DISTINCT imdb_id) as unique_exports FROM imdb_exports WHERE imdb_id IS NOT NULL AND imdb_id != '' AND imdb_id LIKE 'tt%'",
            fetch_one=True
        )
        exports_total = exports_result.get('total', 0) if exports_result and isinstance(exports_result, dict) else 0
        exports_unique = exports_result.get('unique_exports', 0) if exports_result and isinstance(exports_result, dict) else 0
        # exports_duplicates = exports_total - exports_unique # Removed as per instruction

        # Calculate percentage
        imdb_percentage = (items_with_imdb / total_library_items * 100) if total_library_items > 0 else 0

        # Check if user is authenticated for server features
        is_authenticated = False
        server_status = "Not configured"
        server_count = 0
        last_upload_info = "Never"
        library_stats = None

        try:
            # Check if remote API is configured and accessible
            if remote_client.test_connection():
                is_authenticated = True
                
                # Get comprehensive library statistics
                stats_response = remote_client.get_library_statistics()
                if stats_response and stats_response.get('success'):
                    library_stats = stats_response.get('stats', {})
                    
                    # Extract basic info from stats
                    library_overview = library_stats.get('library_overview', {})
                    server_count = library_overview.get('total_uploaded', 0)
                    
                    # Get last upload info from batch history in stats
                    batch_history = library_stats.get('batch_history', {})
                    recent_batches = batch_history.get('recent_batches', [])
                    
                    if recent_batches:
                        last_batch = recent_batches[0]  # Most recent batch
                        upload_count = last_batch.get('successful_imports', 0)
                        upload_date = last_batch.get('completed_at', 'Unknown')
                        batch_type = last_batch.get('status', 'unknown')

                        # Parse and format the date
                        try:
                            if upload_date and upload_date != 'Unknown':
                                # Assuming ISO format date string
                                parsed_date = datetime.datetime.fromisoformat(upload_date.replace('Z', '+00:00'))
                                formatted_date = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
                                last_upload_info = f"{upload_count} movies ({batch_type}) on {formatted_date}"
                            else:
                                last_upload_info = f"{upload_count} movies ({batch_type})"
                        except:
                            last_upload_info = f"{upload_count} movies ({batch_type}) on {upload_date}"

                    server_status = f"Connected - {server_count} movies on server"
                else:
                    # Fallback to old method if stats endpoint fails
                    movie_list = remote_client.get_movie_list(per_page=1)
                    if movie_list and movie_list.get('success'):
                        server_count = movie_list.get('user_movie_count', 0)
                        server_status = f"Connected - {server_count} movies on server"
                    else:
                        server_status = "Connected but unable to get movie count"

        except Exception as e:
            utils.log(f"Error checking server status: {str(e)}", "WARNING")
            is_authenticated = False

        # Determine color coding based on IMDb coverage
        def get_coverage_color(percentage):
            if percentage >= 95:
                return "green"
            elif percentage >= 85:
                return "yellow"
            else:
                return "red"

        def get_coverage_assessment(percentage):
            if percentage >= 98:
                return "Perfect"
            elif percentage >= 95:
                return "Great"
            elif percentage >= 90:
                return "OK"
            else:
                return "Weak"

        

        # Calculate IMDb coverage as percentage of unique IMDb IDs vs total library items
        unique_imdb_coverage = (unique_imdb_count / total_library_items * 100) if total_library_items > 0 else 0
        
        # Use unique IMDb coverage for color coding and assessment
        coverage_color = get_coverage_color(unique_imdb_coverage)
        coverage_assessment = get_coverage_assessment(unique_imdb_coverage)

        # Build comprehensive status message
        status_lines = [
            "=== ADDON LIBRARY STATUS ===",
            f"[COLOR {coverage_color}]LOCAL LIBRARY[/COLOR] {total_library_items:,}",
            f"  • Unique IMDb: {unique_imdb_count:,} ({unique_imdb_coverage:.0f}% coverage)",
            f"  • Items without IMDb: {total_library_items - items_with_imdb:,} (not covered)",
        ]

        # Add AI search assessment for non-authenticated users
        if not is_authenticated:
            status_lines.extend([
                f"[COLOR {coverage_color}]AI SEARCH[/COLOR] {coverage_assessment} ({unique_imdb_coverage:.0f}% IMDb coverage)",
            ])
        else:
            # Add server status for authenticated users
            server_color = "green" if "Connected" in server_status else "red"
            status_lines.extend([
                f"[COLOR {server_color}]SERVER STATUS[/COLOR] {server_status.replace('Status: ', '')}",
                f"  • Last upload: {last_upload_info}",
            ])

            # Add comprehensive server statistics if available
            if library_stats:
                setup_status = library_stats.get('setup_status', {})
                data_quality = library_stats.get('data_quality', {})
                system_context = library_stats.get('system_context', {})
                
                # Setup completeness
                completely_setup = setup_status.get('completely_setup', {})
                setup_count = completely_setup.get('count', 0)
                setup_percentage = completely_setup.get('percentage', 0)
                
                if setup_count > 0:
                    setup_color = "green" if setup_percentage >= 95 else "yellow" if setup_percentage >= 85 else "red"
                    status_lines.extend([
                        f"[COLOR {setup_color}]SEARCH READY[/COLOR] {setup_count:,} movies ({setup_percentage:.1f}%)",
                    ])
                
                # Data quality metrics
                tmdb_available = data_quality.get('tmdb_data_available', {})
                opensearch_indexed = data_quality.get('opensearch_indexed', {})
                
                if tmdb_available.get('count', 0) > 0:
                    tmdb_percentage = tmdb_available.get('percentage', 0)
                    tmdb_color = "green" if tmdb_percentage >= 98 else "yellow" if tmdb_percentage >= 90 else "red"
                    status_lines.append(f"  • TMDB metadata: {tmdb_percentage:.1f}%")
                
                if opensearch_indexed.get('count', 0) > 0:
                    search_percentage = opensearch_indexed.get('percentage', 0)
                    search_color = "green" if search_percentage >= 95 else "yellow" if search_percentage >= 85 else "red"
                    status_lines.append(f"  • Search indexed: {search_percentage:.1f}%")
                
                # System context information
                if system_context:
                    total_system_movies = system_context.get('total_movies_in_system', 0)
                    user_lists_stats = system_context.get('user_lists_stats', {})
                    avg_per_user = user_lists_stats.get('average_movies_per_user', 0)
                    
                    status_lines.extend([
                        "",
                        "[COLOR white]SYSTEM OVERVIEW[/COLOR]",
                        f"  • Total movies in system: {total_system_movies:,}",
                        f"  • Average collection size: {avg_per_user:.0f} movies",
                    ])

            # Add sync status comparison only if authenticated and we have server data
            if server_count > 0 and unique_imdb_count > 0:
                sync_difference = abs(unique_imdb_count - server_count)
                sync_color = "green" if sync_difference == 0 else "yellow" if sync_difference <= 50 else "red"
                
                if sync_difference == 0:
                    sync_status_text = "Perfect sync"
                elif unique_imdb_count > server_count:
                    sync_status_text = f"Local has {sync_difference} more movies"
                else:
                    sync_status_text = f"Server has {sync_difference} more movies"
                
                status_lines.extend([
                    "",
                    f"[COLOR {sync_color}]SYNC STATUS[/COLOR] {sync_status_text}",
                    f"  • Server: {server_count:,} | Local unique: {unique_imdb_count:,} | Export ready: {exports_unique:,}",
                ])

        utils.log("LIBRARY_STATUS: Status summary generated successfully", "INFO")
        # utils.log(f"LIBRARY_STATUS: Total: {total_library_items}, IMDb: {items_with_imdb}, Unique IMDb: {unique_imdb_count}, Duplicates: {duplicate_imdb_count}, Authenticated: {is_authenticated}, Server: {server_count if is_authenticated else 'N/A'}", "INFO") # Updated log to remove duplicate count
        utils.log(f"LIBRARY_STATUS: Total: {total_library_items}, IMDb: {items_with_imdb}, Unique IMDb: {unique_imdb_count}, Authenticated: {is_authenticated}, Server: {server_count if is_authenticated else 'N/A'}", "INFO")


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