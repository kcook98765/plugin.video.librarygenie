
```python
import xbmc
import xbmcgui
import xbmcplugin
import re
from resources.lib.config.config_manager import Config
from resources.lib.data.database_manager import DatabaseManager
from resources.lib.utils import utils

def display_imdb_data_as_directory(params, handle):
    """Display all database data for an IMDb ID as directory items"""
    try:
        imdb_id = params.get('imdb_id', [None])[0] if params.get('imdb_id') else None
        title = params.get('title', ['Unknown'])[0] if params.get('title') else 'Unknown'

        # URL decode the title
        import urllib.parse
        if title:
            title = urllib.parse.unquote_plus(title)

        if not imdb_id or not str(imdb_id).startswith('tt'):
            # Add error item
            li = xbmcgui.ListItem(label="ERROR: No valid IMDb ID found")
            li.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", li, False)
            xbmcplugin.endOfDirectory(handle)
            return

        utils.log(f"LibraryGenie: Dev Display for {title} (IMDb: {imdb_id})", "INFO")

        # Get database manager
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Set directory properties
        xbmcplugin.setContent(handle, "files")
        xbmcplugin.setPluginCategory(handle, f"Dev Display - {imdb_id}")

        # Add header item
        header_li = xbmcgui.ListItem(label=f"=== DEV DISPLAY FOR {title} ===")
        header_li.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle, "", header_li, False)

        # Add IMDb ID info
        imdb_li = xbmcgui.ListItem(label=f"IMDb ID: {imdb_id}")
        imdb_li.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle, "", imdb_li, False)

        # Spacer
        spacer_li = xbmcgui.ListItem(label="")
        spacer_li.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle, "", spacer_li, False)

        # Table 1: media_items table analysis
        try:
            section_li1 = xbmcgui.ListItem(label="=== MEDIA_ITEMS TABLE ===")
            section_li1.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", section_li1, False)

            # Get total count
            total_result = db_manager.query_manager.execute_query("SELECT COUNT(*) as count FROM media_items", fetch_one=True)
            total_media = total_result['count'] if total_result else 0

            # Get count with IMDb numbers
            imdb_result = db_manager.query_manager.execute_query(
                "SELECT COUNT(*) as count FROM media_items WHERE imdbnumber IS NOT NULL AND imdbnumber != '' AND imdbnumber LIKE 'tt%'",
                fetch_one=True
            )
            with_imdb = imdb_result['count'] if imdb_result else 0

            # Display counts
            count_li = xbmcgui.ListItem(label=f"Total media_items: {total_media}")
            count_li.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", count_li, False)

            imdb_count_li = xbmcgui.ListItem(label=f"media_items with IMDb ID: {with_imdb}")
            imdb_count_li.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", imdb_count_li, False)

            # Get breakdown by source
            source_breakdown = db_manager.query_manager.execute_query(
                "SELECT source, COUNT(*) as count FROM media_items GROUP BY source ORDER BY COUNT(*) DESC",
                fetch_all=True
            )

            # Display source breakdown
            if source_breakdown:
                source_header_li = xbmcgui.ListItem(label="Source Breakdown:")
                source_header_li.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, "", source_header_li, False)
                for row in source_breakdown:
                    source = row['source']
                    count = row['count']
                    source_li = xbmcgui.ListItem(label=f"  - {source}: {count}")
                    source_li.setProperty('IsPlayable', 'false')
                    xbmcplugin.addDirectoryItem(handle, "", source_li, False)
            else:
                no_source_data_li = xbmcgui.ListItem(label="No source data found.")
                no_source_data_li.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, "", no_source_data_li, False)


            # Fetch and display specific media items
            media_items_query = "SELECT * FROM media_items WHERE imdbnumber = ?"
            media_items_rows = db_manager.query_manager.execute_query(media_items_query, (imdb_id,), fetch_all=True)

            if media_items_rows:
                for i, row in enumerate(media_items_rows):
                    # Convert row to dict
                    row_dict = dict(row)

                    # Create summary line
                    row_title = row_dict.get('title', 'Unknown')
                    row_year = row_dict.get('year', 'N/A')
                    row_source = row_dict.get('source', 'N/A')

                    item_li = xbmcgui.ListItem(label=f"Row {i+1}: {row_title} ({row_year}) - Source: {row_source}")
                    item_li.setProperty('IsPlayable', 'false')

                    # Add details as plot
                    details = []
                    for key, value in row_dict.items():
                        if value is not None and str(value).strip():
                            if key in ['plot', 'cast', 'art'] and len(str(value)) > 100:
                                details.append(f"{key}: {str(value)[:100]}...")
                            else:
                                details.append(f"{key}: {value}")

                    item_li.setInfo('video', {'plot': '\n'.join(details)})
                    xbmcplugin.addDirectoryItem(handle, "", item_li, False)
            else:
                no_data_li = xbmcgui.ListItem(label="No entries found in media_items table for this IMDb ID")
                no_data_li.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, "", no_data_li, False)

        except Exception as e:
            error_li = xbmcgui.ListItem(label=f"Error querying media_items: {str(e)}")
            error_li.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", error_li, False)

        # Spacer
        spacer_li2 = xbmcgui.ListItem(label="")
        spacer_li2.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle, "", spacer_li2, False)

        # Table 2: list_items (where this IMDb ID appears)
        try:
            list_items_query = """
                SELECT li.*, l.name as list_name, mi.title as media_title
                FROM list_items li
                JOIN media_items mi ON li.media_item_id = mi.id
                JOIN lists l ON li.list_id = l.id
                WHERE mi.imdbnumber = ?
            """
            list_items_rows = db_manager.query_manager.execute_query(list_items_query, (imdb_id,), fetch_all=True)

            # Get total list items
            list_items_result = db_manager.query_manager.execute_query("SELECT COUNT(*) as count FROM list_items", fetch_one=True)
            total_list_items = list_items_result['count'] if list_items_result else 0

            # Get unique lists with items
            unique_lists_result = db_manager.query_manager.execute_query("SELECT COUNT(DISTINCT list_id) as count FROM list_items", fetch_one=True)
            lists_with_items = unique_lists_result['count'] if unique_lists_result else 0

            section_li2 = xbmcgui.ListItem(label=f"=== LIST_ITEMS TABLE (Total: {total_list_items}, Lists: {lists_with_items}) ===")
            section_li2.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", section_li2, False)


            if list_items_rows:
                for i, row in enumerate(list_items_rows):
                    row_dict = dict(row)

                    list_name = row_dict.get('list_name', 'Unknown List')
                    media_title = row_dict.get('media_title', 'Unknown Title')

                    item_li = xbmcgui.ListItem(label=f"In List: '{list_name}' - Media: '{media_title}'")
                    item_li.setProperty('IsPlayable', 'false')

                    # Add details
                    details = []
                    for key, value in row_dict.items():
                        if value is not None:
                            details.append(f"{key}: {value}")

                    item_li.setInfo('video', {'plot': '\n'.join(details)})
                    xbmcplugin.addDirectoryItem(handle, "", item_li, False)
            else:
                no_data_li2 = xbmcgui.ListItem(label="No entries found in list_items table for this media item")
                no_data_li2.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, "", no_data_li2, False)

        except Exception as e:
            error_li2 = xbmcgui.ListItem(label=f"Error querying list_items: {str(e)}")
            error_li2.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", error_li2, False)

        # Spacer
        spacer_li3 = xbmcgui.ListItem(label="")
        spacer_li3.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle, "", spacer_li3, False)

        # Table 3: movie_heavy_meta (heavy metadata)
        try:
            # Check if table exists first
            table_exists_result = db_manager.query_manager.execute_query("SELECT name FROM sqlite_master WHERE type='table' AND name='movie_heavy_meta'", fetch_one=True)
            table_exists = table_exists_result is not None

            section_li3 = xbmcgui.ListItem(label="=== MOVIE_HEAVY_META TABLE ===")
            section_li3.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", section_li3, False)

            # Get total heavy meta records
            heavy_total_result = db_manager.query_manager.execute_query("SELECT COUNT(*) as count FROM movie_heavy_meta", fetch_one=True)
            total_heavy = heavy_total_result['count'] if heavy_total_result else 0

            # Get count with IMDb numbers in heavy meta
            heavy_imdb_result = db_manager.query_manager.execute_query(
                "SELECT COUNT(*) as count FROM movie_heavy_meta WHERE imdbnumber IS NOT NULL AND imdbnumber != '' AND imdbnumber LIKE 'tt%'",
                fetch_one=True
            )
            heavy_with_imdb = heavy_imdb_result['count'] if heavy_imdb_result else 0

            if table_exists:
                heavy_meta_query = "SELECT * FROM movie_heavy_meta WHERE imdbnumber = ?"
                heavy_meta_rows = db_manager.query_manager.execute_query(heavy_meta_query, (imdb_id,), fetch_all=True)

                if heavy_meta_rows:
                    for i, row in enumerate(heavy_meta_rows):
                        row_dict = dict(row)

                        kodi_movieid = row_dict.get('kodi_movieid', 'N/A')
                        updated_at = row_dict.get('updated_at', 'N/A')

                        item_li = xbmcgui.ListItem(label=f"Heavy Meta Row {i+1}: Kodi ID {kodi_movieid} (Updated: {updated_at})")
                        item_li.setProperty('IsPlayable', 'false')

                        # Add details with truncated cast
                        details = []
                        for key, value in row_dict.items():
                            if value is not None and str(value).strip():
                                if key == 'cast_json' and value:
                                    # Parse JSON and show first cast member only
                                    try:
                                        import json
                                        cast_data = json.loads(value)
                                        if isinstance(cast_data, list) and len(cast_data) > 0:
                                            first_cast = cast_data[0]
                                            cast_name = first_cast.get('name', 'Unknown') if isinstance(first_cast, dict) else str(first_cast)
                                            details.append(f"cast_json: [{cast_name}] + {len(cast_data)-1} more...")
                                        else:
                                            details.append(f"cast_json: {str(value)[:50]}...")
                                    except:
                                        details.append(f"cast_json: {str(value)[:50]}...")
                                elif len(str(value)) > 100:
                                    details.append(f"{key}: {str(value)[:100]}...")
                                else:
                                    details.append(f"{key}: {value}")

                        item_li.setInfo('video', {'plot': '\n'.join(details)})
                        xbmcplugin.addDirectoryItem(handle, "", item_li, False)
                else:
                    no_data_li3 = xbmcgui.ListItem(label="No entries found in movie_heavy_meta table for this IMDb ID")
                    no_data_li3.setProperty('IsPlayable', 'false')
                    xbmcplugin.addDirectoryItem(handle, "", no_data_li3, False)
            else:
                no_table_li = xbmcgui.ListItem(label="movie_heavy_meta table does not exist")
                no_table_li.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, "", no_table_li, False)

        except Exception as e:
            error_li3 = xbmcgui.ListItem(label=f"Error querying movie_heavy_meta: {str(e)}")
            error_li3.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", error_li3, False)

        # Spacer
        spacer_li3b = xbmcgui.ListItem(label="")
        spacer_li3b.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle, "", spacer_li3b, False)

        # Table 4: imdb_exports
        try:
            # Check if table exists first
            table_exists_result4 = db_manager.query_manager.execute_query("SELECT name FROM sqlite_master WHERE type='table' AND name='imdb_exports'", fetch_one=True)
            table_exists4 = table_exists_result4 is not None

            section_li4 = xbmcgui.ListItem(label="=== IMDB_EXPORTS TABLE ===")
            section_li4.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", section_li4, False)

            # Get total exports
            exports_total_result = db_manager.query_manager.execute_query("SELECT COUNT(*) as count FROM imdb_exports", fetch_one=True)
            total_exports = exports_total_result['count'] if exports_total_result else 0

            # Get valid IMDb exports
            exports_valid_result = db_manager.query_manager.execute_query(
                "SELECT COUNT(*) as count FROM imdb_exports WHERE imdb_id IS NOT NULL AND imdb_id != '' AND imdb_id LIKE 'tt%'",
                fetch_one=True
            )
            valid_exports = exports_valid_result['count'] if exports_valid_result else 0

            if table_exists4:
                imdb_exports_query = "SELECT * FROM imdb_exports WHERE imdb_id = ?"
                imdb_exports_rows = db_manager.query_manager.execute_query(imdb_exports_query, (imdb_id,), fetch_all=True)

                if imdb_exports_rows:
                    for i, row in enumerate(imdb_exports_rows):
                        row_dict = dict(row)

                        export_title = row_dict.get('title', 'Unknown')
                        export_year = row_dict.get('year', 'N/A')

                        item_li = xbmcgui.ListItem(label=f"Export Row {i+1}: {export_title} ({export_year})")
                        item_li.setProperty('IsPlayable', 'false')

                        # Add details
                        details = []
                        for key, value in row_dict.items():
                            if value is not None and str(value).strip():
                                details.append(f"{key}: {value}")

                        item_li.setInfo('video', {'plot': '\n'.join(details)})
                        xbmcplugin.addDirectoryItem(handle, "", item_li, False)
                else:
                    no_data_li4 = xbmcgui.ListItem(label="No entries found in imdb_exports table for this IMDb ID")
                    no_data_li4.setProperty('IsPlayable', 'false')
                    xbmcplugin.addDirectoryItem(handle, "", no_data_li4, False)
            else:
                no_table_li4 = xbmcgui.ListItem(label="imdb_exports table does not exist")
                no_table_li4.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, "", no_table_li4, False)

        except Exception as e:
            error_li4 = xbmcgui.ListItem(label=f"Error querying imdb_exports: {str(e)}")
            error_li4.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", error_li4, False)

        # Spacer
        spacer_li4b = xbmcgui.ListItem(label="")
        spacer_li4b.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle, "", spacer_li4b, False)

        # Table 5: Check for any other tables with IMDb-related columns
        try:
            section_li5 = xbmcgui.ListItem(label="=== OTHER TABLES WITH IMDB DATA ===")
            section_li5.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", section_li5, False)

            # Get all table names
            all_tables_result = db_manager.query_manager.execute_query("SELECT name FROM sqlite_master WHERE type='table'", fetch_all=True)
            all_tables = [row['name'] for row in all_tables_result]

            # Safe table name pattern (alphanumeric and underscore only)
            safe_table_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

            found_other_tables = False
            for table_name in all_tables:
                if table_name in ['media_items', 'list_items', 'movie_heavy_meta', 'imdb_exports']:
                    continue  # Skip already checked tables

                # Skip tables with unsafe names
                if not safe_table_pattern.match(table_name):
                    utils.log(f"Skipping table with unsafe name: {table_name}", "WARNING")
                    continue

                # Get column info for this table
                try:
                    # Safe to use table name directly since we validated it with regex
                    columns = db_manager.query_manager.execute_query(f"PRAGMA table_info({table_name})", fetch_all=True)

                    # Check if any column might contain IMDb data
                    imdb_columns = []
                    for col_info in columns:
                        col_name = col_info['name'].lower()  # Column name
                        if 'imdb' in col_name or col_name in ['imdbnumber', 'uniqueid']:
                            imdb_columns.append(col_info['name'])  # Use original case

                    if imdb_columns:
                        found_other_tables = True
                        table_li = xbmcgui.ListItem(label=f"TABLE: {table_name}")
                        table_li.setProperty('IsPlayable', 'false')
                        xbmcplugin.addDirectoryItem(handle, "", table_li, False)

                        for col_name in imdb_columns:
                            col_li = xbmcgui.ListItem(label=f"  - Column: {col_name}")
                            col_li.setProperty('IsPlayable', 'false')
                            xbmcplugin.addDirectoryItem(handle, "", col_li, False)

                        # Show sample data - safe to use table name since we validated it
                        try:
                            sample_rows = db_manager.query_manager.execute_query(f"SELECT * FROM {table_name} LIMIT 3", fetch_all=True)
                            for i, row in enumerate(sample_rows):
                                row_dict = dict(row)
                                row_str = str(row_dict)[:100] + "..." if len(str(row_dict)) > 100 else str(row_dict)
                                row_li = xbmcgui.ListItem(label=f"    Row {i+1}: {row_str}")
                                row_li.setProperty('IsPlayable', 'false')
                                xbmcplugin.addDirectoryItem(handle, "", row_li, False)
                        except Exception as sample_e:
                            error_sample_li = xbmcgui.ListItem(label=f"    Error getting sample data for {table_name}: {str(sample_e)}")
                            error_sample_li.setProperty('IsPlayable', 'false')
                            xbmcplugin.addDirectoryItem(handle, "", error_sample_li, False)


                except Exception as table_e:
                    error_table_li = xbmcgui.ListItem(label=f"Error processing table {table_name}: {str(table_e)}")
                    error_table_li.setProperty('IsPlayable', 'false')
                    xbmcplugin.addDirectoryItem(handle, "", error_table_li, False)
                    continue  # Skip tables that can't be queried

            if not found_other_tables:
                no_other_li = xbmcgui.ListItem(label="No other tables found with IMDb-related columns")
                no_other_li.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, "", no_other_li, False)

        except Exception as e:
            error_li5 = xbmcgui.ListItem(label=f"Error checking other tables: {str(e)}")
            error_li5.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", error_li5, False)

        # Spacer
        spacer_li4b_end = xbmcgui.ListItem(label="")
        spacer_li4b_end.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle, "", spacer_li4b_end, False)

        # Summary
        summary_li = xbmcgui.ListItem(label=f"=== END DEV DISPLAY FOR {imdb_id} ===")
        summary_li.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle, "", summary_li, False)

        # End directory
        xbmcplugin.endOfDirectory(handle)

    except Exception as e:
        utils.log(f"Error in dev display: {str(e)}", "ERROR")
        import traceback
        utils.log(f"Dev display traceback: {traceback.format_exc()}", "ERROR")

        # Add error item
        error_li = xbmcgui.ListItem(label=f"Error in dev display: {str(e)}")
        error_li.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle, "", error_li, False)
        xbmcplugin.endOfDirectory(handle)
```
