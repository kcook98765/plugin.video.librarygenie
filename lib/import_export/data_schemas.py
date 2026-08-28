#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Data Schemas
Versioned schemas for import/export operations
"""

import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict


def _addon_metadata() -> Dict[str, str]:
    """Return the running addon's real ``id`` and ``version``.

    The authoritative source is the Kodi API (``xbmcaddon``), the same source
    the rest of the addon uses for its identity -- so a normal Kodi run never
    touches the filesystem.

    When the Kodi API is unavailable (pure off-Kodi tooling / tests) both
    values are read from the addon's own ``addon.xml`` in the source tree,
    located relative to this file. That avoids duplicating the version
    constant in Python.
    """
    try:
        import xbmcaddon

        addon = xbmcaddon.Addon()
        addon_id = addon.getAddonInfo("id") or ""
        addon_version = addon.getAddonInfo("version") or ""
        if addon_id and addon_version:
            return {"addon_id": addon_id, "addon_version": addon_version}
    except Exception:
        pass

    return _addon_metadata_from_xml()


def _addon_metadata_from_xml() -> Dict[str, str]:
    """Read the addon ``id``/``version`` from the addon's own ``addon.xml``.

    Used only when the Kodi API is not available. Locates ``addon.xml`` two
    directories above this file (``lib/import_export/`` -> repo root) and
    reads the root element's ``id``/``version`` attributes via the stdlib.
    Raises if the file cannot be found or parsed; callers treat that as a
    genuine error rather than silently emitting wrong metadata.
    """
    addon_xml = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "addon.xml",
    )
    root = ET.parse(addon_xml).getroot()
    return {
        "addon_id": root.get("id", ""),
        "addon_version": root.get("version", ""),
    }


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
        metadata = _addon_metadata()
        return cls(
            addon_id=metadata["addon_id"],
            addon_version=metadata["addon_version"],
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
    imdbnumber: Optional[str]
    tmdb_id: Optional[str]
    external_ids: Dict[str, str]
    backup_metadata: Optional[Dict[str, Any]] = None


@dataclass
class ExportedFolder:
    """Exported folder data structure"""
    id: int
    name: str
    parent_id: Optional[int]
    created_at: str


@dataclass
class ExportedFavorite:
    """Exported favorite data structure (mapped items only)"""
    name: str
    kodi_id: Optional[int]
    title: str
    year: Optional[int]
    file_path: str
    normalized_path: str
    imdbnumber: Optional[str]
    tmdb_id: Optional[str]
    backup_metadata: Optional[Dict[str, Any]] = None


@dataclass
class ExportedLibraryItem:
    """Exported library snapshot item"""
    kodi_id: int
    title: str
    year: Optional[int]
    file_path: str
    imdbnumber: Optional[str]
    tmdb_id: Optional[str]
    external_ids: Dict[str, str]
    added_at: str
    backup_metadata: Optional[Dict[str, Any]] = None


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
                # Description is optional but should be a string if present
                if "description" in item and not isinstance(item["description"], (str, type(None))):
                    errors.append(f"lists[{i}]: description must be a string")
        
        elif export_type == "list_items":
            for i, item in enumerate(data):
                required_fields = ["list_id", "title"]
                for field in required_fields:
                    if field not in item:
                        errors.append(f"list_items[{i}]: missing {field}")
        
        elif export_type == "favorites":
            for i, item in enumerate(data):
                required_fields = ["name", "normalized_path", "original_path"]
                for field in required_fields:
                    if field not in item:
                        errors.append(f"favorites[{i}]: missing {field}")
        
        elif export_type == "library_snapshot":
            for i, item in enumerate(data):
                required_fields = ["kodi_id", "title", "file_path", "media_type"]
                for field in required_fields:
                    if field not in item:
                        errors.append(f"library_snapshot[{i}]: missing {field}")
        
        elif export_type == "folders":
            for i, item in enumerate(data):
                required_fields = ["id", "name", "created_at"]
                for field in required_fields:
                    if field not in item:
                        errors.append(f"folders[{i}]: missing {field}")
        
        return errors