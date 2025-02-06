Kodi Artwork Management and setArt() Usage

Compatible with Kodi 19 (Matrix), Kodi 20 (Nexus), and Kodi 21 (Omega)
Overview

Kodi allows developers to enrich ListItems with artwork using the setArt() method. This method accepts a dictionary of artwork values where each key corresponds to a type of image (e.g., poster, fanart, thumb). The same API and artwork keys are supported in Kodi 19, 20, and 21.
The setArt() Function

Definition:

ListItem.setArt(values)

Parameters:

    values (dictionary): A mapping of artwork keys to image locations. The keys include:
        thumb: string – image filename or URL.
        poster: string – image filename or URL.
        banner: string – image filename or URL.
        fanart: string – image filename or URL.
        clearart: string – image filename or URL.
        clearlogo: string – image filename or URL.
        landscape: string – image filename or URL.
        icon: string – image filename or URL.

Note: Values can be either local file paths or web URLs. When using URLs, it’s common practice to wrap them with the image:// protocol to ensure Kodi processes the image correctly.
Artwork Types and Their Uses
Poster

    Usage:
    Used for movie artwork, music video artwork, and TV-show artwork. The poster image replicates a movie poster or DVD cover—featuring a clearly visible title or logo.

    Specifications:
        Name: poster
        Type: jpg or png
        Resolution: Approximately 1000w x 1500h
        Aspect Ratio: 2:3
        Transparent Background: No

Fanart and Others

    Fanart: Often used as a background image for media.
    Thumb, Banner, Clearart, Clearlogo, Landscape, Icon: These keys allow you to provide alternative images or thumbnails in different contexts within the Kodi UI.

Code Snippets
Example: Setting Artwork in a ListItem

Below is an example of how to create a ListItem with properly formatted artwork. This example includes a helper function to wrap image URLs with the image:// prefix if needed.

from urllib.parse import quote
import xbmcgui

def format_art(url):
    """
    Wraps a URL with the 'image://' protocol if it is not already wrapped.
    Returns an empty string if the URL is not provided.
    """
    if not url:
        return ''
    if not url.startswith('image://'):
        return f'image://{quote(url)}/'
    return url

# Create a ListItem for a movie
list_item = xbmcgui.ListItem(label="Example Movie")

# Define artwork using a dictionary.
art = {}

# Set poster: Try using a dedicated poster URL
poster_url = "http://example.com/path/to/poster.jpg"
art['poster'] = format_art(poster_url)
art['thumb'] = format_art(poster_url)
art['icon']  = format_art(poster_url)

# Optionally, set fanart
fanart_url = "http://example.com/path/to/fanart.jpg"
art['fanart'] = format_art(fanart_url)

# Assign the artwork dictionary to the ListItem
list_item.setArt(art)

Accessing Artwork in a ListItem

Once the artwork is set, you can retrieve any image URL by key:

poster = list_item.getArt('poster')
print("Poster URL:", poster)

JSON‑RPC Example: Retrieving Artwork Information

When querying Kodi’s video library via JSON‑RPC, artwork is returned under the art object. For instance:

{
    "movieid": 1,
    "label": "My Movie",
    "art": {
        "poster": "http://example.com/path/to/poster.jpg",
        "fanart": "http://example.com/path/to/fanart.jpg",
        "thumb": "http://example.com/path/to/thumb.jpg"
        // ... additional artwork types
    }
    // ... other movie properties
}

This JSON response can be parsed in your add-on to display the correct images.
Compatibility Across Kodi Versions

The artwork API has not undergone significant changes between Kodi 19, 20, and 21. Here’s what you need to know for each version:

    Kodi 19 (Matrix):
    The setArt() method and artwork keys (poster, fanart, etc.) work as described. Both local file paths and URLs (wrapped with image://) are supported.

    Kodi 20 (Nexus):
    There are no changes to the way artwork is handled compared to Kodi 19. The same practices and code snippets apply.

    Kodi 21 (Omega):
    The artwork API remains consistent. Developers can confidently use the same methods for setting and retrieving artwork as in earlier versions.

Conclusion

This document outlines how to work with Kodi’s artwork system using the setArt() function. The following points summarize the key practices:

    Use a helper function (like format_art()) to ensure URLs are correctly wrapped.
    Assign artwork keys such as poster, fanart, and thumb consistently across your add-on.
    Access artwork via JSON‑RPC or ListItem methods without worrying about version differences, as the API has remained stable across Kodi 19, 20, and 21.

By following these guidelines and using the provided code snippets, you can ensure that your media’s artwork displays correctly in Kodi’s GUI regardless of the version.
