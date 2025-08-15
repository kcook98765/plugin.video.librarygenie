from .database_manager import DatabaseManager
from .config_manager import Config
from . import utils

class ApiClient:
    """Legacy API client - only maintains non-remote API functionality"""

    def __init__(self):
        self.config = Config()
        self.db_manager = DatabaseManager(Config().db_path)

    def export_imdb_list(self, list_id):
        """Export list items to IMDB format"""
        from resources.lib.database_sync_manager import DatabaseSyncManager
        from resources.lib.query_manager import QueryManager

        query_manager = QueryManager(Config().db_path)
        sync_manager = DatabaseSyncManager(query_manager)

        sync_manager.setup_tables()
        return sync_manager.sync_library_movies()

# All remote API functionality has been moved to remote_api_client.py