#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - ShortList Addon Importer
Imports lists from the ShortList addon into LibraryGenie
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from ..data.connection_manager import get_connection_manager
from ..data import QueryManager
from ..data.list_library_manager import get_list_library_manager
from ..kodi.json_rpc_helper import get_json_rpc_helper
from ..utils.logger import get_logger


class ShortListImporter:
    """Imports lists from ShortList addon"""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.conn_manager = get_connection_manager()
        self.query_manager = QueryManager()
        self.list_library_manager = get_list_library_manager()
        self.json_rpc = get_json_rpc_helper()

    def is_shortlist_installed(self) -> bool:
        """Check if ShortList addon is installed and enabled"""
        try:
            response = self.json_rpc.execute_request("Addons.GetAddonDetails", {
                "addonid": "plugin.program.shortlist",
                "properties": ["enabled"]
            })

            if not response.success:
                return False

            is_enabled = (response.data or {}).get("addon", {}).get("enabled", False)
            self.logger.info(f"ShortList addon enabled: {is_enabled}")
            return is_enabled

        except Exception as e:
            self.logger.debug(f"ShortList addon not found: {e}")
            return False

    def get_shortlist_directory(self, url: str, start: int = 0, end: int = 200) -> List[Dict]:
        """Get directory contents from ShortList addon"""
        try:
            # Use comprehensive properties for file listings
            properties = [
                "title", "file", "thumbnail", "fanart", "art", "plot", "plotoutline",
                "genre", "director", "cast", "year", "rating", "duration", "runtime",
                "dateadded", "resume", "streamdetails", "trailer", "originaltitle",
                "writer", "studio", "mpaa", "country", "imdbnumber"
            ]

            response = self.json_rpc.execute_request("Files.GetDirectory", {
                "directory": url,
                "media": "files",
                "properties": properties,
                "limits": {"start": start, "end": end}
            })

            if not response.success:
                self.logger.error(f"Failed to get directory {url}: {response.error.message if response.error else 'Unknown error'}")
                return []

            files = (response.data or {}).get("files", [])
            total = (response.data or {}).get("limits", {}).get("total", len(files))

            # Paginate if needed
            while len(files) < total:
                start = len(files)
                chunk_response = self.json_rpc.execute_request("Files.GetDirectory", {
                    "directory": url,
                    "media": "files",
                    "properties": properties,
                    "limits": {"start": start, "end": start + 200}
                })

                if not chunk_response.success:
                    break

                chunk = (chunk_response.data or {}).get("files", [])
                if not chunk:
                    break
                files.extend(chunk)

            return files

        except Exception as e:
            self.logger.error(f"Error getting ShortList directory {url}: {e}")
            return []

    def scrape_shortlist_data(self) -> List[Dict]:
        """Scrape all lists from ShortList addon"""
        base_url = "plugin://plugin.program.shortlist/"
        lists = []

        try:
            # Get top-level directories (lists)
            entries = self.get_shortlist_directory(base_url)
            self.logger.info(f"Found {len(entries)} top-level entries in ShortList")

            for entry in entries:
                if entry.get("filetype") != "directory":
                    continue

                list_name = entry.get("label") or entry.get("title") or "Unnamed List"
                list_url = entry.get("file")

                if not list_url:
                    self.logger.warning(f"Skipping list '{list_name}' - no valid URL found")
                    continue

                self.logger.info(f"Processing ShortList: {list_name}")

                # Get items in this list
                items_raw = self.get_shortlist_directory(list_url)
                items = []

                for item in items_raw:
                    if item.get("filetype") == "directory":
                        continue

                    # Extract item data
                    item_data = {
                        "title": item.get("title") or item.get("label"),
                        "file": item.get("file"),
                        "year": item.get("year"),
                        "rating": item.get("rating"),
                        "duration": item.get("duration") or item.get("runtime"),
                        "plot": item.get("plot") or item.get("plotoutline"),
                        "genre": item.get("genre"),
                        "director": item.get("director"),
                        "cast": item.get("cast"),
                        "studio": item.get("studio"),
                        "mpaa": item.get("mpaa"),
                        "imdbnumber": item.get("imdbnumber"),
                        "art": item.get("art", {}),
                        "thumbnail": item.get("thumbnail"),
                        "fanart": item.get("fanart"),
                        "position": len(items)
                    }

                    items.append(item_data)

                if items:
                    lists.append({
                        "name": list_name,
                        "url": list_url,
                        "items": items
                    })
                    self.logger.info(f"Added list '{list_name}' with {len(items)} items")

        except Exception as e:
            self.logger.error(f"Error scraping ShortList data: {e}")
            raise

        self.logger.info(f"ShortList scrape complete: {len(lists)} lists found")
        return lists

    def match_movie_to_library(self, item_data: Dict) -> Optional[int]:
        """Match ShortList item to library movie using media_items table"""
        try:
            title = item_data.get("title")
            year = item_data.get("year")
            imdbnumber = item_data.get("imdbnumber")

            if not title:
                return None

            # Method 1: Match by IMDb ID if available
            if imdbnumber:
                result = self.conn_manager.execute_single(
                    "SELECT id FROM media_items WHERE imdbnumber = ? AND is_removed = 0",
                    [imdbnumber]
                )
                if result:
                    movie_id = result[0] if hasattr(result, '__getitem__') else result.get('id')
                    return movie_id

            # Method 2: Match by title and year
            conditions = ["title = ?", "is_removed = 0"]
            params = [title]

            if year:
                conditions.append("year = ?")
                params.append(year)

            query = f"SELECT id FROM media_items WHERE {' AND '.join(conditions)}"
            result = self.conn_manager.execute_single(query, params)

            if result:
                movie_id = result[0] if hasattr(result, '__getitem__') else result.get('id')
                return movie_id

            # Method 3: Fuzzy title match without year
            result = self.conn_manager.execute_single(
                "SELECT id FROM media_items WHERE title = ? AND is_removed = 0",
                [title]
            )

            if result:
                movie_id = result[0] if hasattr(result, '__getitem__') else result.get('id')
                return movie_id

            return None

        except Exception as e:
            self.logger.error(f"Error matching movie to library: {e}")
            return None

    def remove_existing_shortlist_import(self) -> bool:
        """Remove existing 'ShortList Import' folder and all its contents (replace functionality)"""
        try:
            self.logger.info("Starting remove of existing ShortList Import folder and contents")
            
            # Find the ShortList Import folder
            folder_info = self.conn_manager.execute_single(
                "SELECT id, name FROM folders WHERE name = ? AND parent_id IS NULL", 
                ["ShortList Import"]
            )
            
            if not folder_info:
                self.logger.info("No existing ShortList Import folder found - nothing to remove")
                return True
                
            folder_id = folder_info[0] if hasattr(folder_info, '__getitem__') else folder_info.get('id')
            self.logger.info(f"Found existing ShortList Import folder (ID: {folder_id}) - removing all contents")
            
            with self.conn_manager.transaction() as conn:
                # Use recursive CTE to find all descendant folders (including the root folder)
                # Step 1: Delete all list_items for lists in the entire folder hierarchy
                conn.execute("""
                    WITH RECURSIVE folder_tree(id) AS (
                        SELECT id FROM folders WHERE id = ?
                        UNION ALL
                        SELECT f.id FROM folders f 
                        JOIN folder_tree ft ON f.parent_id = ft.id
                    )
                    DELETE FROM list_items 
                    WHERE list_id IN (
                        SELECT l.id FROM lists l 
                        WHERE l.folder_id IN (SELECT id FROM folder_tree)
                    )
                """, [folder_id])
                
                # Step 2: Delete all lists in the entire folder hierarchy
                conn.execute("""
                    WITH RECURSIVE folder_tree(id) AS (
                        SELECT id FROM folders WHERE id = ?
                        UNION ALL
                        SELECT f.id FROM folders f 
                        JOIN folder_tree ft ON f.parent_id = ft.id
                    )
                    DELETE FROM lists 
                    WHERE folder_id IN (SELECT id FROM folder_tree)
                """, [folder_id])
                
                # Step 3: Delete all folders in the hierarchy using bottom-up approach
                # First, count the total number of folders in the subtree for dynamic iteration limit
                subtree_count = conn.execute("""
                    WITH RECURSIVE folder_tree(id) AS (
                        SELECT id FROM folders WHERE id = ?
                        UNION ALL
                        SELECT f.id FROM folders f 
                        JOIN folder_tree ft ON f.parent_id = ft.id
                    )
                    SELECT COUNT(*) as count FROM folder_tree
                """, [folder_id]).fetchone()
                
                max_iterations = (subtree_count['count'] if subtree_count else 1) + 10  # Add buffer for safety
                
                # Iteratively delete leaf folders (folders with no children) until only root remains
                folders_deleted = True
                iteration = 0
                
                while folders_deleted and iteration < max_iterations:
                    # Delete folders that have no children and are not the root folder
                    result = conn.execute("""
                        WITH RECURSIVE folder_tree(id) AS (
                            SELECT id FROM folders WHERE id = ?
                            UNION ALL
                            SELECT f.id FROM folders f 
                            JOIN folder_tree ft ON f.parent_id = ft.id
                        )
                        DELETE FROM folders 
                        WHERE id IN (SELECT id FROM folder_tree)
                        AND id != ?
                        AND id NOT IN (
                            SELECT DISTINCT parent_id FROM folders 
                            WHERE parent_id IS NOT NULL
                            AND parent_id IN (SELECT id FROM folder_tree)
                        )
                    """, [folder_id, folder_id])
                    
                    folders_deleted = result.rowcount > 0
                    iteration += 1
                    
                    if folders_deleted:
                        self.logger.debug(f"Deleted {result.rowcount} leaf folders in iteration {iteration}")
                
                if iteration >= max_iterations:
                    self.logger.warning("Reached maximum iterations for folder deletion - continuing with root deletion")
                
                # Finally delete the root folder
                conn.execute("DELETE FROM folders WHERE id = ?", [folder_id])
            
            self.logger.info("Successfully removed existing ShortList Import folder and all contents")
            return True
            
        except Exception as e:
            self.logger.error(f"Error removing existing ShortList Import folder: {e}")
            return False

    def create_shortlist_import_folder(self) -> Optional[int]:
        """Create the 'ShortList Import' folder"""
        try:
            # Create new folder
            with self.conn_manager.transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO folders (name, parent_id)
                    VALUES (?, NULL)
                """, ["ShortList Import"])
                folder_id = cursor.lastrowid

            self.logger.info(f"Created ShortList Import folder (ID: {folder_id})")
            return folder_id

        except Exception as e:
            self.logger.error(f"Error creating ShortList Import folder: {e}")
            return None

    def create_or_get_shortlist_sublist(self, list_name: str, folder_id: int, conn=None) -> Tuple[Optional[int], bool]:
        """Create or get a list for a specific shortlist under the ShortList Import folder
        
        Returns:
            tuple: (list_id, was_created) where was_created is True if a new list was created
        """
        try:
            # Use provided connection or create a new transaction
            if conn is None:
                with self.conn_manager.transaction() as transaction_conn:
                    return self._create_or_get_list_internal(list_name, folder_id, transaction_conn)
            else:
                return self._create_or_get_list_internal(list_name, folder_id, conn)

        except Exception as e:
            self.logger.error(f"Error creating list '{list_name}': {e}")
            return None, False

    def _create_or_get_list_internal(self, list_name: str, folder_id: int, conn) -> Tuple[int, bool]:
        """Internal method to create or get list using provided connection"""
        # Check if list already exists in this folder
        existing = conn.execute(
            "SELECT id FROM lists WHERE name = ? AND folder_id = ?", 
            [list_name, folder_id]
        ).fetchone()

        if existing:
            list_id = existing['id']
            self.logger.info(f"Using existing list '{list_name}' (ID: {list_id})")
            return list_id, False

        # Create new list in the folder
        cursor = conn.execute("""
            INSERT INTO lists (name, folder_id)
            VALUES (?, ?)
        """, [list_name, folder_id])
        list_id = cursor.lastrowid

        self.logger.info(f"Created list '{list_name}' (ID: {list_id}) in ShortList Import folder")
        return list_id, True

    def import_shortlist_items(self) -> Dict[str, Any]:
        """Import all ShortList items into LibraryGenie"""
        self.logger.info("=== IMPORT_SHORTLIST_ITEMS METHOD CALLED ===")
        self.logger.info(f"Method signature check - self: {type(self)}")
        
        start_time = datetime.now()
        self.logger.info(f"Import started at: {start_time}")

        try:
            self.logger.info("Starting ShortList import process...")
            # Check if ShortList is installed
            if not self.is_shortlist_installed():
                return {
                    "success": False,
                    "error": "ShortList addon not found or not enabled"
                }

            # Scrape ShortList data
            shortlist_data = self.scrape_shortlist_data()
            if not shortlist_data:
                return {
                    "success": False,
                    "error": "No lists found in ShortList addon"
                }

            # REPLACE functionality: Remove any existing ShortList Import folder and contents
            if not self.remove_existing_shortlist_import():
                return {
                    "success": False,
                    "error": "Failed to remove existing ShortList Import data"
                }

            # Create the import folder
            import_folder_id = self.create_shortlist_import_folder()
            if not import_folder_id:
                return {
                    "success": False,
                    "error": "Failed to create ShortList Import folder"
                }

            # Process each shortlist as a separate list
            total_items = 0
            items_added = 0
            items_matched = 0
            lists_created = 0

            with self.conn_manager.transaction() as conn:
                for shortlist in shortlist_data:
                    list_name = shortlist["name"]
                    items = shortlist["items"]
                    total_items += len(items)

                    if not items:
                        self.logger.info(f"Skipping empty shortlist: '{list_name}'")
                        continue

                    self.logger.info(f"Processing {len(items)} items from '{list_name}'")

                    # Create or get list for this shortlist
                    list_id, was_created = self.create_or_get_shortlist_sublist(list_name, import_folder_id, conn)
                    if not list_id:
                        self.logger.error(f"Failed to create list for '{list_name}', skipping")
                        continue

                    if was_created:
                        lists_created += 1

                    # Clear existing items in this list
                    conn.execute(
                        "DELETE FROM list_items WHERE list_id = ?",
                        [list_id]
                    )

                    # Process items for this specific list
                    position = 0
                    for item in items:
                        try:
                            # Try to match to library movie
                            library_movie_id = self.match_movie_to_library(item)

                            if library_movie_id:
                                # Add mapped item to this specific list
                                conn.execute("""
                                    INSERT OR IGNORE INTO list_items 
                                    (list_id, media_item_id, position)
                                    VALUES (?, ?, ?)
                                """, [list_id, library_movie_id, position])

                                items_matched += 1
                                items_added += 1
                                position += 1
                            else:
                                # For unmapped items, we could optionally store them
                                # as metadata only entries, but for now we skip them
                                # since LibraryGenie focuses on library integration
                                self.logger.debug(f"Skipping unmapped item: {item.get('title')}")

                        except Exception as e:
                            self.logger.error(f"Error processing item {item.get('title')}: {e}")

                    self.logger.info(f"Completed list '{list_name}' with {position} items added")

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return {
                "success": True,
                "total_items": total_items,
                "items_added": items_added,
                "items_matched": items_matched,
                "items_unmapped": total_items - items_matched,
                "lists_processed": len(shortlist_data),
                "lists_created": lists_created,
                "duration_ms": duration_ms
            }

        except Exception as e:
            self.logger.error(f"ShortList import failed: {e}")
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return {
                "success": False,
                "error": str(e),
                "duration_ms": duration_ms
            }


# Global instance
_shortlist_importer_instance = None


def get_shortlist_importer():
    """Get global ShortList importer instance"""
    global _shortlist_importer_instance
    if _shortlist_importer_instance is None:
        _shortlist_importer_instance = ShortListImporter()
    return _shortlist_importer_instance


def import_from_shortlist():
    """Standalone function for settings action"""
    importer = get_shortlist_importer()
    return importer.import_shortlist_items()