Function: setArt(values)
Sets the listitem's art

Parameters
    values	dictionary - pairs of { label: value }.

        Some default art values (any string possible):
        Label 	Type
        thumb 	string - image filename
        poster 	string - image filename
        banner 	string - image filename
        fanart 	string - image filename
        clearart 	string - image filename
        clearlogo 	string - image filename
        landscape 	string - image filename
        icon 	string - image filename 

----------------------------
poster

Used in: Movie artwork Movie sets artwork Music Video artwork TV-Show artwork

Posters replicates the movie posters often seen in cinema complexes, or the front cover of home video releases, and contain a clearly visible logo or name of the video.
Image specifications
Name 	poster
Type 	jpg or png
Resolution 	1000w x 1500h
Aspect Ratio 	2:3
Transparent background 	No


-------------------------
In JSON‑RPC: When you call methods like VideoLibrary.GetMovieDetails or VideoLibrary.GetMovies (with the appropriate properties requested), the poster is found in the returned JSON under the art object, with the key "poster". For example:

{
    "movieid": 1,
    "label": "My Movie",
    "art": {
        "poster": "http://example.com/path/to/poster.jpg",
        "fanart": "http://example.com/path/to/fanart.jpg"
        // ... other artwork types
    }
    // ... other properties
}

In ListItems: When dealing with list items (for instance, when you retrieve items from a video playlist or similar), you now access the poster via the item’s art dictionary. In many cases you can use a method like ListItem.getArt('poster') (or access the art object directly) to get the URL for the poster image.
