5) Fix the external/plugin-only path in the builder

When there’s no kodi_id, use your plugin://… URL 

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