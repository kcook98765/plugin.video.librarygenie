#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Skin Mappings Manager
Manages skin control mappings in database
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, List, Optional

from ..utils.logger import get_logger


class SkinMappingsManager:
    """Manages skin control mappings in database"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self.logger = get_logger(__name__)
        self._ensure_table_exists()
        self._ensure_default_mappings()
    
    def _ensure_table_exists(self) -> None:
        """Ensure skin_mappings table exists"""
        create_sql = """
            CREATE TABLE IF NOT EXISTS skin_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skin_id TEXT UNIQUE,
                preset_key TEXT UNIQUE,
                display_name TEXT NOT NULL,
                down_controls TEXT NOT NULL DEFAULT '',
                right_controls TEXT NOT NULL DEFAULT '',
                is_builtin INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """
        self.db.execute(create_sql)
        
        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_skin_mappings_skin_id ON skin_mappings(skin_id)",
            "CREATE INDEX IF NOT EXISTS idx_skin_mappings_preset_key ON skin_mappings(preset_key)",
            "CREATE INDEX IF NOT EXISTS idx_skin_mappings_is_active ON skin_mappings(is_active)"
        ]
        for index_sql in indexes:
            self.db.execute(index_sql)
    
    def get_mapping_by_skin_id(self, skin_id: str) -> Optional[Dict]:
        """Get skin mapping by Kodi skin ID"""
        query = """
            SELECT preset_key, display_name, down_controls, right_controls
            FROM skin_mappings 
            WHERE skin_id = ? AND is_active = 1
        """
        result = self.db.fetchone(query, (skin_id,))
        return dict(result) if result else None
    
    def get_mapping_by_preset_key(self, preset_key: str) -> Optional[Dict]:
        """Get skin mapping by preset key"""
        query = """
            SELECT skin_id, display_name, down_controls, right_controls
            FROM skin_mappings 
            WHERE preset_key = ? AND is_active = 1
        """
        result = self.db.fetchone(query, (preset_key,))
        return dict(result) if result else None
        
    def get_all_mappings_for_gui(self) -> List[Dict]:
        """Get all mappings ordered for GUI display (Auto and Custom first, then alphabetical)"""
        query = """
            SELECT preset_key, display_name
            FROM skin_mappings 
            WHERE is_active = 1
            ORDER BY 
                CASE preset_key 
                    WHEN 'auto' THEN 0
                    WHEN 'custom' THEN 1  
                    ELSE 2
                END,
                display_name ASC
        """
        return [dict(row) for row in self.db.fetchall(query)]
    
    def add_or_update_mapping(self, skin_id: str, preset_key: str, 
                             display_name: str, down_controls: str, 
                             right_controls: str, is_builtin: bool = False) -> bool:
        """Add or update a skin mapping"""
        try:
            timestamp = datetime.now().isoformat()
            
            # Check if mapping exists
            existing = self.get_mapping_by_preset_key(preset_key)
            
            if existing:
                # Update existing mapping
                query = """
                    UPDATE skin_mappings 
                    SET skin_id = ?, display_name = ?, down_controls = ?, 
                        right_controls = ?, is_builtin = ?, updated_at = ?
                    WHERE preset_key = ?
                """
                self.db.execute(query, (skin_id, display_name, down_controls, 
                                      right_controls, int(is_builtin), timestamp, preset_key))
            else:
                # Insert new mapping
                query = """
                    INSERT INTO skin_mappings 
                    (skin_id, preset_key, display_name, down_controls, right_controls, 
                     is_builtin, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """
                self.db.execute(query, (skin_id, preset_key, display_name, 
                                      down_controls, right_controls, 
                                      int(is_builtin), timestamp, timestamp))
            return True
        except Exception as e:
            self.logger.error(f"Failed to add/update skin mapping: {e}")
            return False
    
    def _ensure_default_mappings(self) -> None:
        """Initialize default skin mappings if not present"""
        defaults = [
            ("", "auto", "Auto-Detect", "", "", True),
            ("", "custom", "Custom", "", "", True),
            ("skin.estuary", "estuary", "Estuary (Default)", "50,55", "500,501,502,51,52,53,54", True),
            ("skin.arctic.zephyr.mod", "arctic_zephyr", "Arctic Zephyr Reloaded", "50,58,59,52", "53,55", True),
            ("skin.aeon.nox.silvo", "aeon_nox", "Aeon Nox SiLVO", "50,55", "500,501,502,56,57,58,59", True),
            ("skin.mimic", "mimic", "Mimic", "50,52,55", "500,501,502,504,505,507,509,520", True),
            ("skin.confluence", "confluence", "Confluence", "50,52", "500,501", True),
        ]
        
        for skin_id, preset_key, display_name, down, right, builtin in defaults:
            # Only add if doesn't exist
            existing = self.get_mapping_by_preset_key(preset_key)
            if not existing:
                self.add_or_update_mapping(skin_id, preset_key, display_name, down, right, builtin)
                self.logger.debug(f"Added default skin mapping: {display_name}")