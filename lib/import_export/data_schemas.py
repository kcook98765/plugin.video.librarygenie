#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Data Schemas
Versioned schemas for import/export operations
"""

from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import json


@dataclass
class ExportEnvelope:
    """Top-level envelope for all exports"""
    addon_id: str
    addon_version: str
    schema_version: int
    generated_at: str  # ISO 8601 UTC
    export_types: List[str]
    payload: Dict[str, Any]
    
    @classmethod
    def create(cls, export_types: List[str], payload: Dict[str, Any]) -> 'ExportEnvelope':
        """Create new export envelope with current metadata"""
        return cls(
            addon_id="plugin.video.library.genie",
            addon_version="0.0.1",
            schema_version=1,
            generated_at=datetime.now(timezone.utc).isoformat(),
            export_types=export_types,
            payload=payload
        )
    
    def to_json(self) -> str:
        """Serialize to JSON string"""
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ExportEnvelope':
        """Deserialize from JSON string"""
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class ExportedList:
    """Exported list data structure"""
    id: int
    name: str
    description: str
    created_at: str
    updated_at: str
    item_count: int


@dataclass
class ExportedListItem:
    """Exported list membership data structure"""
    list_id: int
    kodi_id: Optional[int]
    title: str
    year: Optional[int]
    file_path: str
    imdb_id: Optional[str]
    tmdb_id: Optional[str]
    external_ids: Dict[str, str]


@dataclass
class ExportedFavorite:
    """Exported favorite data structure (mapped items only)"""
    name: str
    kodi_id: Optional[int]
    title: str
    year: Optional[int]
    file_path: str
    normalized_path: str
    imdb_id: Optional[str]
    tmdb_id: Optional[str]


@dataclass
class ExportedLibraryItem:
    """Exported library snapshot item"""
    kodi_id: int
    title: str
    year: Optional[int]
    file_path: str
    imdb_id: Optional[str]
    tmdb_id: Optional[str]
    external_ids: Dict[str, str]
    added_at: str


@dataclass
class ImportPreview:
    """Preview of import operations before execution"""
    lists_to_create: List[str]
    lists_to_update: List[str]
    items_to_add: int
    items_already_present: int
    items_unmatched: int
    total_operations: int
    warnings: List[str]


@dataclass
class ImportResult:
    """Result of import operation"""
    success: bool
    lists_created: int
    lists_updated: int
    items_added: int
    items_skipped: int
    items_unmatched: int
    unmatched_items: List[Dict[str, Any]]
    errors: List[str]
    duration_ms: int


class ExportSchema:
    """Schema definitions and validation"""
    
    CURRENT_VERSION = 1
    SUPPORTED_VERSIONS = [1]
    
    REQUIRED_ENVELOPE_FIELDS = ["addon_id", "schema_version", "generated_at", "export_types", "payload"]
    
    @classmethod
    def validate_envelope(cls, data: Dict[str, Any]) -> List[str]:
        """Validate export envelope structure"""
        errors = []
        
        # Check required fields
        for field in cls.REQUIRED_ENVELOPE_FIELDS:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        # Check schema version
        if "schema_version" in data:
            version = data["schema_version"]
            if version not in cls.SUPPORTED_VERSIONS:
                errors.append(f"Unsupported schema version: {version}")
        
        # Check export types
        if "export_types" in data:
            if not isinstance(data["export_types"], list):
                errors.append("export_types must be a list")
            elif not data["export_types"]:
                errors.append("export_types cannot be empty")
        
        # Check payload
        if "payload" in data:
            if not isinstance(data["payload"], dict):
                errors.append("payload must be an object")
        
        return errors
    
    @classmethod
    def validate_export_type(cls, export_type: str, data: List[Dict]) -> List[str]:
        """Validate specific export type data"""
        errors = []
        
        if export_type == "lists":
            for i, item in enumerate(data):
                required_fields = ["id", "name", "created_at"]
                for field in required_fields:
                    if field not in item:
                        errors.append(f"lists[{i}]: missing {field}")
        
        elif export_type == "list_items":
            for i, item in enumerate(data):
                required_fields = ["list_id", "title"]
                for field in required_fields:
                    if field not in item:
                        errors.append(f"list_items[{i}]: missing {field}")
        
        elif export_type == "favorites":
            for i, item in enumerate(data):
                required_fields = ["name", "title", "normalized_path"]
                for field in required_fields:
                    if field not in item:
                        errors.append(f"favorites[{i}]: missing {field}")
        
        elif export_type == "library_snapshot":
            for i, item in enumerate(data):
                required_fields = ["kodi_id", "title", "file_path"]
                for field in required_fields:
                    if field not in item:
                        errors.append(f"library_snapshot[{i}]: missing {field}")
        
        return errors