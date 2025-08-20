
import xbmc
import xbmcgui
import xbmcplugin
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

        # Table 1: media_items
        try:
            media_items_query = "SELECT * FROM media_items WHERE imdbnumber = ?"
            db_manager._execute_with_retry(db_manager.cursor.execute, media_items_query, (imdb_id,))
            media_items_rows = db_manager.cursor.fetchall()

            # Add section header
            section_li = xbmcgui.ListItem(label="=== MEDIA_ITEMS TABLE ===")
            section_li.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", section_li, False)

            if media_items_rows:
                for i, row in enumerate(media_items_rows):
                    # Convert row to dict for easier access
                    row_dict = dict(row) if hasattr(row, 'keys') else dict(zip([description[0] for description in db_manager.cursor.description], row))
                    
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
                no_data_li = xbmcgui.ListItem(label="No entries found in media_items table")
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
            db_manager._execute_with_retry(db_manager.cursor.execute, list_items_query, (imdb_id,))
            list_items_rows = db_manager.cursor.fetchall()

            # Add section header
            section_li2 = xbmcgui.ListItem(label="=== LIST_ITEMS TABLE ===")
            section_li2.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", section_li2, False)

            if list_items_rows:
                for i, row in enumerate(list_items_rows):
                    row_dict = dict(row) if hasattr(row, 'keys') else dict(zip([description[0] for description in db_manager.cursor.description], row))
                    
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
                no_data_li2 = xbmcgui.ListItem(label="No entries found in list_items table")
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
            db_manager._execute_with_retry(db_manager.cursor.execute, "SELECT name FROM sqlite_master WHERE type='table' AND name='movie_heavy_meta'")
            table_exists = db_manager.cursor.fetchone()

            section_li3 = xbmcgui.ListItem(label="=== MOVIE_HEAVY_META TABLE ===")
            section_li3.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", section_li3, False)

            if table_exists:
                heavy_meta_query = "SELECT * FROM movie_heavy_meta WHERE imdbnumber = ?"
                db_manager._execute_with_retry(db_manager.cursor.execute, heavy_meta_query, (imdb_id,))
                heavy_meta_rows = db_manager.cursor.fetchall()

                if heavy_meta_rows:
                    for i, row in enumerate(heavy_meta_rows):
                        row_dict = dict(row) if hasattr(row, 'keys') else dict(zip([description[0] for description in db_manager.cursor.description], row))
                        
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
                    no_data_li3 = xbmcgui.ListItem(label="No entries found in movie_heavy_meta table")
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
            db_manager._execute_with_retry(db_manager.cursor.execute, "SELECT name FROM sqlite_master WHERE type='table' AND name='imdb_exports'")
            table_exists = db_manager.cursor.fetchone()

            section_li4 = xbmcgui.ListItem(label="=== IMDB_EXPORTS TABLE ===")
            section_li4.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", section_li4, False)

            if table_exists:
                imdb_exports_query = "SELECT * FROM imdb_exports WHERE imdb_id = ?"
                db_manager._execute_with_retry(db_manager.cursor.execute, imdb_exports_query, (imdb_id,))
                imdb_exports_rows = db_manager.cursor.fetchall()

                if imdb_exports_rows:
                    for i, row in enumerate(imdb_exports_rows):
                        row_dict = dict(row) if hasattr(row, 'keys') else dict(zip([description[0] for description in db_manager.cursor.description], row))
                        
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
                    no_data_li4 = xbmcgui.ListItem(label="No entries found in imdb_exports table")
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
            db_manager._execute_with_retry(db_manager.cursor.execute, "SELECT name FROM sqlite_master WHERE type='table'")
            all_tables = [row[0] for row in db_manager.cursor.fetchall()]

            found_other_tables = False
            for table_name in all_tables:
                if table_name in ['media_items', 'list_items', 'movie_heavy_meta', 'imdb_exports']:
                    continue  # Skip already checked tables

                try:
                    # Get table schema to check for imdb-related columns
                    db_manager._execute_with_retry(db_manager.cursor.execute, f"PRAGMA table_info({table_name})")
                    columns = db_manager.cursor.fetchall()
                    imdb_columns = [col[1] for col in columns if 'imdb' in col[1].lower()]
                    
                    if imdb_columns:
                        found_other_tables = True
                        # Check if this table has data for our IMDb ID
                        for col in imdb_columns:
                            try:
                                query = f"SELECT * FROM {table_name} WHERE {col} = ?"
                                db_manager._execute_with_retry(db_manager.cursor.execute, query, (imdb_id,))
                                rows = db_manager.cursor.fetchall()
                                
                                if rows:
                                    table_li = xbmcgui.ListItem(label=f"Table: {table_name} (Column: {col}) - {len(rows)} rows")
                                    table_li.setProperty('IsPlayable', 'false')
                                    
                                    # Show first row details
                                    if rows:
                                        row = rows[0]
                                        row_dict = dict(zip([desc[0] for desc in db_manager.cursor.description], row))
                                        details = []
                                        for key, value in row_dict.items():
                                            if value is not None and str(value).strip():
                                                details.append(f"{key}: {value}")
                                        table_li.setInfo('video', {'plot': '\n'.join(details)})
                                    
                                    xbmcplugin.addDirectoryItem(handle, "", table_li, False)
                            except Exception as col_e:
                                error_col_li = xbmcgui.ListItem(label=f"Error checking {table_name}.{col}: {str(col_e)}")
                                error_col_li.setProperty('IsPlayable', 'false')
                                xbmcplugin.addDirectoryItem(handle, "", error_col_li, False)
                                
                except Exception as table_e:
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
        spacer_li5 = xbmcgui.ListItem(label="")
        spacer_li5.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle, "", spacer_li5, False)

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
