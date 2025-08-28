ere’s a single, end-to-end checklist to bring your current code in line with the desired ListItem behavior (Matrix v19 + v20+), with resume always shown for library items, light metadata only, and clean version branching. I’m referencing the files currently in your zip (notably lib/ui/listitem_builder.py, lib/ui/listitem_renderer.py, lib/ui/menu_builder.py, lib/ui/search_handler.py, and lib/data/query_manager.py). No code snippets—just the exact steps to apply.

Step-by-step changes (apply in order)
1) Centralize version detection (used by the builder)

Add a tiny helper in your ListItem builder module (since lib/utils/versioning.py isn’t present):

Provide a function that returns True if Kodi major version ≥ 20, otherwise False. Use xbmc.getInfoLabel("System.BuildVersion") parsing or a similar, already-available helper if you have one elsewhere.

You’ll use this in the builder to decide how to set resume and whether to call any InfoTag setters.

2) Normalize the item model that the builder consumes

Make sure every item handed to the builder (library or plugin) has:

Identity: type ("movie" / "episode" / "tvshow"), and for library items, the Kodi DB id (kodi_id).

Lightweight fields (strings unless noted): title, originaltitle (if different), sorttitle, year (int), genre (comma-separated string), plot or plotoutline, rating (float 0–10), votes (int), mpaa, duration_minutes (int), studio, country, premiered or dateadded (YYYY-MM-DD), and mediatype (must match Kodi: movie/episode/tvshow).

Episode extras (when type == "episode"): tvshowtitle, season (int), episode (int), aired (YYYY-MM-DD), playcount (int), lastplayed (string) if you have it.

Art: dictionary with keys you actually have: poster, fanart (minimum); plus thumb, banner, landscape, clearlogo only if valid.

Resume: a resume dict with position_seconds and total_seconds for all library movies/episodes. (You will always set these in the list view for library items.)

If you already have a normalizer, verify these keys exist and have the expected types; otherwise adapt your normalizer to produce them.

3) Ensure the data layer fetches the right fields (no heavy arrays)

Edit your query/enrichment functions in lib/data/query_manager.py so JSON-RPC calls request only what you need for list rows:

Movies: request properties including: title, originaltitle, year, genre, plotoutline, rating, votes, mpaa, runtime, studio, country, premiered, sorttitle, thumbnail, art, resume.

Episodes: title, plotoutline, season, episode, showtitle, aired, runtime, rating, playcount, lastplayed, thumbnail, art, resume.

TV shows (for show rows): the same light set as movies (omit resume—resume is per episode/movie).

Map runtime to your duration_minutes variable; map resume.position/resume.total (seconds) into your resume dict.

4) Fix the library path in the ListItem builder (lib/ui/listitem_builder.py)

When kodi_id is present and type is movie or episode (i.e., it’s a library-backed item):

URL: keep using your existing videodb:// builder for the addDirectoryItem URL (your logs show this is already working for movies).

Folder/Playable: mark rows properly (most movie/episode rows are not folders; set IsPlayable="true" if they’re playable).

Light metadata: set only the lightweight fields listed in Step 2. Do not inject heavy fields (cast, big arrays).

Art: set poster and fanart at minimum; add others only if valid.

Resume (always for library movies/episodes):

v19 path (Matrix): set ListItem properties ResumeTime and TotalTime with seconds from your resume dict.

v20+ path: set the resume point on the item’s video tag (seconds).

Use your version helper to branch. Do not call v20-only APIs on v19.

Remove/disable any v20-only InfoTag setters you currently call on library items (e.g., the setMediaType call your logs warned about). Those should be guarded by version, and skipped entirely on v19.

Rationale: For library items, Kodi’s background loader will hydrate art and some basics for visible rows; you are supplying just enough to make the list feel native immediately, plus resume, without heavy fields.

5) Fix the external/plugin-only path in the builder

When there’s no kodi_id, use your plugin://… URL (or route to your play/details action).

Apply the exact same lightweight info profile and art keys as in Step 4.

Resume for plugin-only: only set if you maintain your own resume store for those items (your “always show resume” rule applies to library items; plugin-only items are at your discretion).

Keep folder/playable flags correct (IsPlayable="true" only for playable rows).

6) Don’t set heavy fields in list rows

Remove or disable any code that tries to set cast (your listitem_builder.py has a _set_cast routine—leave it unused for list views).

Do not populate deep streamdetails in list rows unless you already have them trivially; this keeps scrolling snappy and matches Kodi’s own approach in plugin containers.

7) Container hygiene—do it once per directory build

In the part of your pipeline that finalizes a directory page (likely lib/ui/listitem_renderer.py or menu_builder.py):

Before adding items, set content type appropriately (movies, episodes, or tvshows) so skins choose correct layouts/overlays.

Add a few sort methods (Title-Ignore-The, Year, Date) like you’re already attempting; make sure this runs only once per build (not per item).

Ensure every item added has a non-empty URL to avoid directory errors.

8) Remove v20-only calls in v19 code paths (eliminate warnings)

Your logs showed:
'xbmc.InfoTagVideo' object has no attribute 'setMediaType'

Search your codebase for InfoTag setters you’re calling unconditionally in the library path (setMediaType, setDbId, setCast, etc.).

Guard all such calls behind your version helper; skip them on v19.

In v19, rely on the classic info labels and ListItem properties described above.

9) Verify the resume mapping end-to-end

Confirm JSON-RPC resume values (seconds) are present for library movies/episodes in your enrichment step.

Ensure the builder sets:

v19: ResumeTime and TotalTime ListItem properties (seconds).

v20+: the resume point on the video tag (seconds).

Confirm you’re not accidentally converting to minutes here—resume stays in seconds for both versions.


Where to make the edits (recap by file)

lib/data/query_manager.py
Add resume to JSON-RPC properties for movies/episodes; keep the property sets “light” as above; map runtime → minutes; map resume seconds.

lib/ui/listitem_builder.py
Add version helper; apply version-branched resume setting; remove v20-only tag setters from v19 path; ensure URL/isFolder/IsPlayable and the lightweight info/art profile; stop calling _set_cast in list rows.

lib/ui/listitem_renderer.py (or your directory finalizer)
Set container content and sort methods once per page; add items with non-empty URLs.