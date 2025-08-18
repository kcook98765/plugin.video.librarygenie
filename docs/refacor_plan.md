Objective

Create one canonical path from “raw movie/episode data from anywhere” → “Kodi ListItem on screen,” with all Kodi-version differences, art mapping, and context menus handled once.

Deliverables (what should exist when done)

data/models.py with MediaItem and Actor dataclasses.

data/normalize/ module with three normalizers:

from_jsonrpc()

from_remote_api()

from_db()
Each returns a MediaItem.

kodi/adapters/infotag_adapter.py to apply InfoTag fields and version-specific behavior.

kodi/adapters/art_mapper.py to map MediaItem.art → Kodi art keys.

kodi/listitem/factory.py with a single build_listitem(MediaItem, view_hint) entry point.

kodi/menu/registry.py exposing for_item(MediaItem) -> list[menu entries].

All existing views/routes use build_listitem() and do not set InfoTags or art directly.

File-by-file instructions
1) New files to add
resources/lib/data/models.py

Define MediaItem (movie/episode/folder) with these fields (adjust if needed):
id, media_type, title, year, imdb, tmdb, plot, genres, runtime, rating, votes, studio, country, stream_details, play_path, is_folder, art (dict), cast (list[Actor]), context_tags (set), sort_keys, extras (dict for odd fields).

Define Actor with name, role, order, thumb.

resources/lib/data/normalize/__init__.py

Add three functions:

from_jsonrpc(payload) -> MediaItem

from_remote_api(payload) -> MediaItem

from_db(row) -> MediaItem

In each, normalize:

IDs (imdb/tmdb), title/year, plot cleanup, genres list, cast list, art dict (poster, fanart, thumb, banner, landscape), runtime seconds, rating + votes, play_path, is_folder.

Apply consistent defaults (empty strings/lists/dicts), and ensure you never return None for required text fields.

resources/lib/kodi/adapters/infotag_adapter.py

One public function: apply_infotag(item: MediaItem, li):

Write all InfoTag data to li in one place.

Internally route to per-version helpers (v19/v20/v21) for cast, ratings, unique IDs, and stream details.

Handle the v21 xbmcgui.Actor/setCast path here only (not in screens).

Add robust try/except and a small debug log on version fallback.

resources/lib/kodi/adapters/art_mapper.py

One function: apply_art(item: MediaItem, li):

Translate your item.art into Kodi art keys (poster, fanart, thumb, clearlogo, etc.).

Provide safe fallbacks (e.g., fanart = poster if missing).

resources/lib/kodi/listitem/factory.py

One function: build_listitem(item: MediaItem, view_hint: str|Enum) -> xbmcgui.ListItem

Sets label/label2, isFolder/playable, calls apply_infotag, apply_art, and sets any needed properties (e.g., infolabels that aren’t in InfoTag, sort keys).

Attaches context menu entries from menu/registry.py.

resources/lib/kodi/menu/registry.py

One function: for_item(item: MediaItem) -> list[tuple(label, action)]

Implement rules like “show ‘Find Similar’ only if item.imdb starts with ‘tt’”, shortlist actions, etc.

No UI calls here—just return menu definitions.

2) Existing files to stop doing UI shaping and delegate instead

For each file below, remove direct ListItem/InfoTag/art manipulation and replace with:

normalize source data → MediaItem

build ListItem via build_listitem(item, view_hint)

do not call setCast, setArt, or write InfoTag directly here.

resources/lib/listitem_builder.py

Action: Convert to thin wrappers or delete if fully superseded.

Replace any InfoTag/art writes with a call to the factory.

resources/lib/listitem_infotagvideo.py

Action: Move all version-specific InfoTag/cast logic into kodi/adapters/infotag_adapter.py.

Leave only minor convenience helpers (or retire this file after moving content).

resources/lib/context_menu_builder.py

Action: Move menu decision logic into kodi/menu/registry.py.

Keep only glue code if necessary (or retire).

resources/lib/directory_builder.py

Action: Replace “build each ListItem” code with:

Build MediaItem via the appropriate normalizer,

Pass to build_listitem(),

Add to directory.

resources/lib/route_handlers.py

Action: In each handler that renders a list:

Gather source payloads,

Map each payload → MediaItem using the correct normalizer,

Call build_listitem() for display.

resources/lib/navigation_manager.py

Action: Ensure navigation code no longer touches InfoTag/art/cast directly.

Only responsible for routing and view_hint selection (if needed).

resources/lib/window_search.py

Action: When showing results, create MediaItem for each result, then build_listitem().

3) Integration points: produce MediaItem, not ListItem
resources/lib/integrations/jsonrpc/jsonrpc_manager.py

Action: Stop producing UI-ready dicts/ListItems.

Provide raw JSON-RPC payloads or an optional helper that returns MediaItem via normalize.from_jsonrpc().

resources/lib/integrations/remote_api/* (client/setup/auth/imdb_upload_manager/shortlist_importer)

Action: Same approach—either return raw payloads or directly MediaItem via normalize.from_remote_api().

resources/lib/data/query_manager.py and resources/lib/data/results_manager.py

Action: If they currently shape UI dicts, refocus them on data retrieval/joins only.

If convenient, let results_manager convert DB rows → MediaItem using normalize.from_db().

resources/lib/data/database_manager.py

Action: No UI code here. Optionally add small helper to fetch rows and let normalize.from_db() do the shaping elsewhere.

4) Utilities/config that may need small changes
resources/lib/kodi/kodi_helper.py

Action: Keep window/dialog helpers only. Remove any per-item InfoTag setting.

resources/lib/media/media_manager.py

Action: If it generates art URLs or paths, make sure it returns them into MediaItem.art. Do not set art on ListItems here.

resources/lib/config/*

Action: No feature change; you might add a single get_kodi_version() utility here (or keep it in a shared utils) so infotag_adapter.py can read version once.

resources/lib/utils/utils.py

Action: Keep generic helpers (logging, version parse, safe access). Remove anything that writes to UI objects.

5) Import updates (pattern)

Replace call sites that import builders/ad-hoc UI code with:

from resources.lib.data.normalize import from_jsonrpc, from_remote_api, from_db

from resources.lib.kodi.listitem.factory import build_listitem

from resources.lib.kodi.menu.registry import for_item (only if directly used)

Migration steps (do in this order)

Add new modules (models.py, normalize/, adapters/, factory.py, menu/registry.py).

Move InfoTag/art/cast code from listitem_infotagvideo.py into infotag_adapter.py. Keep behavior identical.

Implement build_listitem() so it calls the adapter + art mapper and attaches context menu entries.

Wire one route end-to-end (pick a simple movie list route):

Route handler → use a normalizer → MediaItem → build_listitem() → display.

Verify on v19/20/21 (cast, art, ratings all appear).

Convert remaining screens (directory builder, search window, etc.) to the same pattern.

Convert integrations to return raw payloads or MediaItem (but not ListItems).

Delete/retire now-unused per-view InfoTag/art writes and duplicated version checks.

Run a global search for setCast, setArt, direct InfoTag writes—ensure all occur only in infotag_adapter.py / art_mapper.py.

Logging: On the adapter, add a small “version path chosen” debug log once per session to confirm routing.

Acceptance criteria (how we know we’re done)

There is exactly one place where:

Cast is written (including v21 Actor objects),

Art is mapped,

Ratings/votes/unique IDs are applied.

No file outside kodi/adapters/* writes InfoTag or calls setCast/setArt.

Every route/build step follows: payload → normalizer → MediaItem → build_listitem().

Adding a new data source (e.g., a different API) only requires a new normalize.from_newsource(); nothing else changes.

Upgrading to a new Kodi version requires changes only in infotag_adapter.py.

Notes on scope & risk

No UX behavior change is intended; this is a mechanical refactor. Screens should look the same.

If any screen had special label2/prop quirks, carry those into build_listitem() via a view_hint argument (string or small Enum).

If context menus varied per screen, encode those rules in menu/registry.py using item.context_tags or view_hint.