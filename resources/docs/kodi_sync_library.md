### IGNORE THIS FILE FOR NOW ###


Would need these sqlite tables setup:

CREATE TABLE movies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path   TEXT,   -- e.g., "smb://192.168.2.102/plex/Movies/"
    file_name   TEXT,   -- e.g., "Freaks (2018).mp4"
    movieid     INTEGER, -- Kodi library movie ID (if available)
    imdbnumber  TEXT,   -- Use the "imdbnumber" field; if blank, try uniqueid.imdb; else NULL
    tmdbnumber  TEXT,   -- Taken from uniqueid.tmdb (if available); else NULL
    tvdbnumber  TEXT,   -- Taken from uniqueid.tvdb (if available); else NULL
    addon_file  TEXT,   -- For non‑library entries (from ListItem.FilenameAndPath)
    source      TEXT NOT NULL CHECK(source IN ('Lib','File'))
);

-- For library entries ("Lib"): combination of file_path and file_name must be unique.
CREATE UNIQUE INDEX idx_movies_lib_unique
    ON movies(file_path, file_name)
    WHERE source = 'Lib';

-- For non-library (addon) entries ("File"): addon_file must be unique.
CREATE UNIQUE INDEX idx_movies_file_unique
    ON movies(addon_file)
    WHERE source = 'File';


CREATE TABLE addon_metadata (
    movie_id    INTEGER PRIMARY KEY,  -- References movies(id)
    filename    TEXT,    -- xbmc.getInfoLabel('ListItem.FilenameAndPath')
    title       TEXT,    -- sys.listitem.getLabel()
    duration    INTEGER, -- sys.listitem.getProperty('duration')
    rating      REAL,    -- videoInfoTag.getRating()
    year        INTEGER, -- videoInfoTag.getYear()
    date        TEXT,    -- videoInfoTag.getPremiered()
    plot        TEXT,    -- videoInfoTag.getPlot()
    plotoutline TEXT,    -- videoInfoTag.getPlotOutline()
    thumb       TEXT,    -- sys.listitem.getArt('thumb')
    poster      TEXT,    -- sys.listitem.getArt('poster')
    fanart      TEXT,    -- sys.listitem.getArt('fanart')
    banner      TEXT,    -- sys.listitem.getArt('banner')
    clearart    TEXT,    -- sys.listitem.getArt('clearart')
    clearlogo   TEXT,    -- sys.listitem.getArt('clearlogo')
    landscape   TEXT,    -- sys.listitem.getArt('landscape')
    icon        TEXT,    -- sys.listitem.getArt('icon')
    FOREIGN KEY(movie_id) REFERENCES movies(id) ON DELETE CASCADE
);


1) Need a process that can:
1A) run jsonRpc :
```http://192.168.2.7:8080/jsonrpc?request={
  "jsonrpc": "2.0",
  "method": "VideoLibrary.GetMovies",
  "params": {
    "properties": [
      "title",
      "year",
      "file",
      "imdbnumber",
      "uniqueid"
    ]
  },
  "id": 1
}``` (possibly "paginate, as could be very large 10k+ entries)
2) sync (store/update/remove) the data in "movies" table for all "source" = "Lib" so that it aligns with kodi library, but do not touch "source" "File" entries.
