import os
import sqlite3
import json
import time
from resources.lib import utils
from resources.lib.config_manager import Config

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.config = Config()  # Instantiate Config to access FIELDS
        self._connect()

    def _connect(self):
        try:
            # Ensure the directory exists
            db_dir = os.path.dirname(self.db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir)

            self.connection = sqlite3.connect(self.db_path, timeout=30.0)
            self.cursor = self.connection.cursor()
            self.cursor.execute('PRAGMA foreign_keys = ON')
        except Exception as e:
            utils.log(f"Database connection error: {str(e)}", "ERROR")
            raise

    def _execute_with_retry(self, func, *args, **kwargs):
        retries = 5
        for i in range(retries):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if 'database is locked' in str(e):
                    utils.log(f"Database is locked, retrying... ({i+1}/{retries})", "WARNING")
                    time.sleep(0.5)  # Wait for 0.5 seconds before retrying
                else:
                    raise

    def setup_database(self):
        fields_str = ', '.join(self.config.FIELDS)
        table_creations = [
            '''
                CREATE TABLE IF NOT EXISTS imdb_exports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kodi_id INTEGER,
                    imdb_id TEXT,
                    title TEXT,
                    year INTEGER,
                    filename TEXT,
                    path TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            '''
                CREATE TABLE IF NOT EXISTS folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    parent_id INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            '''
                CREATE TABLE IF NOT EXISTS lists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder_id INTEGER,
                    name TEXT UNIQUE,
                    query TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            f'''
                CREATE TABLE IF NOT EXISTS media_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    {fields_str},
                    UNIQUE (kodi_id, play)
                )
            ''',
            '''
                CREATE TABLE IF NOT EXISTS list_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_id INTEGER,
                    media_item_id INTEGER,
                    flagged INTEGER DEFAULT 0,
                    FOREIGN KEY (list_id) REFERENCES lists (id),
                    FOREIGN KEY (media_item_id) REFERENCES media_items (id)
                )
            ''',
            '''
                CREATE TABLE IF NOT EXISTS whitelist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_id INTEGER,
                    title TEXT,
                    FOREIGN KEY (list_id) REFERENCES lists (id)
                )
            ''',
            '''
                CREATE TABLE IF NOT EXISTS blacklist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_id INTEGER,
                    title TEXT,
                    FOREIGN KEY (list_id) REFERENCES lists (id)
                )
            ''',
            '''
                CREATE TABLE IF NOT EXISTS genie_lists (
                    list_id INTEGER PRIMARY KEY,
                    description TEXT,
                    rpc TEXT,
                    FOREIGN KEY (list_id) REFERENCES lists (id)
                )
            ''',
            '''
                CREATE TABLE IF NOT EXISTS original_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    description TEXT,
                    response_json TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            '''
                CREATE TABLE IF NOT EXISTS parsed_movies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER,
                    title TEXT,
                    year INTEGER,
                    director TEXT,
                    FOREIGN KEY (request_id) REFERENCES original_requests (id)
                )
            '''
        ]

        for create_statement in table_creations:
            self._execute_with_retry(self.cursor.execute, create_statement)
        self.connection.commit()

    def fetch_folders(self, parent_id=None):
        query = """
            SELECT 
                id,
                name,
                parent_id
            FROM folders
            WHERE parent_id IS ?
            ORDER BY name COLLATE NOCASE
        """
        utils.log(f"Executing SQL: {query}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, (parent_id,))
        rows = self.cursor.fetchall()
        return [{'id': row[0], 'name': row[1], 'parent_id': row[2]} for row in rows]

    def fetch_lists(self, folder_id=None):
        query = """
            SELECT 
                id,
                name,
                folder_id
            FROM lists
            WHERE folder_id IS ?
            ORDER BY name COLLATE NOCASE
        """
        utils.log(f"Executing SQL: {query}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, (folder_id,))
        rows = self.cursor.fetchall()
        return [{'id': row[0], 'name': row[1], 'folder_id': row[2]} for row in rows]

    def get_folder_depth(self, folder_id):
        depth = 0
        current_id = folder_id
        while current_id is not None:
            query = "SELECT parent_id FROM folders WHERE id = ?"
            self._execute_with_retry(self.cursor.execute, query, (current_id,))
            result = self.cursor.fetchone()
            if result is None:
                break
            current_id = result[0]
            depth += 1
        return depth

    def insert_folder(self, name, parent_id=None):
        if parent_id is not None:
            current_depth = self.get_folder_depth(parent_id)
            max_depth = self.config.max_folder_depth - 1  # -1 because we're adding a new level
            if current_depth >= max_depth:
                raise ValueError(f"Maximum folder depth of {self.config.max_folder_depth} exceeded")

        query = """
            INSERT INTO folders (name, parent_id)
            VALUES (?, ?)
        """
        utils.log(f"Executing SQL: {query} with name={name}, parent_id={parent_id}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, (name, parent_id))
        self.connection.commit()

    def update_list_folder(self, list_id, folder_id):
        query = """
            UPDATE lists
            SET folder_id = ?
            WHERE id = ?
        """
        utils.log(f"Executing SQL: {query} with list_id={list_id}, folder_id={folder_id}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, (folder_id, list_id))
        self.connection.commit()

    def fetch_lists_with_item_status(self, item_id):
        query = """
            SELECT 
                lists.id, 
                lists.name,
                CASE 
                    WHEN list_items.media_item_id IS NOT NULL THEN 1
                    ELSE 0
                END AS is_member
            FROM lists
            LEFT JOIN list_items ON lists.id = list_items.list_id AND list_items.media_item_id IN (
                SELECT id FROM media_items WHERE kodi_id = ?
            )
            ORDER BY lists.name COLLATE NOCASE
        """
        utils.log(f"Executing SQL: {query} with item_id={item_id}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, (item_id,))
        rows = self.cursor.fetchall()
        return [{'id': row[0], 'name': row[1], 'is_member': row[2]} for row in rows]

    def fetch_all_lists_with_item_status(self, item_id):
        query = """
            SELECT 
                lists.id, 
                lists.name,
                lists.folder_id,
                CASE 
                    WHEN list_items.media_item_id IS NOT NULL THEN 1
                    ELSE 0
                END AS is_member
            FROM lists
            LEFT JOIN list_items ON lists.id = list_items.list_id AND list_items.media_item_id IN (
                SELECT id FROM media_items WHERE kodi_id = ?
            )
            ORDER BY lists.folder_id, lists.name COLLATE NOCASE
        """
        utils.log(f"Executing SQL: {query} with item_id={item_id}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, (item_id,))
        rows = self.cursor.fetchall()
        return [{'id': row[0], 'name': row[1], 'folder_id': row[2], 'is_member': row[3]} for row in rows]

    def fetch_list_items(self, list_id):
        fields_str = ', '.join([f'"{field.split()[0]}"' for field in self.config.FIELDS])
        query = f"""
            SELECT media_items.id, {fields_str}
            FROM list_items
            JOIN media_items ON list_items.media_item_id = media_items.id
            WHERE list_items.list_id = ?
        """
        utils.log(f"Executing SQL: {query} with list_id={list_id}", "DEBUG")
        try:
            self._execute_with_retry(self.cursor.execute, query, (list_id,))
            rows = self.cursor.fetchall()
            utils.log(f"Fetched rows: {rows}", "DEBUG")  # Log the fetched rows

            items = []
            for row in rows:
                item = {
                    'id': row[0],
                    'title': row[self.config.FIELDS.index('title TEXT') + 1],
                    'info': {field.split()[0]: (json.loads(row[idx + 1]) if field.split()[0] == 'cast' and row[idx + 1] else row[idx + 1]) for idx, field in enumerate(self.config.FIELDS) if field.split()[0] != 'title'}
                }
                utils.log(f"Collected path: {item['info'].get('path')}", "DEBUG")  # Log the path here
                items.append(item)
            return items
        except sqlite3.OperationalError as e:
            utils.log(f"SQL error: {e}", "ERROR")
            return []

    def truncate_data(self, data, max_length=10):
        truncated_data = {}
        for key, value in data.items():
            str_value = str(value)
            if len(str_value) > max_length:
                truncated_data[key] = str_value[:max_length] + "..."
            else:
                truncated_data[key] = str_value
        return truncated_data

    def insert_data(self, table, data):
        # Convert the cast list to a JSON string if it exists
        if 'cast' in data and isinstance(data['cast'], list):
            data['cast'] = json.dumps(data['cast'])

        truncated_data = self.truncate_data(data)
        utils.log(f"Final data for insertion: {truncated_data}", "DEBUG")  # Additional logging

        if table == 'list_items':
            # Extract field names from self.config.FIELDS
            field_names = [field.split()[0] for field in self.config.FIELDS]
            utils.log(f"Field names for media data: {field_names}", "DEBUG")  # Log field names

            utils.log(f"Keys in data dictionary: {list(data.keys())}", "DEBUG")  # Log keys in data

            # Insert or ignore into media_items
            media_data = {key: data[key] for key in data if key in field_names}

            truncated_data = self.truncate_data(media_data)
            utils.log(f"Media data for insertion after comprehension: {truncated_data}", "DEBUG")  # Log media_data

            # Insert or ignore into media_items
            columns = ', '.join(media_data.keys())
            placeholders = ', '.join('?' for _ in media_data)
            query = f'INSERT OR IGNORE INTO media_items ({columns}) VALUES ({placeholders})'
            utils.log(f"Executing SQL: {query} with data={media_data}", "DEBUG")
            self._execute_with_retry(self.cursor.execute, query, tuple(media_data.values()))
            self.connection.commit()

            # Get the media_item_id
            query = """
                SELECT id
                FROM media_items
                WHERE kodi_id = ? AND play = ?
            """
            utils.log(f"Executing SQL: {query} with kodi_id={media_data.get('kodi_id')} and play={media_data.get('play')}", "DEBUG")
            self._execute_with_retry(self.cursor.execute, query, (media_data['kodi_id'], media_data['play']))
            media_item_id = self.cursor.fetchone()
            utils.log(f"Fetched media_item_id: {media_item_id}", "DEBUG")

            if media_item_id:
                media_item_id = media_item_id[0]
                # Insert into list_items
                list_data = {
                    'list_id': data['list_id'],
                    'media_item_id': media_item_id
                }
                columns = ', '.join(list_data.keys())
                placeholders = ', '.join('?' for _ in list_data)
                query = f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'
                utils.log(f"Executing SQL: {query} with data={list_data}", "DEBUG")
                self._execute_with_retry(self.cursor.execute, query, tuple(list_data.values()))
            else:
                utils.log("No media_item_id found, insertion skipped", "ERROR")
        else:
            columns = ', '.join(data.keys())
            placeholders = ', '.join('?' for _ in data)
            query = f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'
            utils.log(f"Executing SQL: {query} with data={data}", "DEBUG")
            self._execute_with_retry(self.cursor.execute, query, tuple(data.values()))

        self.connection.commit()
        utils.log(f"Data inserted into {table} successfully", "DEBUG")  # Log after insertion

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

    def update_data(self, table, data, condition):
        columns = ', '.join(f'{col} = ?' for col in data)
        query = f'UPDATE {table} SET {columns} WHERE {condition}'
        utils.log(f"Executing SQL: {query} with data={data}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, tuple(data.values()))
        self.connection.commit()

    def delete_data(self, table, condition):
        query = f'DELETE FROM {table} WHERE {condition}'
        utils.log(f"Executing SQL: {query}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query)
        self.connection.commit()

    def get_list_id_by_name(self, list_name):
        query = "SELECT id FROM lists WHERE name = ?"
        utils.log(f"Executing SQL: {query} with list_name={list_name}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, (list_name,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def get_lists_for_item(self, item_id):
        query = """
            SELECT lists.name
            FROM list_items
            JOIN lists ON list_items.list_id = lists.id
            JOIN media_items ON list_items.media_item_id = media_items.id
            WHERE media_items.kodi_id = ?
        """
        utils.log(f"Executing SQL: {query} with item_id={item_id}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, (item_id,))
        rows = self.cursor.fetchall()
        return [row[0] for row in rows]

    def fetch_all_folders(self):
        query = """
            SELECT 
                id,
                name,
                parent_id
            FROM folders
            ORDER BY parent_id, name COLLATE NOCASE
        """
        utils.log(f"Executing SQL: {query}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query)
        rows = self.cursor.fetchall()
        return [{'id': row[0], 'name': row[1], 'parent_id': row[2]} for row in rows]

    def fetch_all_lists(self):
        query = """
            SELECT 
                id,
                name,
                folder_id
            FROM lists
            ORDER BY folder_id, name COLLATE NOCASE
        """
        utils.log(f"Executing SQL: {query}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query)
        rows = self.cursor.fetchall()
        return [{'id': row[0], 'name': row[1], 'folder_id': row[2]} for row in rows]

    def get_item_id_by_title_and_list(self, list_id, title):
        query = """
            SELECT list_items.id
            FROM list_items
            JOIN media_items ON list_items.media_item_id = media_items.id
            WHERE list_items.list_id = ? AND media_items.title = ?
        """
        utils.log(f"Executing SQL: {query} with list_id={list_id}, title={title}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, (list_id, title))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def get_folder_id_by_name(self, folder_name):
        query = "SELECT id FROM folders WHERE name = ?"
        utils.log(f"Executing SQL: {query} with folder_name={folder_name}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, (folder_name,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def update_folder_name(self, folder_id, new_name):
        query = "UPDATE folders SET name = ? WHERE id = ?"
        utils.log(f"Executing SQL: {query} with folder_id={folder_id}, new_name={new_name}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, (new_name, folder_id))
        self.connection.commit()

    def update_folder_parent(self, folder_id, new_parent_id):
        if new_parent_id is not None:
            # Get the depth of the subtree being moved
            subtree_depth = self._get_subtree_depth(folder_id)

            # Get the depth at the new location
            target_depth = self.get_folder_depth(new_parent_id)

            # Calculate total depth after move
            total_depth = target_depth + subtree_depth + 1

            if total_depth > self.config.max_folder_depth:
                raise ValueError(f"Moving folder would exceed maximum depth of {self.config.max_folder_depth}")

            # Check if move would create a cycle
            temp_parent = new_parent_id
            while temp_parent is not None:
                if temp_parent == folder_id:
                    raise ValueError("Cannot move folder: would create a cycle")
                query = "SELECT parent_id FROM folders WHERE id = ?"
                self._execute_with_retry(self.cursor.execute, query, (temp_parent,))
                result = self.cursor.fetchone()
                temp_parent = result[0] if result else None

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

        query = "UPDATE folders SET parent_id = ? WHERE id = ?"
        utils.log(f"Executing SQL: {query} with folder_id={folder_id}, new_parent_id={new_parent_id}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, (new_parent_id, folder_id))
        self.connection.commit()

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

            # Delete lists in all nested folders
            placeholders = ','.join('?' * len(folder_ids))
            self._execute_with_retry(self.cursor.execute, 
                f"DELETE FROM lists WHERE folder_id IN ({placeholders})", 
                folder_ids)

            # Delete all nested folders
            self._execute_with_retry(self.cursor.execute, 
                f"DELETE FROM folders WHERE id IN ({placeholders})", 
                folder_ids)

            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            raise e

    def fetch_folder_by_id(self, folder_id):
        query = "SELECT id, name, parent_id FROM folders WHERE id = ?"
        self._execute_with_retry(self.cursor.execute, query, (folder_id,))
        row = self.cursor.fetchone()
        if row:
            return {'id': row[0], 'name': row[1], 'parent_id': row[2]}
        return None

    def fetch_list_by_id(self, list_id):
        query = "SELECT id, name, folder_id FROM lists WHERE id = ?"
        self._execute_with_retry(self.cursor.execute, query, (list_id,))
        row = self.cursor.fetchone()
        if row:
            return {'id': row[0], 'name': row[1], 'folder_id': row[2]}
        return None

    def fetch_folders_with_item_status(self, item_id):
        query = """
            SELECT 
                folders.id,
                folders.name,
                folders.parent_id,
                CASE 
                    WHEN list_items.media_item_id IS NOT NULL THEN 1
                    ELSE 0
                END AS is_member
            FROM folders
            LEFT JOIN lists ON folders.id = lists.folder_id
            LEFT JOIN list_items ON lists.id = list_items.list_id AND list_items.media_item_id IN (
                SELECT id FROM media_items WHERE kodi_id = ?
            )
            ORDER BY folders.name COLLATE NOCASE
        """
        utils.log(f"Executing SQL: {query} with item_id={item_id}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, (item_id,))
        rows = self.cursor.fetchall()
        return [{'id': row[0], 'name': row[1], 'parent_id': row[2], 'is_member': row[3]} for row in rows]

    def remove_media_item_from_list(self, list_id, media_item_id):
        query = """
            DELETE FROM list_items
            WHERE list_id = ? AND media_item_id = ?
        """
        utils.log(f"Executing SQL: {query} with list_id={list_id}, media_item_id={media_item_id}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, (list_id, media_item_id))
        self.connection.commit()
        utils.log(f"Media item ID {media_item_id} removed from list ID {list_id}", "DEBUG")

    def get_genie_list(self, list_id):
        query = "SELECT description, rpc FROM genie_lists WHERE list_id = ?"
        self._execute_with_retry(self.cursor.execute, query, (list_id,))
        row = self.cursor.fetchone()
        if row:
            return {'description': row[0], 'rpc': row[1]}
        return None

    def update_genie_list(self, list_id, description, rpc):
        query = "UPDATE genie_lists SET description = ?, rpc = ? WHERE list_id = ?"
        try:
            self._execute_with_retry(self.cursor.execute, query, (description, json.dumps(rpc), list_id))
            self.connection.commit()
            utils.log(f"Updated genie_list for list_id={list_id}", "DEBUG")
        except sqlite3.OperationalError as e:
            utils.log(f"SQL error in update_genie_list: {e}", "ERROR")
            # Optional: Retry logic or additional error handling here

    def insert_genie_list(self, list_id, description, rpc):
        query = "INSERT INTO genie_lists (list_id, description, rpc) VALUES (?, ?, ?)"
        try:
            self._execute_with_retry(self.cursor.execute, query, (list_id, description, json.dumps(rpc)))
            self.connection.commit()
            utils.log(f"Inserted genie_list for list_id={list_id}", "DEBUG")
        except sqlite3.OperationalError as e:
            utils.log(f"SQL error in insert_genie_list: {e}", "ERROR")
            # Optional: Retry logic or additional error handling here

    def delete_genie_list(self, list_id):
        query = "DELETE FROM genie_lists WHERE list_id = ?"
        self._execute_with_retry(self.cursor.execute, query, (list_id,))
        self.connection.commit()

    def remove_genielist_entries(self, list_id):
        query = """
            DELETE FROM list_items
            WHERE list_id = ? AND media_item_id IN (
                SELECT id FROM media_items WHERE source = 'genielist'
            )
        """
        utils.log(f"Removing GenieList entries for list_id={list_id}", "DEBUG")
        self._execute_with_retry(self.cursor.execute, query, (list_id,))
        self.connection.commit()

    def insert_genielist_entries(self, list_id, media_items):
        for item in media_items:
            fields_keys = [field.split()[0] for field in Config.FIELDS]
            data = {field: item.get(field) for field in fields_keys}

            # Ensure data types are correct
            data['kodi_id'] = int(data['kodi_id']) if data['kodi_id'] and data['kodi_id'].isdigit() else 0
            data['duration'] = int(data['duration']) if data['duration'] and data['duration'].isdigit() else 0
            data['rating'] = float(data['rating']) if data['rating'] else 0.0
            data['votes'] = int(data['votes']) if data['votes'] else 0
            data['year'] = int(data['year']) if data['year'] else 0
            data['source'] = 'genielist'
            data['country'] = ','.join(data['country']) if isinstance(data['country'], list) else data['country']
            data['director'] = ','.join(data['director']) if isinstance(data['director'], list) else data['director']
            data['genre'] = ','.join(data['genre']) if isinstance(data['genre'], list) else data['genre']
            data['studio'] = ','.join(data['studio']) if isinstance(data['studio'], list) else data['studio']
            data['writer'] = ','.join(data['writer']) if isinstance(data['writer'], list) else data['writer']

            if 'cast' in data and isinstance(data['cast'], list):
                data['cast'] = json.dumps(data['cast'])

            self.insert_data('media_items', data)
            media_item_id = self.cursor.lastrowid
            list_item_data = {'list_id': list_id, 'media_item_id': media_item_id}
            self.insert_data('list_items', list_item_data)

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
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN imdb_id IS NOT NULL AND imdb_id != '' AND imdb_id LIKE 'tt%' THEN 1 ELSE 0 END) as valid_imdb
            FROM imdb_exports
        """
        self._execute_with_retry(self.cursor.execute, query)
        result = self.cursor.fetchone()
        return {
            'total': result[0],
            'valid_imdb': result[1],
            'percentage': (result[1] / result[0] * 100) if result[0] > 0 else 0
        }

    def insert_imdb_export(self, movies):
        """Insert multiple movies into imdb_exports table"""
        query = """
            INSERT INTO imdb_exports 
            (kodi_id, imdb_id, title, year, filename, path)
            VALUES (?, ?, ?, ?, ?, ?)
        """        for movie in movies:
            file_path = movie.get('file', '')
            filename = file_path.split('/')[-1] if file_path else ''
            path = '/'.join(file_path.split('/')[:-1]) if file_path else ''

            self._execute_with_retry(
                self.cursor.execute, 
                query,
                (
                    movie.get('movieid'), 
                    movie.get('imdbnumber'),
                    movie.get('title'),
                    movie.get('year'),
                    filename,
                    path
                )
            )
        self.connection.commit()


    def get_valid_imdb_numbers(self):
        """Get all valid IMDB numbers from exports table"""
        query = """
            SELECT imdb_id
            FROM imdb_exports
            WHERE imdb_id IS NOT NULL 
            AND imdb_id != '' 
            AND imdb_id LIKE 'tt%'
            ORDER BY imdb_id
        """
        self._execute_with_retry(self.cursor.execute, query)
        rows = self.cursor.fetchall()
        return [row[0] for row in rows]

    def __del__(self):
        if getattr(self, 'connection', None):
            self.connection.close()