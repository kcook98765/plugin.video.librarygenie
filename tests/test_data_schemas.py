"""Tests for lib.import_export.data_schemas (envelope + validation logic).

Pure-Python dataclasses / validators - no Kodi dependency.
"""

import os
import sys
import xml.etree.ElementTree as ET

from lib.import_export.data_schemas import (
    ExportEnvelope,
    ExportSchema,
    _addon_metadata,
)


def test_envelope_create_defaults():
    env = ExportEnvelope.create(["lists"], {"lists": []})
    assert env.schema_version == 1
    # create() must report the *real* addon identity (see below), not a
    # hard-coded placeholder. Under the test stubs the id/version are
    # "plugin.video.librarygenie" / "0.8.49".
    assert env.addon_id == "plugin.video.librarygenie"
    assert env.addon_version == "0.8.49"
    assert env.export_types == ["lists"]
    assert env.payload == {"lists": []}
    # generated_at must be a parseable ISO-8601 timestamp.
    from datetime import datetime

    datetime.fromisoformat(env.generated_at)


def test_envelope_create_uses_real_addon_metadata(monkeypatch):
    """create() must source id/version from the live addon, not constants.

    Point the stub ``xbmcaddon.Addon`` at a distinct id/version and confirm
    the envelope carries those exact values. This fails if the factory falls
    back to a baked-in constant instead of reading the addon.
    """
    import tests.kodimocks as km

    real_addon = km.Addon

    class _Addon:
        def __init__(self, *a, **k):
            pass

        def getAddonInfo(self, key):
            if key == "id":
                return "plugin.video.testid"
            if key == "version":
                return "9.9.9"
            return ""

    km.Addon = _Addon
    # ExportEnvelope reads the module-level name via `import xbmcaddon`, so
    # patch the sys.modules entry that the stub installed too.
    import sys

    sys.modules["xbmcaddon"].Addon = _Addon
    try:
        env = ExportEnvelope.create(["lists"], {})
        assert env.addon_id == "plugin.video.testid"
        assert env.addon_version == "9.9.9"
    finally:
        km.Addon = real_addon
        sys.modules["xbmcaddon"].Addon = real_addon


def test_envelope_create_fallback_without_kodi(monkeypatch):
    """When the Kodi API is unavailable, id/version come from addon.xml.

    Forcing the off-Kodi path (by hiding ``xbmcaddon``) must return the
    values declared in the addon's own ``addon.xml`` -- i.e. the real id and
    version, not a hard-coded Python constant.
    """
    import lib.import_export.data_schemas as ds

    # The expected values, read straight from the repo's addon.xml so the
    # assertion tracks the actual source of truth rather than a copy.
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(ds.__file__))))
    expected = ET.parse(os.path.join(repo_root, "addon.xml")).getroot()
    expected_id = expected.get("id")
    expected_version = expected.get("version")

    # Hide xbmcaddon so `import xbmcaddon` fails and the xml path is taken.
    # monkeypatch restores the original stub on teardown.
    monkeypatch.setitem(sys.modules, "xbmcaddon", None)
    meta = ds._addon_metadata()
    assert meta == {
        "addon_id": expected_id,
        "addon_version": expected_version,
    }
    # Sanity: these are the real addon identity, not placeholders.
    assert expected_id == "plugin.video.librarygenie"
    assert expected_version is not None and expected_version != "0.0.1"


def test_envelope_json_round_trip():
    payload = {"lists": [{"id": 1, "name": "My List"}]}
    env = ExportEnvelope.create(["lists"], payload)
    restored = ExportEnvelope.from_json(env.to_json())
    assert restored.addon_id == env.addon_id
    assert restored.export_types == ["lists"]
    assert restored.payload == payload


def test_envelope_metadata_not_placeholder():
    """Regression: the old hard-coded values must be gone.

    Before the fix ``ExportEnvelope.create`` baked in
    ``addon_id="plugin.video.library.genie"`` (dotted, wrong id) and
    ``addon_version="0.0.1"`` (placeholder). These asserts fail against that
    implementation.
    """
    env = ExportEnvelope.create(["lists"], {})
    assert env.addon_id != "plugin.video.library.genie"
    assert env.addon_version != "0.0.1"
    assert env.addon_id == "plugin.video.librarygenie"


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
