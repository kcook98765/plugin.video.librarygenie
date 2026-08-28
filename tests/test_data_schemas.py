"""Tests for lib.import_export.data_schemas (envelope + validation logic).

Pure-Python dataclasses / validators - no Kodi dependency.
"""

from lib.import_export.data_schemas import (
    ExportEnvelope,
    ExportSchema,
)


def test_envelope_create_defaults():
    env = ExportEnvelope.create(["lists"], {"lists": []})
    assert env.schema_version == 1
    assert env.addon_id == "plugin.video.library.genie"
    assert env.export_types == ["lists"]
    assert env.payload == {"lists": []}
    # generated_at must be a parseable ISO-8601 timestamp.
    from datetime import datetime

    datetime.fromisoformat(env.generated_at)


def test_envelope_json_round_trip():
    payload = {"lists": [{"id": 1, "name": "My List"}]}
    env = ExportEnvelope.create(["lists"], payload)
    restored = ExportEnvelope.from_json(env.to_json())
    assert restored.addon_id == env.addon_id
    assert restored.export_types == ["lists"]
    assert restored.payload == payload


def test_envelope_documented_hardcoded_metadata():
    """Pin the metadata that ``ExportEnvelope.create`` hard-codes.

    Two values are baked into the factory rather than read from the running
    addon (see ``lib/import_export/data_schemas.py``):

    * ``addon_id`` is the string ``"plugin.video.library.genie"`` -- a dotted
      form that differs from the addon's real id
      ``"plugin.video.librarygenie"`` (the id used in ``addon.xml`` and all
      ``plugin://`` URLs).
    * ``addon_version`` is the placeholder ``"0.0.1"`` rather than the live
      ``addon.xml`` version.

    Neither is used by the importer (it validates ``schema_version``), so
    this documents current behaviour. If/when the factory is updated to emit
    the real addon id/version, update these two asserts.
    """
    env = ExportEnvelope.create(["lists"], {})
    assert env.addon_id == "plugin.video.library.genie"  # != real addon id
    assert env.addon_version == "0.0.1"  # placeholder, not live version


def test_validate_envelope_valid():
    data = {
        "addon_id": "plugin.video.librarygenie",
        "schema_version": 1,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "export_types": ["lists"],
        "payload": {},
    }
    assert ExportSchema.validate_envelope(data) == []


def test_validate_envelope_missing_required_field():
    data = {"schema_version": 1, "export_types": ["lists"], "payload": {}}
    errors = ExportSchema.validate_envelope(data)
    assert any("addon_id" in e for e in errors)
    assert any("generated_at" in e for e in errors)


def test_validate_envelope_unsupported_version():
    data = {
        "addon_id": "x",
        "schema_version": 99,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "export_types": ["lists"],
        "payload": {},
    }
    errors = ExportSchema.validate_envelope(data)
    assert any("Unsupported schema version" in e for e in errors)


def test_validate_envelope_bad_shapes():
    data = {
        "addon_id": "x",
        "schema_version": 1,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "export_types": [],      # empty list is invalid
        "payload": "not-a-dict", # wrong type
    }
    errors = ExportSchema.validate_envelope(data)
    assert any("export_types cannot be empty" in e for e in errors)
    assert any("payload must be an object" in e for e in errors)


def test_validate_lists_requires_fields():
    errors = ExportSchema.validate_export_type("lists", [{"name": "x"}])
    assert any("lists[0]: missing id" in e for e in errors)
    assert any("lists[0]: missing created_at" in e for e in errors)


def test_validate_list_items_requires_fields():
    errors = ExportSchema.validate_export_type("list_items", [{"title": "x"}])
    assert any("list_items[0]: missing list_id" in e for e in errors)


def test_validate_folders_requires_fields():
    errors = ExportSchema.validate_export_type("folders", [{"name": "x"}])
    assert any("folders[0]: missing id" in e for e in errors)


def test_validate_unknown_type_is_noop():
    assert ExportSchema.validate_export_type("nonsense", [{"a": 1}]) == []
