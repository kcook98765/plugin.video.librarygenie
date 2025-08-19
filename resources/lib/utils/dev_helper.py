
import xbmcgui
import xbmcplugin
from resources.lib.config.config_manager import Config
from resources.lib.data.database_manager import DatabaseManager
from resources.lib.utils import utils


def display_imdb_data_as_directory(params, handle):
    """Display all database data for an IMDb ID as directory items"""
    try:
        imdb_id = params.get('imdb_id')
        title = params.get('title', '')

        if not imdb_id or not str(imdb_id).startswith('tt'):
            # Add error item
            li = xbmcgui.ListItem(label="ERROR: No valid IMDb ID found")
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
        header_li = xbmcgui.ListItem(label=f"DEV DISPLAY - {title} ({imdb_id})")
        header_li.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle, "", header_li, False)

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
                columns = [description[0] for description in db_manager.cursor.description]
                for i, row in enumerate(media_items_rows):
                    row_li = xbmcgui.ListItem(label=f"Media Item Row {i+1}")
                    row_li.setProperty('IsPlayable', 'false')
                    
                    # Create plot with all column data
                    plot_lines = []
                    for col_name, value in zip(columns, row):
                        plot_lines.append(f"{col_name}: {value}")
                    row_li.getVideoInfoTag().setPlot("\n".join(plot_lines))
                    
                    xbmcplugin.addDirectoryItem(handle, "", row_li, False)
            else:
                no_data_li = xbmcgui.ListItem(label="No records found")
                no_data_li.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, "", no_data_li, False)

        except Exception as e:
            error_li = xbmcgui.ListItem(label=f"Error querying media_items: {str(e)}")
            error_li.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", error_li, False)

        # Table 2: imdb_exports
        try:
            imdb_exports_query = "SELECT * FROM imdb_exports WHERE imdb_id = ?"
            db_manager._execute_with_retry(db_manager.cursor.execute, imdb_exports_query, (imdb_id,))
            imdb_exports_rows = db_manager.cursor.fetchall()

            # Add section header
            section_li = xbmcgui.ListItem(label="=== IMDB_EXPORTS TABLE ===")
            section_li.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", section_li, False)

            if imdb_exports_rows:
                columns = [description[0] for description in db_manager.cursor.description]
                for i, row in enumerate(imdb_exports_rows):
                    row_li = xbmcgui.ListItem(label=f"Export Row {i+1}")
                    row_li.setProperty('IsPlayable', 'false')
                    
                    # Create plot with all column data
                    plot_lines = []
                    for col_name, value in zip(columns, row):
                        plot_lines.append(f"{col_name}: {value}")
                    row_li.getVideoInfoTag().setPlot("\n".join(plot_lines))
                    
                    xbmcplugin.addDirectoryItem(handle, "", row_li, False)
            else:
                no_data_li = xbmcgui.ListItem(label="No records found")
                no_data_li.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, "", no_data_li, False)

        except Exception as e:
            error_li = xbmcgui.ListItem(label=f"Error querying imdb_exports: {str(e)}")
            error_li.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", error_li, False)

        # Table 3: movie_heavy_meta
        try:
            heavy_meta_query = "SELECT * FROM movie_heavy_meta WHERE imdbnumber = ?"
            db_manager._execute_with_retry(db_manager.cursor.execute, heavy_meta_query, (imdb_id,))
            heavy_meta_rows = db_manager.cursor.fetchall()

            # Add section header
            section_li = xbmcgui.ListItem(label="=== MOVIE_HEAVY_META TABLE ===")
            section_li.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", section_li, False)

            if heavy_meta_rows:
                columns = [description[0] for description in db_manager.cursor.description]
                for i, row in enumerate(heavy_meta_rows):
                    row_li = xbmcgui.ListItem(label=f"Heavy Meta Row {i+1}")
                    row_li.setProperty('IsPlayable', 'false')
                    
                    # Create plot with all column data
                    plot_lines = []
                    for col_name, value in zip(columns, row):
                        plot_lines.append(f"{col_name}: {value}")
                    row_li.getVideoInfoTag().setPlot("\n".join(plot_lines))
                    
                    xbmcplugin.addDirectoryItem(handle, "", row_li, False)
            else:
                no_data_li = xbmcgui.ListItem(label="No records found")
                no_data_li.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, "", no_data_li, False)

        except Exception as e:
            error_li = xbmcgui.ListItem(label=f"Error querying movie_heavy_meta: {str(e)}")
            error_li.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", error_li, False)

        # Table 4: List associations
        try:
            list_associations_query = """
                SELECT l.name as list_name, f.name as folder_name, li.list_id, li.media_item_id
                FROM list_items li
                JOIN lists l ON li.list_id = l.id
                LEFT JOIN folders f ON l.folder_id = f.id
                JOIN media_items mi ON li.media_item_id = mi.id
                WHERE mi.imdbnumber = ?
            """
            db_manager._execute_with_retry(db_manager.cursor.execute, list_associations_query, (imdb_id,))
            list_rows = db_manager.cursor.fetchall()

            # Add section header
            section_li = xbmcgui.ListItem(label="=== LIST ASSOCIATIONS ===")
            section_li.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", section_li, False)

            if list_rows:
                columns = [description[0] for description in db_manager.cursor.description]
                for i, row in enumerate(list_rows):
                    row_li = xbmcgui.ListItem(label=f"Association {i+1}")
                    row_li.setProperty('IsPlayable', 'false')
                    
                    # Create plot with all column data
                    plot_lines = []
                    for col_name, value in zip(columns, row):
                        plot_lines.append(f"{col_name}: {value}")
                    row_li.getVideoInfoTag().setPlot("\n".join(plot_lines))
                    
                    xbmcplugin.addDirectoryItem(handle, "", row_li, False)
            else:
                no_data_li = xbmcgui.ListItem(label="No list associations found")
                no_data_li.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, "", no_data_li, False)

        except Exception as e:
            error_li = xbmcgui.ListItem(label=f"Error querying associations: {str(e)}")
            error_li.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(handle, "", error_li, False)

        xbmcplugin.endOfDirectory(handle)

    except Exception as e:
        utils.log(f"Error in display_imdb_data_as_directory: {str(e)}", "ERROR")
        import traceback
        utils.log(f"Dev Display traceback: {traceback.format_exc()}", "ERROR")
        
        # Add error item
        error_li = xbmcgui.ListItem(label=f"Dev Display error: {str(e)}")
        error_li.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(handle, "", error_li, False)
        xbmcplugin.endOfDirectory(handle)
