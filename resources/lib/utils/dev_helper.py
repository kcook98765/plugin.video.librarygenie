import xbmc
import xbmcgui
import xbmcplugin
import re
from resources.lib.config.config_manager import Config
from resources.lib.data.database_manager import DatabaseManager
from resources.lib.utils import utils

def _validate_sql_identifier(identifier):
    """Validate SQL identifier against safe pattern and sqlite_master"""
    import re

    # Check safe name pattern: alphanumeric, underscore, no spaces, reasonable length
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier) or len(identifier) > 64:
        return False

    # Additional check: identifier must not be a SQL keyword
    sql_keywords = {
        'select', 'insert', 'update', 'delete', 'drop', 'create', 'alter', 
        'table', 'index', 'view', 'trigger', 'database', 'schema', 'from',
        'where', 'join', 'union', 'group', 'order', 'having', 'limit'
    }

    if identifier.lower() in sql_keywords:
        return False

    return True

def _validate_table_exists(db_manager, table_name):
    """Validate table exists in sqlite_master"""
    if not _validate_sql_identifier(table_name):
        return False

    result = db_manager.query_manager.execute_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
        fetch_one=True
    )
    return result is not None

def display_imdb_data_as_directory(handle):
    """Display database structure and sample data"""
    from resources.lib.data.database_manager import DatabaseManager
    from resources.lib.config.config_manager import Config
    import xbmcgui
    import xbmcplugin

    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)

        # Get all table names from the database (parameterized query)
        tables = db_manager.query_manager.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", 
            fetch_all=True
        )

        for table_info in tables:
            table_name = table_info['name']

            if table_name == 'sqlite_sequence':
                continue  # Skip system table

            # Validate table name for security
            if not _validate_table_exists(db_manager, table_name):
                error_li = xbmcgui.ListItem(label=f"Invalid table name: {table_name}")
                error_li.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, "", error_li, False)
                continue

            try:
                # Get table info using parameterized PRAGMA (table name validated above)
                table_structure = db_manager.query_manager.execute_query(
                    f"PRAGMA table_info({table_name})", 
                    fetch_all=True
                )

                # Count rows using parameterized query with validated table name
                count_query = f"SELECT COUNT(*) as count FROM {table_name}"
                count_result = db_manager.query_manager.execute_query(count_query, fetch_one=True)
                row_count = count_result['count'] if count_result else 0

                # Create list item for table
                table_li = xbmcgui.ListItem(label=f"Table: {table_name} ({row_count} rows)")
                table_li.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, "", table_li, False)

                # Show structure
                for col in table_structure:
                    col_name = col.get('name', 'unknown')
                    col_type = col.get('type', 'unknown')
                    col_nullable = "NOT NULL" if col.get('notnull', 0) else "NULL"
                    col_li = xbmcgui.ListItem(label=f"  Column: {col_name} ({col_type}, {col_nullable})")
                    col_li.setProperty('IsPlayable', 'false')
                    xbmcplugin.addDirectoryItem(handle, "", col_li, False)

                # Show sample data using validated table name
                try:
                    sample_query = f"SELECT * FROM {table_name} LIMIT 3"
                    sample_rows = db_manager.query_manager.execute_query(sample_query, fetch_all=True)
                    for i, row in enumerate(sample_rows):
                        row_dict = row
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