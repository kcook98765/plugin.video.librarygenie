Here’s a tight, version-aware recipe to make your plugin directory list look like Kodi’s native lists—including resume in the list view for all library items—while keeping things light (no heavy fields like cast).

1) Row types you’ll output

Library-backed rows (you matched the item to Kodi’s DB and know the id):
Use a videodb://… URL for the row. You will still set lightweight info yourself (below), and you will always set resume for these rows.

Plugin-only rows (no DB id):
Use your plugin://… URL and set the same lightweight info. Resume is up to you (only if you store it yourself), but the “always use resume” requirement here applies to library-backed items.

2) Lightweight fields to set on every video row

Set what you have; skip what you don’t. These mirror what native lists show without heavy metadata.

Common (movies / episodes / shows)

title

originaltitle (if different)

sorttitle (helpful for consistent sorting)

year

genre (comma-separated string, e.g., “Horror, Drama”)

plot or plotoutline (pick one; outline is shorter)

rating (0–10 float)

votes (int)

mpaa (e.g., R, PG-13)

duration (minutes, not seconds)

studio (primary only)

country (primary only)

premiered or dateadded (YYYY-MM-DD)

mediatype (movie, episode, tvshow, musicvideo)

Episodes

tvshowtitle

season, episode

aired (YYYY-MM-DD)

playcount (int), lastplayed (if you have it)

TV shows (show rows)

Same basics; don’t pull/show heavy counts unless you already have them cached.

Artwork (light & skin-friendly)

Set: poster, fanart

Nice to have: thumb (use poster if nothing else), banner, landscape, clearlogo

Never pass None/broken URLs—omit missing keys.

Skip in list view (heavy)

Cast / roles

Deep streamdetails (codec/bitrate/channels), unless you already have them locally

3) Resume in the list view (always for library items)

Library-backed movies & episodes:
Always show resume progress in your list rows. That means you must set the per-row resume fields for every library match you list.

Kodi v19 (Matrix): set the classic ListItem properties ResumeTime and TotalTime (in seconds) on the row.

Kodi v20+: set the row’s resume point on the video info tag (time and totalTime in seconds).
(You’ll detect the running Kodi version at runtime and choose the appropriate method.)

TV show rows: resume is per movie/episode; don’t attempt resume on the show node itself.

Playback-time persistence is handled by Kodi. Your job here is simply to show resume in the list for library items by setting the per-row fields every time you build the directory.

4) Minimal JSON-RPC to pull (only what you need)

To prefill those lightweight fields (and resume) without heavy arrays, batch one of these per page:

Movies — use VideoLibrary.GetMovies with:

["title","originaltitle","year","genre","plotoutline","rating","votes","mpaa","runtime","studio","country","premiered","sorttitle","thumbnail","art","resume"]

Episodes — use VideoLibrary.GetEpisodes with:

["title","plotoutline","season","episode","showtitle","aired","runtime","rating","playcount","lastplayed","thumbnail","art","resume"]

TV shows — use VideoLibrary.GetTVShows with:

["title","originaltitle","year","genre","plotoutline","rating","studio","premiered","sorttitle","thumbnail","art"]
(No per-show resume here.)

Notes:

runtime is minutes (matches your list item’s duration).

resume gives you position & total (seconds) for movies/episodes.

Batch by page and cache for snappy scrolling.

5) Versioning rules you must follow (detect and branch)

You will detect the running Kodi version (or feature-detect the tag API) and branch your ListItem population.

Kodi v19 (Matrix, Python 3.8):

Use the classic info labels & setArt approach for the lightweight fields.

Resume in list view: set ListItem properties ResumeTime and TotalTime (seconds).

Do not call v20-only InfoTagVideo setters (those cause attribute errors on v19).

Kodi v20+:

You may set the same fields via the InfoTagVideo setters (or continue with the classic labels; keep the field set identical for a consistent look).

Resume in list view: set the InfoTagVideo resume point (time & totalTime, seconds).

Keep your v19 path in place for backward compatibility.

6) URL & container hygiene (for native feel)

Every item must have a non-empty URL.

Folders: plugin://…?action=…, isFolder = true, no IsPlayable.

Playable rows: final media URL or your plugin://play handler, isFolder = false, IsPlayable = "true".

Library-backed rows should use the videodb://… URL for that movie/episode (you’re still setting the lightweight fields and resume per above).

Before endOfDirectory, set the container content (movies, episodes, tvshows) so skins render the expected layouts and overlays.