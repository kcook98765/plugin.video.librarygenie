
"""
ListingDAO - Data Access Object for folder and list operations
Extracted from QueryManager to separate concerns while maintaining the same API
"""

class ListingDAO:
    """Data Access Object for folder and list database operations"""
    
    def __init__(self, execute_query_callable, execute_write_callable):
        """
        Initialize DAO with injected query executors
        
        Args:
            execute_query_callable: Function to execute SELECT queries
                                   Signature: execute_query(sql: str, params: tuple, fetch_all: bool) -> List[Dict]
            execute_write_callable: Function to execute INSERT/UPDATE/DELETE
                                   Signature: execute_write(sql: str, params: tuple) -> Dict[str, int]
        """
        self.execute_query = execute_query_callable
        self.execute_write = execute_write_callable

    # =========================
    # FOLDER OPERATIONS
    # =========================

    def get_folders(self, parent_id=None):
        """Get folders by parent ID"""
        if parent_id is None:
            sql = "SELECT * FROM folders WHERE parent_id IS NULL ORDER BY name COLLATE NOCASE"
            params = ()
        else:
            sql = "SELECT * FROM folders WHERE parent_id = ? ORDER BY name COLLATE NOCASE"
            params = (parent_id,)
        return self.execute_query(sql, params, fetch_all=True)

    def fetch_folders_direct(self, parent_id=None):
        """Direct folder fetch without transformation"""
        if parent_id is None:
            sql = "SELECT * FROM folders WHERE parent_id IS NULL ORDER BY name COLLATE NOCASE"
            params = ()
        else:
            sql = "SELECT * FROM folders WHERE parent_id = ? ORDER BY name COLLATE NOCASE"
            params = (parent_id,)
        return self.execute_query(sql, params, fetch_all=True)

    def insert_folder_direct(self, name, parent_id):
        """Direct folder insertion"""
        sql = "INSERT INTO folders (name, parent_id) VALUES (?, ?)"
        params = (name, parent_id)
        result = self.execute_write(sql, params)
        return result['lastrowid']

    def update_folder_name_direct(self, folder_id, new_name):
        """Direct folder name update"""
        sql = "UPDATE folders SET name = ? WHERE id = ?"
        params = (new_name, folder_id)
        result = self.execute_write(sql, params)
        return result['rowcount']

    def get_folder_depth(self, folder_id):
        """Calculate folder depth in hierarchy"""
        if folder_id is None:
            return 0
        
        depth = 0
        current_id = folder_id
        
        while current_id is not None:
            sql = "SELECT parent_id FROM folders WHERE id = ?"
            result = self.execute_query(sql, (current_id,), fetch_all=False)
            if not result:
                break
            current_id = result[0]['parent_id'] if result[0]['parent_id'] is not None else None
            depth += 1
            
            # Prevent infinite loops
            if depth > 50:
                break
                
        return depth

    def get_folder_by_name(self, name, parent_id=None):
        """Get folder by name and parent"""
        if parent_id is None:
            sql = "SELECT * FROM folders WHERE name = ? AND parent_id IS NULL"
            params = (name,)
        else:
            sql = "SELECT * FROM folders WHERE name = ? AND parent_id = ?"
            params = (name, parent_id)
        result = self.execute_query(sql, params, fetch_all=False)
        return result[0] if result else None

    def get_folder_id_by_name(self, name, parent_id=None):
        """Get folder ID by name and parent"""
        folder = self.get_folder_by_name(name, parent_id)
        return folder['id'] if folder else None

    def ensure_search_history_folder(self):
        """Ensure Search History folder exists and return its ID"""
        folder_id = self.get_folder_id_by_name("Search History", None)
        if folder_id:
            return folder_id
        return self.insert_folder_direct("Search History", None)

    def insert_folder(self, name, parent_id):
        """Insert folder (alias for create_folder)"""
        return self.create_folder(name, parent_id)

    def create_folder(self, name, parent_id):
        """Create a new folder"""
        return self.insert_folder_direct(name, parent_id)

    def update_folder_name(self, folder_id, new_name):
        """Update folder name"""
        return self.update_folder_name_direct(folder_id, new_name)

    def get_folder_media_count(self, folder_id):
        """Get total media count for folder (including subfolders and lists)"""
        # Count items in lists directly in this folder
        sql_direct = """
            SELECT COUNT(DISTINCT li.media_item_id) AS cnt
            FROM lists l 
            JOIN list_items li ON l.id = li.list_id 
            WHERE l.folder_id = ?
        """
        direct_result = self.execute_query(sql_direct, (folder_id,), fetch_all=False)
        direct_count = direct_result[0]['cnt'] if direct_result and direct_result[0] else 0

        # Count items in subfolders recursively
        subfolder_count = 0
        subfolders = self.get_folders(folder_id)
        for subfolder in subfolders:
            subfolder_count += self.get_folder_media_count(subfolder['id'])

        return direct_count + subfolder_count

    def fetch_folder_by_id(self, folder_id):
        """Fetch folder by ID"""
        sql = "SELECT * FROM folders WHERE id = ?"
        result = self.execute_query(sql, (folder_id,), fetch_all=False)
        return result[0] if result else None

    def update_folder_parent(self, folder_id, new_parent_id):
        """Update folder parent"""
        sql = "UPDATE folders SET parent_id = ? WHERE id = ?"
        params = (new_parent_id, folder_id)
        result = self.execute_write(sql, params)
        return result['rowcount']

    def delete_folder_and_contents(self, folder_id):
        """Delete folder and all its contents recursively
        
        Note: This method should be called within a transaction managed by QueryManager
        to ensure atomicity of the entire operation.
        """
        # Get all subfolders
        subfolders = self.get_folders(folder_id)
        
        # Recursively delete subfolders
        for subfolder in subfolders:
            self.delete_folder_and_contents(subfolder['id'])
        
        # Delete all lists in this folder
        lists_in_folder = self.get_lists(folder_id)
        for list_item in lists_in_folder:
            self.delete_list_and_contents(list_item['id'])
        
        # Delete the folder itself
        sql = "DELETE FROM folders WHERE id = ?"
        result = self.execute_write(sql, (folder_id,))
        return result['rowcount']

    def fetch_folders_with_item_status(self, parent_id, media_item_id):
        """Fetch folders with status for a media item"""
        if parent_id is None:
            sql = """
                SELECT f.*, 
                       CASE WHEN EXISTS (
                           SELECT 1 FROM lists l 
                           JOIN list_items li ON l.id = li.list_id 
                           WHERE l.folder_id = f.id AND li.media_item_id = ?
                       ) THEN 1 ELSE 0 END as has_item
                FROM folders f 
                WHERE f.parent_id IS NULL 
                ORDER BY f.name COLLATE NOCASE
            """
            params = (media_item_id,)
        else:
            sql = """
                SELECT f.*, 
                       CASE WHEN EXISTS (
                           SELECT 1 FROM lists l 
                           JOIN list_items li ON l.id = li.list_id 
                           WHERE l.folder_id = f.id AND li.media_item_id = ?
                       ) THEN 1 ELSE 0 END as has_item
                FROM folders f 
                WHERE f.parent_id = ? 
                ORDER BY f.name COLLATE NOCASE
            """
            params = (media_item_id, parent_id)
        return self.execute_query(sql, params, fetch_all=True)

    def fetch_all_folders(self):
        """Fetch all folders"""
        sql = "SELECT * FROM folders ORDER BY name COLLATE NOCASE"
        return self.execute_query(sql, (), fetch_all=True)

    # =========================
    # LIST OPERATIONS
    # =========================

    def get_lists(self, folder_id=None):
        """Get lists by folder ID"""
        if folder_id is None:
            sql = "SELECT * FROM lists WHERE folder_id IS NULL ORDER BY name COLLATE NOCASE"
            params = ()
        else:
            sql = "SELECT * FROM lists WHERE folder_id = ? ORDER BY name COLLATE NOCASE"
            params = (folder_id,)
        return self.execute_query(sql, params, fetch_all=True)

    def fetch_lists_direct(self, folder_id=None):
        """Direct list fetch without transformation"""
        return self.get_lists(folder_id)

    def get_list_items(self, list_id):
        """Get items in a list"""
        sql = """
            SELECT mi.* 
            FROM media_items mi 
            JOIN list_items li ON mi.id = li.media_item_id 
            WHERE li.list_id = ?
        """
        return self.execute_query(sql, (list_id,), fetch_all=True)

    def fetch_list_items_with_details(self, list_id):
        """Fetch list items with detailed information including search scores"""
        sql = """
            SELECT 
                mi.*,
                li.id as list_item_id
            FROM media_items mi
            JOIN list_items li ON mi.id = li.media_item_id
            WHERE li.list_id = ?
            ORDER BY 
                CASE WHEN mi.search_score IS NOT NULL THEN mi.search_score ELSE 0 END DESC,
                mi.title COLLATE NOCASE
        """
        return self.execute_query(sql, (list_id,), fetch_all=True)

    def get_list_media_count(self, list_id):
        """Get media count for a list"""
        sql = "SELECT COUNT(*) AS cnt FROM list_items WHERE list_id = ?"
        result = self.execute_query(sql, (list_id,), fetch_all=False)
        return result[0]['cnt'] if result and result[0] else 0

    def fetch_lists_with_item_status(self, folder_id, media_item_id):
        """Fetch lists with status for a media item"""
        if folder_id is None:
            sql = """
                SELECT l.*, 
                       CASE WHEN EXISTS (
                           SELECT 1 FROM list_items li 
                           WHERE li.list_id = l.id AND li.media_item_id = ?
                       ) THEN 1 ELSE 0 END as has_item
                FROM lists l 
                WHERE l.folder_id IS NULL 
                ORDER BY l.name COLLATE NOCASE
            """
            params = (media_item_id,)
        else:
            sql = """
                SELECT l.*, 
                       CASE WHEN EXISTS (
                           SELECT 1 FROM list_items li 
                           WHERE li.list_id = l.id AND li.media_item_id = ?
                       ) THEN 1 ELSE 0 END as has_item
                FROM lists l 
                WHERE l.folder_id = ? 
                ORDER BY l.name COLLATE NOCASE
            """
            params = (media_item_id, folder_id)
        return self.execute_query(sql, params, fetch_all=True)

    def fetch_all_lists_with_item_status(self, media_item_id):
        """Fetch all lists with status for a media item"""
        sql = """
            SELECT l.*, 
                   CASE WHEN EXISTS (
                       SELECT 1 FROM list_items li 
                       WHERE li.list_id = l.id AND li.media_item_id = ?
                   ) THEN 1 ELSE 0 END as has_item
            FROM lists l 
            ORDER BY l.name COLLATE NOCASE
        """
        return self.execute_query(sql, (media_item_id,), fetch_all=True)

    def update_list_folder(self, list_id, folder_id):
        """Update list's folder"""
        sql = "UPDATE lists SET folder_id = ? WHERE id = ?"
        params = (folder_id, list_id)
        result = self.execute_write(sql, params)
        return result['rowcount']

    def get_list_id_by_name(self, name, folder_id=None):
        """Get list ID by name and folder"""
        if folder_id is None:
            sql = "SELECT id FROM lists WHERE name = ? AND folder_id IS NULL"
            params = (name,)
        else:
            sql = "SELECT id FROM lists WHERE name = ? AND folder_id = ?"
            params = (name, folder_id)
        result = self.execute_query(sql, params, fetch_all=False)
        return result[0]['id'] if result else None

    def get_lists_for_item(self, media_item_id):
        """Get all lists containing a media item"""
        sql = """
            SELECT l.* 
            FROM lists l 
            JOIN list_items li ON l.id = li.list_id 
            WHERE li.media_item_id = ?
            ORDER BY l.name COLLATE NOCASE
        """
        return self.execute_query(sql, (media_item_id,), fetch_all=True)

    def get_item_id_by_title_and_list(self, title, list_id):
        """Get media item ID by title within a specific list"""
        sql = """
            SELECT mi.id 
            FROM media_items mi 
            JOIN list_items li ON mi.id = li.media_item_id 
            WHERE mi.title = ? AND li.list_id = ?
        """
        result = self.execute_query(sql, (title, list_id), fetch_all=False)
        return result[0]['id'] if result else None

    def create_list(self, name, folder_id=None):
        """Create a new list"""
        sql = "INSERT INTO lists (name, folder_id) VALUES (?, ?)"
        params = (name, folder_id)
        result = self.execute_write(sql, params)
        return result['lastrowid']

    def get_unique_list_name(self, base_name, folder_id=None):
        """Generate a unique list name in the given folder"""
        # Check if base name is available
        existing = self.get_list_id_by_name(base_name, folder_id)
        if not existing:
            return base_name
        
        # Generate numbered variants
        counter = 1
        while True:
            candidate = f"{base_name} ({counter})"
            existing = self.get_list_id_by_name(candidate, folder_id)
            if not existing:
                return candidate
            counter += 1
            
            # Safety valve
            if counter > 1000:
                import time
                return f"{base_name} ({int(time.time())})"

    def delete_list_and_contents(self, list_id):
        """Delete list and all its contents"""
        # Delete list items first
        sql_items = "DELETE FROM list_items WHERE list_id = ?"
        self.execute_write(sql_items, (list_id,))
        
        # Delete the list itself
        sql_list = "DELETE FROM lists WHERE id = ?"
        result = self.execute_write(sql_list, (list_id,))
        return result['rowcount']

    def fetch_all_lists(self):
        """Fetch all lists"""
        sql = "SELECT * FROM lists ORDER BY name COLLATE NOCASE"
        return self.execute_query(sql, (), fetch_all=True)

    def fetch_list_by_id(self, list_id):
        """Fetch list by ID"""
        sql = "SELECT * FROM lists WHERE id = ?"
        result = self.execute_query(sql, (list_id,), fetch_all=False)
        return result[0] if result else None

    def insert_list_item(self, list_id, media_item_id):
        """Insert item into list"""
        sql = "INSERT INTO list_items (list_id, media_item_id) VALUES (?, ?)"
        params = (list_id, media_item_id)
        result = self.execute_write(sql, params)
        return result['lastrowid']

    def remove_media_item_from_list(self, list_id, media_item_id):
        """Remove media item from list"""
        sql = "DELETE FROM list_items WHERE list_id = ? AND media_item_id = ?"
        params = (list_id, media_item_id)
        result = self.execute_write(sql, params)
        return result['rowcount']

    def get_list_item_by_media_id(self, list_id, media_item_id):
        """Get list item by list_id and media_item_id"""
        sql = "SELECT * FROM list_items WHERE list_id = ? AND media_item_id = ?"
        params = (list_id, media_item_id)
        result = self.execute_query(sql, params, fetch_all=False)
        return result[0] if result else None

    def upsert_heavy_meta(self, movieid, imdbnumber, cast_json, ratings_json, showlink_json, stream_json, uniqueid_json, tags_json):
        """Upsert heavy metadata for a movie with retry logic"""
        import time
        
        # First try to update existing record
        update_sql = """
            UPDATE movie_heavy_meta SET
                imdbnumber = ?,
                cast_json = ?,
                ratings_json = ?,
                showlink_json = ?,
                stream_json = ?,
                uniqueid_json = ?,
                tags_json = ?,
                updated_at = ?
            WHERE kodi_movieid = ?
        """
        update_params = (imdbnumber, cast_json, ratings_json, showlink_json, 
                        stream_json, uniqueid_json, tags_json, int(time.time()), movieid)
        
        # Retry logic for database operations
        max_retries = 5
        for attempt in range(max_retries):
            try:
                result = self.execute_write(update_sql, update_params)
                if result['rowcount'] > 0:
                    return movieid  # Successfully updated
                
                # No rows updated, try insert
                insert_sql = """
                    INSERT OR IGNORE INTO movie_heavy_meta
                        (kodi_movieid, imdbnumber, cast_json, ratings_json, showlink_json,
                         stream_json, uniqueid_json, tags_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                insert_params = (movieid, imdbnumber, cast_json, ratings_json, showlink_json, 
                               stream_json, uniqueid_json, tags_json, int(time.time()))
                result = self.execute_write(insert_sql, insert_params)
                return result['lastrowid'] or movieid
                
            except Exception as e:
                if 'database is locked' in str(e) and attempt < max_retries - 1:
                    import time
                    wait_time = 0.1 * (2 ** attempt)  # Exponential backoff
                    time.sleep(wait_time)
                    continue
                else:
                    # Re-raise the exception if it's not a lock or we've exhausted retries
                    raise
        
        # If we get here, all retries failed
        raise Exception(f"Failed to upsert heavy metadata after {max_retries} attempts")

    def get_heavy_meta_by_movieids(self, movieids):
        """Get heavy metadata for multiple movie IDs"""
        if not movieids:
            return {}
        
        placeholders = ','.join(['?'] * len(movieids))
        sql = f"""
            SELECT kodi_movieid, cast_json, ratings_json, showlink_json, 
                   stream_json, uniqueid_json, tags_json
            FROM movie_heavy_meta 
            WHERE kodi_movieid IN ({placeholders})
        """
        
        rows = self.execute_query(sql, movieids, fetch_all=True)
        
        heavy_by_id = {}
        for row in rows:
            import json
            movieid = row['kodi_movieid']
            heavy_by_id[movieid] = {
                'cast': json.loads(row['cast_json']) if row['cast_json'] else [],
                'ratings': json.loads(row['ratings_json']) if row['ratings_json'] else {},
                'showlink': json.loads(row['showlink_json']) if row['showlink_json'] else [],
                'streamdetails': json.loads(row['stream_json']) if row['stream_json'] else {},
                'uniqueid': json.loads(row['uniqueid_json']) if row['uniqueid_json'] else {},
                'tag': json.loads(row['tags_json']) if row['tags_json'] else []
            }
        
        return heavy_by_id

    
