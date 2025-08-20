import os
import sqlite3
import json
import time
from resources.lib.utils import utils
from resources.lib.config.config_manager import Config
from datetime import datetime # Import datetime

from resources.lib.utils.singleton_base import Singleton

class DatabaseManager(Singleton):
    SCHEMA_VERSION = 2

    def __init__(self, db_path):
        if not hasattr(self, '_initialized'):
            self.db_path = db_path
            self.config = Config()  # Instantiate Config to access FIELDS
            self._connect()
            self.setup_database()
            self.ensure_search_history_folder()
            self.ensure_imported_lists_folder()
            # Initialize query_manager for direct access
            from resources.lib.data.query_manager import QueryManager
            self._query_manager = QueryManager(self.db_path)
            self._initialized = True

    def _connect(self):
        try:
            # Ensure the directory exists
            db_dir = os.path.dirname(self.db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir)

            self.connection = sqlite3.connect(self.db_path, timeout=60.0)  # Increased timeout
            self.cursor = self.connection.cursor()

            # Performance optimizations for bulk operations
            self.cursor.execute('PRAGMA foreign_keys = ON')
            self.cursor.execute('PRAGMA journal_mode = WAL')  # Write-Ahead Logging for better concurrency
            self.cursor.execute('PRAGMA synchronous = NORMAL')  # Faster writes
            self.cursor.execute('PRAGMA cache_size = 20000')  # Larger cache for heavy operations
            self.cursor.execute('PRAGMA temp_store = MEMORY')  # Use memory for temp tables
            self.cursor.execute('PRAGMA busy_timeout = 60000')  # 60 second busy timeout

        except Exception as e:
            utils.log(f"Database connection error: {str(e)}", "ERROR")
            raise

    def optimize_for_heavy_operations(self):
        """Optimize database settings for heavy batch operations"""
        try:
            utils.log("=== OPTIMIZING DATABASE FOR HEAVY OPERATIONS ===", "INFO")

            # Check initial WAL state
            self.cursor.execute('PRAGMA wal_checkpoint')
            utils.log("Initial WAL checkpoint completed", "DEBUG")

            self.cursor.execute('PRAGMA synchronous = OFF')  # Fastest writes for bulk operations
            utils.log("Set synchronous = OFF", "DEBUG")

            self.cursor.execute('PRAGMA cache_size = 50000')  # Even larger cache
            utils.log("Set cache_size = 50000", "DEBUG")

            self.cursor.execute('PRAGMA locking_mode = EXCLUSIVE')  # Exclusive access during bulk ops
            utils.log("Set locking_mode = EXCLUSIVE", "DEBUG")

            # Verify settings
            self.cursor.execute('PRAGMA synchronous')
            sync_mode = self.cursor.fetchone()[0]
            self.cursor.execute('PRAGMA locking_mode')
            lock_mode = self.cursor.fetchone()[0]

            utils.log(f"Verified settings - synchronous: {sync_mode}, locking_mode: {lock_mode}", "INFO")
            utils.log("Database optimization complete", "INFO")
        except Exception as e:
            utils.log(f"Error optimizing database: {str(e)}", "WARNING")

    def restore_normal_operations(self):
        """Restore normal database settings after heavy operations"""
        try:
            utils.log("Restoring normal database settings", "INFO")
            self.cursor.execute('PRAGMA synchronous = NORMAL')
            self.cursor.execute('PRAGMA cache_size = 20000')
            self.cursor.execute('PRAGMA locking_mode = NORMAL')
            utils.log("Database settings restored to normal", "DEBUG")
        except Exception as e:
            utils.log(f"Error restoring database settings: {str(e)}", "WARNING")

    @property
    def query_manager(self):
        """Access to QueryManager instance"""
        if not hasattr(self, '_query_manager'):
            from resources.lib.data.query_manager import QueryManager
            self._query_manager = QueryManager(self.db_path)
        return self._query_manager

    def _execute_with_retry(self, func, *args, **kwargs):
        retries = 20  # Increase retry count for heavy operations
        operation_name = func.__name__ if hasattr(func, '__name__') else str(func)
        utils.log(f"=== RETRY OPERATION START: {operation_name} ===", "DEBUG")

        for i in range(retries):
            try:
                utils.log(f"Executing {operation_name} attempt {i+1}/{retries}", "DEBUG")
                result = func(*args, **kwargs)
                if i > 0:  # Only log if we had to retry
                    utils.log(f"=== RETRY SUCCESS: {operation_name} succeeded on attempt {i+1} ===", "INFO")
                return result
            except sqlite3.OperationalError as e:
                if 'database is locked' in str(e):
                    # More aggressive exponential backoff for heavy operations
                    wait_time = min(0.2 * (1.5 ** i), 5.0)  # Cap at 5 seconds
                    utils.log(f"=== DATABASE LOCK DETECTED ===", "ERROR")
                    utils.log(f"Operation: {operation_name}", "ERROR")
                    utils.log(f"Attempt: {i+1}/{retries}", "ERROR")
                    utils.log(f"Args: {args[:2] if args else 'None'}", "ERROR")  # Log first 2 args only
                    utils.log(f"Wait time: {wait_time:.2f}s", "ERROR")
                    utils.log(f"=== END DATABASE LOCK INFO ===", "ERROR")

                    time.sleep(wait_time)

                    # Force a checkpoint every 5 retries to help with WAL mode
                    if i > 0 and i % 5 == 0:
                        try:
                            utils.log(f"Forcing WAL checkpoint on attempt {i+1}", "INFO")
                            self.cursor.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                            utils.log("WAL checkpoint completed successfully", "INFO")
                        except Exception as checkpoint_error:
                            utils.log(f"WAL checkpoint failed: {str(checkpoint_error)}", "WARNING")
                else:
                    utils.log(f"Database error (non-lock) in {operation_name}: {str(e)}", "ERROR")
                    raise

        # If all retries failed
        utils.log(f"=== RETRY OPERATION FAILED: {operation_name} after {retries} attempts ===", "ERROR")
        raise sqlite3.OperationalError(f"Database is locked - {operation_name} failed after retries")

    def setup_database(self):
        """Initialize database with required tables"""
        try:
            utils.log(f"Setting up database schema version {self.SCHEMA_VERSION}...", "DEBUG")

            conn_info = self.query_manager._get_connection()

            try:
                # Check if already in transaction by testing a rollback
                in_transaction = False
                try:
                    conn_info['connection'].execute("SAVEPOINT test_transaction")
                    conn_info['connection'].execute("ROLLBACK TO test_transaction")
                    conn_info['connection'].execute("RELEASE test_transaction")
                except:
                    in_transaction = True

                # Only start transaction if not already in one
                if not in_transaction:
                    conn_info['connection'].execute("BEGIN IMMEDIATE")

                # Create tables if they don't exist
                self._create_tables(conn_info['connection'].cursor())

                # Check current schema version
                cursor = conn_info['connection'].cursor()
                cursor.execute("PRAGMA user_version")
                version_result = cursor.fetchone()
                current_version = version_result[0] if version_result else 0
                utils.log(f"Current database schema version: {current_version}", "DEBUG")

                # Run migrations if needed
                if current_version < self.SCHEMA_VERSION:
                    utils.log(f"Running database migrations from version {current_version} to {self.SCHEMA_VERSION}", "INFO")
                    self._run_migrations(conn_info['connection'].cursor(), current_version)
                    conn_info['connection'].cursor().execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
                    utils.log("Database migrations completed successfully", "INFO")
                else:
                    utils.log("Database schema is up-to-date.", "INFO")

                # Only commit if we started the transaction
                if not in_transaction:
                    conn_info['connection'].commit()

            except Exception as e:
                try:
                    conn_info['connection'].rollback()
                except:
                    pass  # Rollback might fail if no transaction was started
                utils.log(f"Database setup transaction failed: {str(e)}", "ERROR")
                raise
            finally:
                self.query_manager._release_connection(conn_info)

            utils.log("Database setup completed successfully", "DEBUG")
        except Exception as e:
            utils.log(f"Database setup failed: {str(e)}", "ERROR")
            raise

    def _create_tables(self, cursor):
        """Create all necessary tables if they do not exist"""
        # Create folders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_id INTEGER,
                FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_folders_parent_id ON folders (parent_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_folders_name ON folders (name)')

        # Create lists table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                folder_id INTEGER,
                protected INTEGER DEFAULT 0,
                FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_lists_folder_id ON lists (folder_id)')

        # Create media_items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS media_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kodi_id INTEGER DEFAULT 0,
                title TEXT,
                year INTEGER DEFAULT 0,
                rating REAL DEFAULT 0.0,
                plot TEXT,
                tagline TEXT,
                genre TEXT,
                director TEXT,
                studio TEXT,
                writer TEXT,
                country TEXT,
                cast TEXT,
                imdbnumber TEXT,
                art TEXT,
                poster TEXT,
                fanart TEXT,
                source TEXT,
                search_score INTEGER DEFAULT 0,
                duration INTEGER DEFAULT 0,
                votes INTEGER DEFAULT 0,
                play TEXT,
                media_type TEXT DEFAULT 'movie'
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_media_items_kodi_id ON media_items (kodi_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_media_items_title ON media_items (title)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_media_items_imdbnumber ON media_items (imdbnumber)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_media_items_play ON media_items (play)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_media_items_source ON media_items (source)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_media_items_media_type ON media_items (media_type)')


        # Create list_items junction table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS list_items (
                list_id INTEGER NOT NULL,
                media_item_id INTEGER NOT NULL,
                PRIMARY KEY (list_id, media_item_id),
                FOREIGN KEY (list_id) REFERENCES lists(id) ON DELETE CASCADE,
                FOREIGN KEY (media_item_id) REFERENCES media_items(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_list_items_media_item_id ON list_items (media_item_id)')

        # Create original_requests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS original_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT,
                response_json TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create parsed_movies table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS parsed_movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER,
                title TEXT,
                year INTEGER,
                director TEXT,
                FOREIGN KEY (request_id) REFERENCES original_requests(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_parsed_movies_request_id ON parsed_movies (request_id)')

        # Create imdb_exports table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS imdb_exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                imdb_id TEXT NOT NULL,
                title TEXT,
                year INTEGER,
                genre TEXT,
                plot TEXT,
                rating REAL,
                votes INTEGER,
                director TEXT,
                cast TEXT,
                runtime INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(kodi_id, imdb_id)
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_imdb_exports_imdb_id ON imdb_exports (imdb_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_imdb_exports_title_year ON imdb_exports (title, year)')

        # Create movie_heavy_meta table for caching expensive fields
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movie_heavy_meta (
                kodi_movieid INTEGER PRIMARY KEY,
                imdbnumber TEXT,
                cast_json TEXT,
                ratings_json TEXT,
                showlink_json TEXT,
                stream_json TEXT,
                uniqueid_json TEXT,
                tags_json TEXT,
                updated_at INTEGER NOT NULL
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_heavy_imdb ON movie_heavy_meta (imdbnumber)')


    def _run_migrations(self, cursor, from_version):
        """Run database migrations"""
        if from_version < 1:
            # Migration to version 1
            utils.log("Running migration to version 1", "DEBUG")
            # Add any schema changes for version 1 here
            pass

        if from_version < 2:
            # Migration to version 2 - add movie_heavy_meta table
            utils.log("Running migration to version 2 - adding movie_heavy_meta table", "INFO")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS movie_heavy_meta (
                    kodi_movieid INTEGER PRIMARY KEY,
                    imdbnumber TEXT,
                    cast_json TEXT,
                    ratings_json TEXT,
                    showlink_json TEXT,
                    stream_json TEXT,
                    uniqueid_json TEXT,
                    tags_json TEXT,
                    updated_at INTEGER NOT NULL
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_heavy_imdb ON movie_heavy_meta (imdbnumber)')
            utils.log("Movie heavy meta table created successfully", "INFO")

    def fetch_folders(self, parent_id=None):
        return self.query_manager.fetch_folders_direct(parent_id)

    def fetch_lists(self, folder_id=None):
        return self.query_manager.fetch_lists_direct(folder_id)

    def fetch_data(self, table, condition=None):
        """Generic method to fetch data from a table"""
        try:
            if condition:
                query = f"SELECT * FROM {table} WHERE {condition}"
            else:
                query = f"SELECT * FROM {table}"
            self._execute_with_retry(self.cursor.execute, query)
            rows = self.cursor.fetchall()

            # Get column names
            columns = [description[0] for description in self.cursor.description]

            # Convert rows to list of dictionaries
            result = []
            for row in rows:
                result.append(dict(zip(columns, row)))

            return result
        except Exception as e:
            utils.log(f"Error fetching data from {table}: {str(e)}", "ERROR")
            return []

    def get_folder_depth(self, folder_id):
        return self.query_manager.get_folder_depth(folder_id)

    def insert_folder(self, name, parent_id=None):
        self.query_manager.insert_folder_direct(name, parent_id)

    def update_list_folder(self, list_id, folder_id):
        self.query_manager.update_list_folder(list_id, folder_id)

    def fetch_lists_with_item_status(self, media_item_id, folder_id=None):
        return self.query_manager.fetch_lists_with_item_status(folder_id, media_item_id)

    def fetch_all_lists_with_item_status(self, media_item_id):
        return self.query_manager.fetch_all_lists_with_item_status(media_item_id)

    def fetch_list_items(self, list_id):
        return self.query_manager.fetch_list_items_with_details(list_id)

    def fetch_list_items_with_details(self, list_id):
        return self.query_manager.fetch_list_items_with_details(list_id)

    def truncate_data(self, data, max_length=10):
        truncated_data = {}
        for key, value in data.items():
            str_value = str(value)
            if len(str_value) > max_length:
                truncated_data[key] = str_value[:max_length] + "..."
            else:
                truncated_data[key] = str_value
        return truncated_data

    def bulk_insert_data(self, table, data_list):
        """Bulk insert multiple records in a single transaction for better performance"""
        if not data_list:
            return []

        try:
            self.connection.execute("BEGIN TRANSACTION")

            # Prepare the query
            first_item = data_list[0]
            columns = ', '.join(first_item.keys())
            placeholders = ', '.join(['?' for _ in first_item])
            query = f'INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})'

            # Convert cast lists to JSON strings if needed
            processed_data = []
            for data in data_list:
                if 'cast' in data and isinstance(data['cast'], list):
                    data = data.copy()  # Don't modify original
                    data['cast'] = json.dumps(data['cast'])
                processed_data.append(tuple(data.values()))

            # Execute bulk insert
            self.cursor.executemany(query, processed_data)
            self.connection.commit()

            utils.log(f"Bulk inserted {len(data_list)} records into {table}", "DEBUG")

            # Handle case where lastrowid is None (when INSERT OR IGNORE doesn't insert any rows)
            lastrowid = self.cursor.lastrowid
            if lastrowid is None:
                utils.log(f"No rows inserted into {table}. Possible conflict or ignore situation.", "WARNING")
                return []

            return [lastrowid - len(data_list) + i + 1 for i in range(len(data_list))]

        except Exception as e:
            self.connection.rollback()
            utils.log(f"Error in bulk insert to {table}: {str(e)}", "ERROR")
            raise

    def insert_data(self, table, data):
        # Convert the cast list to a JSON string if it exists
        if 'cast' in data and isinstance(data['cast'], list):
            data['cast'] = json.dumps(data['cast'])

        if table == 'lists':
            utils.log(f"Inserting into lists table: {data}", "DEBUG")
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            query = f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'

            self._execute_with_retry(self.cursor.execute, query, tuple(data.values()))
            self.connection.commit()
            last_id = self.cursor.lastrowid
            utils.log(f"Inserted into {table}, got ID: {last_id}", "DEBUG")
            return last_id
        elif table == 'media_items':
            # Handle media_items directly to avoid creating new connections
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            query = f'INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})'

            try:
                cursor = self.cursor
                values = tuple(data.values())
                cursor.execute(query, values)
                self.connection.commit()
                row_id = cursor.lastrowid
                # Only log insertions for non-media_items or in debug mode
                if table != 'media_items' or utils.is_debug_enabled():
                    utils.log(f"Inserted into {table}, got ID: {row_id}", "DEBUG")
                return row_id
            except sqlite3.Error as e:
                utils.log(f"Error inserting into {table}: {str(e)}", "ERROR")
                raise
        elif table == 'list_items':
            media_item_id = self.query_manager.insert_media_item(data)
            if media_item_id:
                self.query_manager.insert_list_item(data['list_id'], media_item_id)
                utils.log(f"Inserted list item with media_item_id: {media_item_id}", "DEBUG")
            else:
                utils.log("No media_item_id found, insertion skipped", "ERROR")
        else:
            # For other tables, use generic insert with existing connection
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            query = f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'

            self._execute_with_retry(self.cursor.execute, query, tuple(data.values()))
            self.connection.commit()

        utils.log(f"Data inserted into {table} successfully", "DEBUG")

    def _insert_or_ignore(self, table_name, data):
        # Check if data is not empty
        if not data:
            utils.log(f"_insert_or_ignore data is empty: {data}", "DEBUG")
            return

        # Prepare column names and placeholders for values
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))

        # Construct the SQL query
        query = f"INSERT OR IGNORE INTO {table_name} ({columns}) VALUES ({placeholders})"

        # Execute the query with the data values
        self._execute_with_retry(self.cursor.execute, query, tuple(data.values()))
        self.connection.commit()

    def is_list_protected(self, list_id):
        """Check if a list is protected from modification"""
        list_data = self.query_manager.fetch_list_by_id(list_id)
        return list_data and list_data.get('protected', 0) == 1

    def is_search_history_folder(self, folder_id):
        """Check if a folder is the Search History folder"""
        search_history_folder_id = self.get_folder_id_by_name("Search History")
        return folder_id == search_history_folder_id

    def delete_data(self, table, condition):
        query = f'DELETE FROM {table} WHERE {condition}'
        utils.log(f"Executing SQL: {query}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query)
        self.connection.commit()

    def get_list_id_by_name(self, list_name):
        return self.query_manager.get_list_id_by_name(list_name)

    def get_lists_for_item(self, item_id):
        return self.query_manager.get_lists_for_item(item_id)

    def fetch_all_folders(self):
        return self.query_manager.fetch_all_folders()

    def fetch_lists_by_folder(self, folder_id):
        """Fetch all lists in a specific folder"""
        try:
            if folder_id is None:
                condition = "folder_id IS NULL"
            else:
                condition = f"folder_id = {folder_id}"

            lists = self.fetch_data('lists', condition)
            return lists if lists else []
        except Exception as e:
            utils.log(f"Error fetching lists by folder {folder_id}: {str(e)}", "ERROR")
            return []

    def fetch_all_lists(self):
        return self.query_manager.fetch_all_lists()

    def get_item_id_by_title_and_list(self, list_id, title):
        return self.query_manager.get_item_id_by_title_and_list(list_id, title)

    def update_folder_name(self, folder_id, new_name):
        self.query_manager.update_folder_name(folder_id, new_name)

    def update_folder_parent(self, folder_id, new_parent_id, override_depth_check=False):
        if new_parent_id is not None:
            # Check if move would create a cycle
            temp_parent = new_parent_id
            while temp_parent is not None:
                if temp_parent == folder_id:
                    raise ValueError("Cannot move folder: would create a cycle")
                folder = self.query_manager.fetch_folder_by_id(temp_parent)
                temp_parent = folder['parent_id'] if folder else None

            # Check depth limit unless overridden
            if not override_depth_check:
                # Get the depth of the subtree being moved
                subtree_depth = self._get_subtree_depth(folder_id)

                # Get the depth at the new location
                target_depth = self.query_manager.get_folder_depth(new_parent_id)

                # Calculate total depth after move
                total_depth = target_depth + subtree_depth + 1

                if total_depth > self.config.max_folder_depth:
                    raise ValueError(f"Moving folder would exceed maximum depth of {self.config.max_folder_depth}")

        self.query_manager.update_folder_parent(folder_id, new_parent_id)

    def _get_subtree_depth(self, folder_id):
        """Calculate the maximum depth of a folder's subtree"""
        query = """
            WITH RECURSIVE folder_tree AS (
                SELECT id, parent_id, 0 as depth
                FROM folders
                WHERE id = ?
                UNION ALL
                SELECT f.id, f.parent_id, ft.depth + 1
                FROM folders f
                JOIN folder_tree ft ON f.parent_id = ft.id
            )
            SELECT MAX(depth) FROM folder_tree
        """
        self._execute_with_retry(self.cursor.execute, query, (folder_id,))
        result = self.cursor.fetchone()
        return result[0] if result[0] is not None else 0

    def delete_folder_and_contents(self, folder_id):
        try:
            self.connection.execute("BEGIN")

            # Get all nested folder IDs
            self._execute_with_retry(self.cursor.execute, """
                WITH RECURSIVE nested_folders AS (
                    SELECT id FROM folders WHERE id = ?
                    UNION ALL
                    SELECT f.id FROM folders f
                    JOIN nested_folders nf ON f.parent_id = nf.id
                )
                SELECT id FROM nested_folders
            """, (folder_id,))
            folder_ids = [row[0] for row in self.cursor.fetchall()]

            if folder_ids:
                # Get all list IDs in these folders
                placeholders = ','.join('?' * len(folder_ids))
                self._execute_with_retry(self.cursor.execute,
                    f"SELECT id FROM lists WHERE folder_id IN ({placeholders})",
                    folder_ids)
                list_ids = [row[0] for row in self.cursor.fetchall()]

                # Delete all related records for each list
                for list_id in list_ids:
                    # Delete from list_items
                    self._execute_with_retry(self.cursor.execute,
                        "DELETE FROM list_items WHERE list_id = ?",
                        (list_id,))

                # Now delete the lists themselves
                self._execute_with_retry(self.cursor.execute,
                    f"DELETE FROM lists WHERE folder_id IN ({placeholders})",
                    folder_ids)

                # Finally delete all nested folders (in reverse order - children first)
                # Sort by depth descending to delete children before parents
                self._execute_with_retry(self.cursor.execute, """
                    WITH RECURSIVE nested_folders AS (
                        SELECT id, 0 as depth FROM folders WHERE id = ?
                        UNION ALL
                        SELECT f.id, nf.depth + 1 FROM folders f
                        JOIN nested_folders nf ON f.parent_id = nf.id
                    )
                    DELETE FROM folders WHERE id IN (
                        SELECT id FROM nested_folders ORDER BY depth DESC
                    )
                """, (folder_id,))

            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            utils.log(f"Error during folder deletion rollback: {str(e)}", "ERROR")
            raise e

    def fetch_folder_by_id(self, folder_id):
        return self.query_manager.fetch_folder_by_id(folder_id)

    def fetch_list_by_id(self, list_id):
        return self.query_manager.fetch_list_by_id(list_id)

    def fetch_folders_with_item_status(self, media_item_id, parent_id=None):
        return self.query_manager.fetch_folders_with_item_status(parent_id, media_item_id)

    def remove_media_item_from_list(self, list_id, media_item_id):
        self.query_manager.remove_media_item_from_list(list_id, media_item_id)

    def fetch_media_items_by_folder(self, folder_id):
        """Fetch all media items from lists in a specific folder"""
        # Get all lists in this folder
        lists_in_folder = self.query_manager.fetch_lists_direct(folder_id)

        all_media_items = []
        for list_item in lists_in_folder:
            # Get items from each list
            list_items = self.query_manager.fetch_list_items_with_details(list_item['id'])
            all_media_items.extend(list_items)

        return all_media_items

    def get_list_media_count(self, list_id):
        query = """
            SELECT COUNT(*)
            FROM list_items
            WHERE list_id = ?
        """
        self._execute_with_retry(self.cursor.execute, query, (list_id,))
        count = self.cursor.fetchone()[0]
        return count

    def get_folder_media_count(self, folder_id):
        def fetch_all_subfolder_ids(parent_id, visited=None):
            if visited is None:
                visited = set()
            if parent_id in visited:
                return []
            visited.add(parent_id)
            subfolders = [f['id'] for f in self.fetch_folders(parent_id)]
            all_subfolders = subfolders[:]
            for subfolder_id in subfolders:
                all_subfolders.extend(fetch_all_subfolder_ids(subfolder_id, visited))
            return all_subfolders

        folder_ids = [folder_id] + fetch_all_subfolder_ids(folder_id)
        folder_ids_placeholder = ', '.join('?' for _ in folder_ids)

        query = f"""
            SELECT COUNT(*)
            FROM list_items
            WHERE list_id IN (
                SELECT id FROM lists WHERE folder_id IN ({folder_ids_placeholder})
            )
        """
        self._execute_with_retry(self.cursor.execute, query, folder_ids)
        count = self.cursor.fetchone()[0]
        return count

    def insert_original_request(self, description, response_json):
        query = """
            INSERT INTO original_requests (description, response_json)
            VALUES (?, ?)
        """
        self._execute_with_retry(self.cursor.execute, query, (description, response_json))
        self.connection.commit()
        return self.cursor.lastrowid

    def insert_parsed_movie(self, request_id, title, year, director):
        query = """
            INSERT INTO parsed_movies (request_id, title, year, director)
            VALUES (?, ?, ?, ?)
        """
        self._execute_with_retry(self.cursor.execute, query, (request_id, title, year, director))
        self.connection.commit()

    def get_imdb_export_stats(self):
        """Get statistics about IMDB numbers in exports"""
        return self.query_manager.get_imdb_export_stats()

    def insert_imdb_export(self, movies):
        """Insert multiple movies into imdb_exports table"""
        self.query_manager.insert_imdb_export(movies)

    def get_valid_imdb_numbers(self):
        """Get all valid IMDB numbers from exports table"""
        return self.query_manager.get_valid_imdb_numbers()

    def sync_movies(self, movies):
        """Sync movies with the database"""
        self.query_manager.sync_movies(movies)

    def search_remote_movies(self, query, limit=20):
        """Search movies using remote API and return formatted results"""
        from resources.lib.integrations.remote_api.remote_api_client import RemoteAPIClient

        remote_client = RemoteAPIClient()
        if not remote_client.api_key:
            utils.log("Remote API not configured", "WARNING")
            return []

        try:
            results = remote_client.search_movies(query, limit)

            # Convert remote API results to minimal format - only IMDB ID and score
            formatted_results = []
            for movie in results:
                formatted_movie = {
                    'imdbnumber': movie.get('imdb_id', ''),  # ONLY store IMDB ID
                    'score': movie.get('score', 0),          # ONLY store search score
                    'search_score': movie.get('score', 0)    # Alias for compatibility
                }
                formatted_results.append(formatted_movie)

            utils.log(f"Remote API semantic search returned {len(formatted_results)} movies", "DEBUG")

            # Add search history
            self.add_search_history(query, formatted_results)

            return formatted_results

        except Exception as e:
            utils.log(f"Error searching remote movies: {str(e)}", "ERROR")
            return []

    def ensure_search_history_folder(self):
        """Ensures the 'Search History' folder exists and is protected."""
        search_history_folder_name = "Search History"

        # Check if the folder already exists
        existing_folder = self.query_manager.get_folder_by_name(search_history_folder_name)

        if not existing_folder:
            utils.log(f"Creating '{search_history_folder_name}' folder.", "INFO")
            self.query_manager.insert_folder_direct(search_history_folder_name, parent_id=None)

            newly_created_folder = self.query_manager.get_folder_by_name(search_history_folder_name)
            if newly_created_folder:
                utils.log(f"'{search_history_folder_name}' folder created with ID: {newly_created_folder['id']}", "INFO")
            else:
                utils.log(f"Failed to retrieve '{search_history_folder_name}' folder after creation.", "ERROR")
        else:
            utils.log(f"'{search_history_folder_name}' folder already exists.", "INFO")

    def ensure_imported_lists_folder(self):
        """Ensures the 'Imported Lists' folder exists and is protected."""
        imported_lists_folder_name = "Imported Lists"

        # Check if the folder already exists
        existing_folder = self.query_manager.get_folder_by_name(imported_lists_folder_name)

        if not existing_folder:
            utils.log(f"Creating '{imported_lists_folder_name}' folder.", "INFO")
            self.query_manager.insert_folder_direct(imported_lists_folder_name, parent_id=None)

            newly_created_folder = self.query_manager.get_folder_by_name(imported_lists_folder_name)
            if newly_created_folder:
                utils.log(f"'{imported_lists_folder_name}' folder created with ID: {newly_created_folder['id']}", "INFO")
            else:
                utils.log(f"Failed to retrieve '{imported_lists_folder_name}' folder after creation.", "ERROR")
        else:
            utils.log(f"'{imported_lists_folder_name}' folder already exists.", "INFO")

    def add_search_history(self, query, results):
        """Adds the search results to the 'Search History' folder as a new list. Returns the list ID."""
        search_history_folder_id = self.get_folder_id_by_name("Search History")
        if not search_history_folder_id:
            utils.log("Search History folder not found, cannot save search results.", "ERROR")
            return None

        # Format the list name with search query, date only, and count
        timestamp = datetime.now().strftime("%Y-%m-%d")
        base_list_name = f"{query} ({timestamp}) ({len(results)})"

        # Check if a list with this name already exists and create unique name
        counter = 1
        list_name = base_list_name
        while self.get_list_id_by_name(list_name):
            list_name = f"{base_list_name} (#{counter})"
            counter += 1

        utils.log(f"Saving search results for query '{query}' into list '{list_name}'.", "INFO")

        # Create the final list (only one creation needed)
        final_list_data = {
            'name': list_name,
            'folder_id': search_history_folder_id
        }
        utils.log("=== SAVING LIST TITLE TO DATABASE ===", "INFO")
        utils.log(f"List title being saved: '{list_name}'", "INFO")
        utils.log(f"Full list data: {final_list_data}", "DEBUG")
        utils.log("=== END SAVING LIST TITLE ===", "INFO")
        final_list_id = self.insert_data('lists', final_list_data)
        utils.log(f"Created search history list with ID: {final_list_id}", "DEBUG")

        if final_list_id:
            utils.log(f"Successfully created search history list ID {final_list_id}, now adding {len(results)} items", "INFO")
            # Store only IMDB IDs and scores - no library data
            media_items_to_insert = []
            for i, result in enumerate(results):
                imdb_id = result.get('imdbnumber') or result.get('imdb_id', '')
                if not imdb_id:
                    utils.log(f"Skipping result {i+1}: No IMDB ID found", "WARNING")
                    continue

                score_display = result.get('score', result.get('search_score', 0))

                # Look up title and year from imdb_exports table if available
                title_from_exports = ''
                year_from_exports = 0

                try:
                    query = """SELECT title, year FROM imdb_exports WHERE imdb_id = ? ORDER BY id DESC LIMIT 1"""
                    self._execute_with_retry(self.cursor.execute, query, (imdb_id,))
                    export_result = self.cursor.fetchone()
                    if export_result:
                        title_from_exports = export_result[0] or ''
                        year_from_exports = int(export_result[1]) if export_result[1] else 0
                    else:
                        utils.log(f"No export data found for {imdb_id}", "DEBUG")
                except Exception as e:
                    utils.log(f"Error looking up export data for {imdb_id}: {str(e)}", "DEBUG")

                # Store search data with title/year from imdb_exports if available
                plot_text = f"Search result for '{query}' - Score: {score_display}"
                if imdb_id:
                    plot_text += f" - IMDb: {imdb_id}"

                media_item_data = {
                    'kodi_id': 0,  # No Kodi ID for search results
                    'title': title_from_exports if title_from_exports else imdb_id,
                    'year': year_from_exports,    # Year from imdb_exports lookup
                    'rating': 0.0,
                    'plot': plot_text,
                    'tagline': 'Search result from LibraryGenie',
                    'genre': 'Search Result',
                    'director': '',
                    'studio': 'LibraryGenie',
                    'writer': '',
                    'country': '',
                    'cast': '[]',
                    'imdbnumber': imdb_id,  # Store IMDB ID
                    'art': '{}',
                    'poster': '',
                    'fanart': '',
                    'source': 'search',  # Use 'search' source for search results
                    'search_score': score_display,  # Store search score
                    'duration': 0,
                    'votes': 0,
                    'play': f"search_history://{imdb_id}",  # Unique identifier for search results
                    'media_type': 'movie'  # Ensure media_type is set
                }

                media_items_to_insert.append(media_item_data)

            if media_items_to_insert:
                # Insert media items and link them to the new list
                for item_data in media_items_to_insert:
                    try:
                        media_item_id = self.query_manager.insert_media_item(item_data)
                        if media_item_id and media_item_id > 0:
                            self.query_manager.insert_list_item(final_list_id, media_item_id)
                            utils.log(f"Successfully added search result {item_data.get('imdbnumber', 'N/A')} to list", "DEBUG")
                        else:
                            utils.log(f"Failed to insert media item for: {item_data.get('imdbnumber', 'N/A')}", "ERROR")
                    except Exception as e:
                        utils.log(f"Error inserting search result {item_data.get('imdbnumber', 'N/A')}: {str(e)}", "ERROR")
                        # Continue with next item instead of failing entire operation
                utils.log("=== SEARCH HISTORY SAVE COMPLETE ===", "INFO")
                utils.log(f"List Name: '{list_name}'", "INFO")
                utils.log(f"List ID: {final_list_id}", "INFO")
                utils.log(f"Items Saved: {len(media_items_to_insert)}", "INFO")
                utils.log(f"Query: '{query}'", "INFO")
                utils.log("=== END SEARCH HISTORY SAVE ===", "INFO")
                return final_list_id
            else:
                utils.log(f"No valid media items to save for search query '{query}'.", "WARNING")
                # Delete the empty list if no items were added
                self.delete_list(final_list_id)
                utils.log(f"Deleted empty list '{list_name}' as no items were saved.", "INFO")
                return None

        else:
            utils.log(f"Failed to create list '{list_name}' for search history.", "ERROR")
            return None

    def __del__(self):
        if hasattr(self, 'connection') and self.connection:
            self.connection.close()

    def create_list(self, name, folder_id=None):
        """Create a new list"""
        utils.log(f"Creating list '{name}' with folder_id={folder_id}", "DEBUG")
        return self.query_manager.create_list(name, folder_id)

    def ensure_folder_exists(self, name, parent_id=None):
        """Ensure a folder exists, create if it doesn't"""
        utils.log(f"Ensuring folder '{name}' exists with parent_id={parent_id}", "DEBUG")

        # Check if folder already exists
        existing_folder = self.get_folder_id_by_name(name, parent_id)
        if existing_folder:
            utils.log(f"Folder '{name}' already exists with ID: {existing_folder}", "DEBUG")
            return existing_folder

        # Create the folder
        folder_id = self.create_folder(name, parent_id)
        utils.log(f"Created folder '{name}' with ID: {folder_id}", "DEBUG")
        return folder_id

    def get_folder_id_by_name(self, name, parent_id=None):
        """Get folder ID by name and parent"""
        folders = self.fetch_folders(parent_id)
        for folder in folders:
            if folder['name'] == name:
                return folder['id']
        return None

    def delete_list(self, list_id):
        """Delete a list and all its related records"""
        # Check if list is protected (but not search history lists - only the folder is protected)
        if self.is_list_protected(list_id):
            raise ValueError("Cannot delete protected list")

        try:
            self.connection.execute("BEGIN")
            # Delete from list_items
            self._execute_with_retry(self.cursor.execute,
                "DELETE FROM list_items WHERE list_id = ?",
                (list_id,))

            # Finally delete the list itself
            self._execute_with_retry(self.cursor.execute,
                "DELETE FROM lists WHERE id = ?",
                (list_id,))

            self.connection.commit()
            utils.log(f"Successfully deleted list {list_id}", "DEBUG")
        except Exception as e:
            self.connection.rollback()
            utils.log(f"Error deleting list {list_id}: {str(e)}", "ERROR")
            raise e

    def delete_folder(self, folder_id):
        """Delete a folder and all its contents"""
        utils.log(f"Deleting folder {folder_id}", "DEBUG")
        return self.delete_folder_and_contents(folder_id)

    def add_shortlist_items(self, list_id, media_items_data):
        """Add multiple shortlist items to a list in a single transaction (like add_search_history)"""
        try:
            utils.log(f"DATABASE: Adding {len(media_items_data)} shortlist items to list {list_id}", "DEBUG")

            # Use single connection/transaction like search history does
            conn_info = self.query_manager._get_connection()
            try:
                conn_info['connection'].execute("BEGIN")

                for item_data in media_items_data:
                    # Ensure media_type is set
                    if 'media_type' not in item_data:
                        item_data['media_type'] = 'movie'

                    # Insert media item directly in this transaction
                    cursor = conn_info['connection'].cursor()

                    # Filter data for media_items table
                    field_names = [field.split()[0] for field in Config.FIELDS]
                    filtered_data = {}
                    for key in field_names:
                        if key in item_data:
                            value = item_data[key]
                            if value is None:
                                value = ''
                            elif isinstance(value, str) and value.strip() == '':
                                value = ''
                            if value != '' or key in ['kodi_id', 'year', 'rating', 'duration', 'votes']:
                                filtered_data[key] = value

                    # Set defaults for essential fields
                    filtered_data.setdefault('kodi_id', 0)
                    filtered_data.setdefault('year', 0)
                    filtered_data.setdefault('rating', 0.0)
                    filtered_data.setdefault('duration', 0)
                    filtered_data.setdefault('votes', 0)
                    filtered_data.setdefault('title', 'Unknown')
                    filtered_data.setdefault('source', 'shortlist_import')
                    filtered_data.setdefault('media_type', 'movie')

                    # Insert or get media item - handle duplicates gracefully
                    # Check for existing media item using multiple strategies to avoid UNIQUE constraint violation
                    existing_media_query = """
                        SELECT id FROM media_items 
                        WHERE (title = ? AND year = ? AND source = ?) 
                        OR (kodi_id = ? AND kodi_id > 0)
                        OR (play = ? AND play IS NOT NULL AND play != '')
                        LIMIT 1
                    """
                    cursor.execute(existing_media_query, (
                        item_data.get('title', ''), 
                        item_data.get('year', 0), 
                        item_data.get('source', ''),
                        item_data.get('kodi_id', 0),
                        item_data.get('play', '')
                    ))
                    existing_media = cursor.fetchone()

                    if existing_media:
                        media_id = existing_media[0]
                        utils.log(f"DATABASE: Found existing media item for '{item_data.get('title')}' with ID {media_id}", "DEBUG")
                    else:
                        # Insert new media item using INSERT OR IGNORE to handle remaining constraint violations
                        columns = ', '.join(filtered_data.keys())
                        placeholders = ', '.join(['?' for _ in filtered_data])
                        media_query = f'INSERT OR IGNORE INTO media_items ({columns}) VALUES ({placeholders})'

                        cursor.execute(media_query, tuple(filtered_data.values()))
                        media_id = cursor.lastrowid

                        # If INSERT OR IGNORE didn't create a new record, find the existing one
                        if not media_id or media_id == 0:
                            cursor.execute(existing_media_query, (
                                item_data.get('title', ''), 
                                item_data.get('year', 0), 
                                item_data.get('source', ''),
                                item_data.get('kodi_id', 0),
                                item_data.get('play', '')
                            ))
                            existing_media = cursor.fetchone()
                            if existing_media:
                                media_id = existing_media[0]
                                utils.log(f"DATABASE: Found existing media item after INSERT OR IGNORE for '{item_data.get('title')}' with ID {media_id}", "DEBUG")
                        else:
                            utils.log(f"DATABASE: Created new media item for '{item_data.get('title')}' with ID {media_id}", "DEBUG")


                    if media_id and media_id > 0:
                        # Insert list item in same transaction
                        list_query = 'INSERT INTO list_items (list_id, media_item_id) VALUES (?, ?)'
                        cursor.execute(list_query, (list_id, media_id))
                        utils.log(f"DATABASE: Added shortlist item '{item_data.get('title', 'Unknown')}' with media_id {media_id}", "DEBUG")
                    else:
                        utils.log(f"DATABASE WARNING: Failed to get media_id for '{item_data.get('title', 'Unknown')}'", "WARNING")

                conn_info['connection'].commit()
                utils.log(f"DATABASE: Successfully added {len(media_items_data)} shortlist items to list {list_id}", "INFO")
                return True

            except Exception as e:
                conn_info['connection'].rollback()
                utils.log(f"DATABASE ERROR: Transaction failed for shortlist items: {str(e)}", "ERROR")
                raise
            finally:
                self.query_manager._release_connection(conn_info)

        except Exception as e:
            utils.log(f"DATABASE ERROR: Failed to add shortlist items to list {list_id}: {str(e)}", "ERROR")
            import traceback
            utils.log(f"DATABASE ERROR traceback: {traceback.format_exc()}", "ERROR")
            raise

    def add_media_item(self, list_id, media_item_data):
        """Add a media item to a list with proper source-aware handling"""
        try:
            utils.log(f"DATABASE: Attempting to add media item to list {list_id}: {media_item_data.get('title', 'Unknown')} (source: {media_item_data.get('source', 'unknown')})", "DEBUG")

            # For shortlist imports, use the dedicated batch method for single items
            if media_item_data.get('source') == 'shortlist_import':
                return self.add_shortlist_items(list_id, [media_item_data])

            # Ensure media_type is set
            if 'media_type' not in media_item_data:
                media_item_data['media_type'] = 'movie'

            # Insert media item using QueryManager which handles different sources properly
            media_id = self.query_manager.insert_media_item(media_item_data)
            utils.log(f"DATABASE: Created media record with ID: {media_id} for source: {media_item_data.get('source', 'unknown')}", "DEBUG")

            if not media_id or media_id <= 0:
                utils.log("DATABASE: Failed to insert media item, skipping list addition.", "ERROR")
                return False

            # Add to list using QueryManager
            self.query_manager.insert_list_item(list_id, media_id)

            utils.log(f"DATABASE: Successfully added media ID {media_id} to list {list_id}", "DEBUG")
            return True

        except Exception as e:
            utils.log(f"DATABASE ERROR: Failed to add media item '{media_item_data.get('title', 'Unknown')}' to list {list_id}: {str(e)}", "ERROR")
            import traceback
            utils.log(f"DATABASE ERROR traceback: {traceback.format_exc()}", "ERROR")
            raise

    def _add_media_record(self, media_dict):
        """Add media record using QueryManager and return media_id"""
        try:
            # Use the established QueryManager.insert_media_item method which properly handles different sources
            media_id = self.query_manager.insert_media_item(media_dict)
            utils.log(f"DATABASE: Media record created with ID: {media_id} for source: {media_dict.get('source', 'unknown')}", "DEBUG")
            return media_id

        except Exception as e:
            utils.log(f"DATABASE ERROR: Failed to insert media record for '{media_dict.get('title', 'Unknown')}': {str(e)}", "ERROR")
            utils.log(f"DATABASE ERROR: Media dict keys: {list(media_dict.keys())}", "ERROR")
            raise

    def update_data(self, table, data_dict, where_clause):
        """Update data in a table with a where clause"""
        try:
            set_clauses = []
            values = []

            for key, value in data_dict.items():
                set_clauses.append(f"{key} = ?")
                values.append(value)

            set_clause = ", ".join(set_clauses)
            query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"

            self.cursor.execute(query, values)
            self.connection.commit()

            return self.cursor.rowcount > 0
        except Exception as e:
            utils.log(f"Error updating data in {table}: {str(e)}", "ERROR")
            return False

    def move_list_to_folder(self, list_id, target_folder_id):
        """Move a list to a different folder"""
        return self.query_manager.update_list_folder(list_id, target_folder_id)

    def clear_list_items(self, list_id):
        """Remove all items from a list"""
        try:
            result = self.query_manager.execute_write(
                "DELETE FROM list_items WHERE list_id = ?", 
                (list_id,)
            )
            return result['rowcount'] > 0
        except Exception as e:
            utils.log(f"Error clearing list items: {str(e)}", "ERROR")
            return False

    def get_descendant_folder_ids(self, folder_id):
        """Get all descendant folder IDs for a given folder"""
        try:
            descendant_ids = []
            # Get direct children
            subfolders = self.query_manager.get_folders(folder_id)

            for subfolder in subfolders:
                descendant_ids.append(subfolder['id'])
                # Recursively get descendants
                descendant_ids.extend(self.get_descendant_folder_ids(subfolder['id']))

            return descendant_ids
        except Exception as e:
            utils.log(f"Error getting descendant folder IDs: {str(e)}", "ERROR")
            return []

    def get_folder_path(self, folder_id):
        """Get the full path of a folder (e.g., 'Parent/Child/Grandchild')"""
        try:
            path_parts = []
            current_id = folder_id

            while current_id:
                folder = self.query_manager.fetch_folder_by_id(current_id)
                if folder:
                    path_parts.insert(0, folder['name'])  # Insert at beginning
                    current_id = folder['parent_id']  # Move to parent
                else:
                    break

            return " / ".join(path_parts) if path_parts else "Root"
        except Exception as e:
            utils.log(f"Error getting folder path: {str(e)}", "ERROR")
            return "Unknown"

    def create_folder(self, name, parent_id=None):
        """Create a new folder"""
        try:
            folder_id = self.query_manager.create_folder(name, parent_id)
            return {
                'id': folder_id,
                'name': name,
                'parent_id': parent_id
            }
        except Exception as e:
            utils.log(f"Error creating folder: {str(e)}", "ERROR")
            return None