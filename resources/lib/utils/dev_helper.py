
import xbmc
import xbmcgui
import xbmcplugin
import re
from resources.lib.config.config_manager import Config
from resources.lib.data.database_manager import DatabaseManager
from resources.lib.utils import utils

def _validate_sql_identifier(identifier):
    """Validate SQL identifier against safe pattern"""
    if not identifier or not isinstance(identifier, str):
        return False
        
    # Check safe name pattern: alphanumeric, underscore, no spaces, reasonable length
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier) or len(identifier) > 64:
        return False

    # Additional check: identifier must not be a SQL keyword
    sql_keywords = {
        'select', 'insert', 'update', 'delete', 'drop', 'create', 'alter', 
        'table', 'index', 'view', 'trigger', 'database', 'schema', 'from',
        'where', 'join', 'union', 'group', 'order', 'having', 'limit'
    }

    return identifier.lower() not in sql_keywords

def _validate_table_exists(query_manager, table_name):
    """Validate table exists in sqlite_master using query_manager"""
    if not _validate_sql_identifier(table_name):
        utils.log(f"Invalid table identifier: {table_name}", "ERROR")
        return False

    result = query_manager.execute_query(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
        fetch_one=True
    )
    return result is not None

def display_imdb_data_as_directory(handle):
    """Display database structure and sample data using only query_manager"""
    try:
        config = Config()
        db_manager = DatabaseManager(config.db_path)
        query_manager = db_manager.query_manager

        # Get all table names from the database using query_manager
        tables = query_manager.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", 
            fetch_all=True
        )

        # Ensure tables is not None before iterating
        if tables is None:
            utils.log("No tables retrieved from the database", "ERROR")
            tables = []

        for table_info in tables:
            # Ensure dict representation for consistent access
            table_dict = dict(table_info) if table_info else {}
            table_name = table_dict.get('name', 'unknown')

            if table_name == 'sqlite_sequence':
                continue  # Skip system table

            # Validate table name for security
            if not _validate_table_exists(query_manager, table_name):
                error_li = xbmcgui.ListItem(label=f"Invalid table name: {table_name}")
                error_li.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, "", error_li, False)
                continue

            try:
                # Get table info using query_manager with validated table name
                # Use the query_manager's internal validation since table name is already validated
                table_structure = query_manager.execute_query(
                    f"PRAGMA table_info({table_name})", 
                    fetch_all=True
                )

                # Ensure table_structure is not None before using
                if table_structure is None:
                    table_structure = []

                # Count rows using parameterized query with validated table name and explicit alias
                count_result = query_manager.execute_query(
                    f"SELECT COUNT(*) as row_count FROM {table_name}",
                    fetch_one=True
                )
                # Ensure we work with dict representation for consistent access
                if count_result:
                    count_dict = dict(count_result)
                    row_count = count_dict.get('row_count', 0)
                else:
                    row_count = 0

                # Create list item for table
                table_li = xbmcgui.ListItem(label=f"Table: {table_name} ({row_count} rows)")
                table_li.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, "", table_li, False)

                # Show structure - ensure dict representation
                for col in table_structure:
                    col_dict = dict(col) if col else {}
                    col_name = col_dict.get('name', 'unknown')
                    col_type = col_dict.get('type', 'unknown')
                    col_nullable = "NOT NULL" if col_dict.get('notnull', 0) else "NULL"
                    col_li = xbmcgui.ListItem(label=f"  Column: {col_name} ({col_type}, {col_nullable})")
                    col_li.setProperty('IsPlayable', 'false')
                    xbmcplugin.addDirectoryItem(handle, "", col_li, False)

                # Show sample data using validated table name and query_manager
                try:
                    sample_rows = query_manager.execute_query(
                        f"SELECT * FROM {table_name} LIMIT 3",
                        fetch_all=True
                    )
                    
                    # Ensure sample_rows is not None before iterating
                    if sample_rows is None:
                        sample_rows = []
                        
                    for i, row in enumerate(sample_rows):
                        # Ensure we always work with dict representation
                        if row:
                            row_dict = dict(row)
                            row_str = str(row_dict)[:100] + "..." if len(str(row_dict)) > 100 else str(row_dict)
                        else:
                            row_str = "Empty row"
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
                continue

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
