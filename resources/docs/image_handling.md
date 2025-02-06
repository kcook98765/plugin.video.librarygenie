# Image Handling in Kodi Addon (LibraryGenie)

This document describes how movie artwork—such as posters, thumbnails, fanart, banners, and cast images—is collected, stored, and applied to ListItems in Kodi. It covers two primary data sources (JSON‑RPC and InfoLabels) and explains how to set up images in Kodi’s ListItems. Specific details for Kodi 19 (Matrix), Kodi 20 (Nexus), and Kodi 21 are noted where relevant.

    Note:

        For movie items the primary artwork types are:
            Poster – the main cover image
            Thumb – a smaller version (often used as a preview)
            Fanart – background image used in the details view
            Banner – used in list displays or details (if available)
        In Kodi 20 and Kodi 21, additional artwork types (e.g. clearlogo, clearart, landscape) are supported. For movie handling the core types remain the same.
        Kodi 21 performs stricter URL validation; therefore, proper URL quoting/formatting is essential.

1. Image Collection

Artwork for movies is gathered from two main sources:
1.1. Via JSON‑RPC

Kodi’s JSON‑RPC API is the preferred method when available. Using the VideoLibrary.GetMovieDetails method (or similar endpoints) returns a details dictionary containing an "art" sub‑dictionary plus other keys such as "thumbnail" and "cast".

Example code snippet:

# Query parameters for JSON-RPC call
params = {
    'properties': [
        'art',       # Dictionary of artwork types (poster, thumb, fanart, banner, etc.)
        'thumbnail', # Main thumbnail (may be duplicated in 'art')
        'fanart',    # Background image
        'cast'       # Cast details including actor images
    ]
}

# Response example (simplified):
# details = {
#     'art': {
#         'poster': 'http://example.com/path/to/poster.jpg',
#         'thumb': 'http://example.com/path/to/thumb.jpg',
#         'fanart': 'http://example.com/path/to/fanart.jpg',
#         'banner': 'http://example.com/path/to/banner.jpg'
#     },
#     'thumbnail': 'http://example.com/path/to/thumbnail.jpg',
#     'cast': [
#         {'name': 'Actor One', 'role': 'Hero', 'order': 0, 'thumbnail': 'http://example.com/path/to/actor1.jpg'},
#         # ... up to however many cast members are provided
#     ]
# }

1.2. Via InfoLabels

When JSON‑RPC is unavailable or as a fallback, the addon can collect artwork from Kodi’s InfoLabels. This method reads predefined label keys that most skins populate.

Example code snippet:

info = {
    'thumbnail': xbmc.getInfoLabel('ListItem.Art(thumb)') or xbmc.getInfoLabel('ListItem.Art(poster)'),
    'fanart': xbmc.getInfoLabel('ListItem.Art(fanart)'),
    'art': {
        'poster': xbmc.getInfoLabel('ListItem.Art(poster)'),
        'thumb': xbmc.getInfoLabel('ListItem.Art(thumb)'),
        'fanart': xbmc.getInfoLabel('ListItem.Art(fanart)'),
        'banner': xbmc.getInfoLabel('ListItem.Art(banner)')
    }
}

1.3. Cast Images

Cast (actor) images are collected separately and, as with other artwork, may come from JSON‑RPC or InfoLabels.
1.3.1. From JSON‑RPC

The cast list is usually provided as an array in the movie details. Often it is wise to limit the number of cast members to avoid performance issues (e.g. first 10).

cast_list = details.get('cast', [])[:10]  # Limit to first 10 cast members
cast = [{
    'name': actor.get('name'),
    'role': actor.get('role'),
    'order': actor.get('order'),
    'thumbnail': actor.get('thumbnail')
} for actor in cast_list]

1.3.2. From InfoLabels

If relying on InfoLabels, iterate over a fixed range (e.g. 1–10):

cast = []
for i in range(1, 11):  # Limit to 10 cast members
    name = xbmc.getInfoLabel(f'ListItem.CastAndRole.{i}.Name')
    if not name:
        break
    cast.append({
        'name': name,
        'role': xbmc.getInfoLabel(f'ListItem.CastAndRole.{i}.Role'),
        'order': i - 1,
        'thumbnail': xbmc.getInfoLabel(f'ListItem.CastAndRole.{i}.Thumb')
    })

2. Storage

Once collected, image URLs (and the entire art dictionary) are stored in the addon’s SQLite database along with other media metadata. Common storage practices include:

    Poster/Thumbnail: Saved in the dedicated thumbnail field.
    Fanart: Saved in the fanart field.
    Art Dictionary: Stored as a JSON string containing various artwork types.
    Cast Images: Stored as part of the cast metadata JSON.

    Tip:
    Ensure that URLs are stored exactly as retrieved. Any necessary formatting (see below) is applied at display time.

3. ListItem Building and Version‑Specific Handling

Kodi ListItems are how media items (and their associated metadata) are passed to the GUI. How artwork is set depends on the Kodi version in use.
3.1. Kodi 19 (Matrix) and Later (Kodi 20 and Kodi 21)

Starting with Kodi 19, the new InfoTagVideo class is used to set video metadata. Both Kodi 19, 20, and 21 support the use of ListItem.setArt() and InfoTagVideo.setCast(). However, there are some version‑specific notes:

    Kodi 19 (Matrix):
    Introduced the InfoTagVideo API. All artwork should be set via ListItem.setArt(art) and cast via info_tag.setCast(actors).

    Kodi 20 (Nexus):
    Continues to use the InfoTagVideo API. Artwork handling remains similar to Kodi 19, but note that Kodi 20 may introduce improved caching and fallback behavior. Always ensure your image URLs are correctly formatted.

    Kodi 21:
    In Kodi 21 the APIs remain largely unchanged. However, Kodi 21 performs stricter validation of image URLs. It is important to URL‑encode and wrap your URLs with the image:// protocol if needed.

Example code for Kodi 19/20/21:

# Retrieve the InfoTagVideo from the listitem (Kodi 19+)
info_tag = listitem.getVideoInfoTag()

# Format the art dictionary (see Section 4 for details on format_art)
art = {
    'poster': format_art(art_dict.get('poster')) if art_dict.get('poster') else '',
    'thumb': format_art(art_dict.get('thumb')) if art_dict.get('thumb') else '',
    'banner': format_art(art_dict.get('banner')) if art_dict.get('banner') else '',
    'fanart': format_art(art_dict.get('fanart')) if art_dict.get('fanart') else ''
}
listitem.setArt(art)

# Build the cast list for the info tag
actors = []
for member in cast:
    actor = xbmc.Actor(
        name=str(member.get('name', '')),
        role=str(member.get('role', '')),
        order=int(member.get('order', 0)),
        thumbnail=str(member.get('thumbnail', ''))
    )
    actors.append(actor)
info_tag.setCast(actors)

    Best Practice:
    Even though Kodi 19+ provides enhanced APIs, always check that your artwork URLs are valid and non‑empty. In addition, when using the JSON‑RPC “art” dictionary, consider merging with any available InfoLabel values to provide a robust fallback mechanism.

3.2. Kodi 18 and Earlier

Older Kodi versions (Kodi 18 “Leia” and earlier) do not support the InfoTagVideo API. Instead, you must use the traditional setInfo() method and rely solely on the ListItem.setArt() method for artwork.

Example code:

listitem.setInfo('video', {
    'title': title,
    'plot': plot,
    # ... other metadata
})
# Artwork is set the same way, but no dedicated cast API is available.
listitem.setArt(art)

    Note:
    Since cast metadata (with thumbnails) is not automatically supported in Kodi 18 and earlier, consider whether to embed cast images elsewhere (or simply skip setting cast images).

4. URL Formatting for Artwork

Before setting an image URL on a ListItem, it should be formatted appropriately. In Kodi 20 and 21, where URL validation is stricter, you should ensure that:

    The URL is wrapped in Kodi’s image:// protocol if it is a normal HTTP/HTTPS URL.
    The URL is properly quoted to escape special characters.

Example formatting function:

from urllib.parse import quote  # For Python 3.x
# For Python 2.x, use: from urllib import quote

def format_art(url):
    """Format the given URL for Kodi display.

    - If the URL is empty, return an empty string.
    - If the URL already begins with 'image://', assume it is preformatted.
    - Otherwise, wrap it in the 'image://' protocol and URL‑quote it.
    """
    if not url:
        return ''
    if url.startswith('image://'):
        return url
    return f'image://{quote(url)}/'

5. Art Priority and Fallback Logic

When setting artwork on a ListItem, use the following priority:

    Dedicated Artwork Field:
    Use the artwork URL provided in the dedicated field (e.g. the "poster" field in the JSON "art" dictionary).

    Art Dictionary Fallback:
    If the dedicated field is empty, check for a corresponding value in the art dictionary (e.g. "thumb", "banner", or "fanart").

    Generic Thumbnail Fallback:
    If none of the above exist, fall back to a generic thumbnail obtained via InfoLabels.

    Empty String:
    If no image is available, set the value to an empty string so Kodi can handle it gracefully.

Implementing this logic when constructing your art dictionary helps ensure that the best available image is used for each role.
6. Summary and Recommendations

    Data Sources: Use JSON‑RPC as your primary source for artwork. Use InfoLabels as a fallback or supplement.
    Storage: Save artwork URLs (and the complete art dictionary) in your database for re‑use.
    ListItem Building:
        For Kodi 19 and later (including 20 and 21), use InfoTagVideo to set metadata and cast.
        For Kodi 18 and earlier, use setInfo() and setArt(), and note that cast images may not be fully supported.
    URL Formatting: Always format artwork URLs (especially in Kodi 20/21) using a dedicated function to ensure proper quoting and protocol wrapping.
    Testing Across Versions:
        Verify that artwork displays correctly in Kodi Matrix (19), Nexus (20), and Kodi 21.
        Test fallbacks (e.g. when JSON‑RPC artwork is missing, that InfoLabels or generic thumbnails are used).

By following these guidelines, your addon should reliably handle movie artwork across Kodi 19, 20, and 21 while taking advantage of newer APIs when available and maintaining backward compatibility.