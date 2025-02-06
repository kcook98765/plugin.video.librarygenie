
# Image Handling in Kodi Addon (LibraryGenie)

## Overview
This document details how images (posters, thumbnails, fanart, and cast photos) are collected, stored, and used in ListItems. The implementation accommodates different Kodi versions with specific handling for Kodi 19+ (Matrix) and later versions.

## Image Collection

### From JSON-RPC
Images are primarily collected through the JSON-RPC API using `VideoLibrary.GetMovieDetails` method. The relevant code is in `jsonrpc_manager.py`:

```python
params = {
    'properties': [
        'art',          # Contains all artwork types
        'thumbnail',    # Main thumbnail
        'fanart',      # Background image
        'cast'         # Cast info including photos
    ]
}
```

### From InfoLabels
As a fallback or alternative source, images are collected using Kodi's InfoLabels. The relevant code is in `media_manager.py`:

```python
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
```

### Cast Images
Cast member images are collected differently depending on the context:

1. From JSON-RPC:
```python
cast_list = details.get('cast', [])[:10]  # Limited to first 10 cast members
cast = [{
    'name': actor.get('name'),
    'role': actor.get('role'),
    'order': actor.get('order'),
    'thumbnail': actor.get('thumbnail')
} for actor in cast_list]
```

2. From InfoLabels:
```python
cast = []
for i in range(1, 11):  # Limited to 10 cast members
    name = xbmc.getInfoLabel(f'ListItem.CastAndRole.{i}.Name')
    if not name:
        break
    cast.append({
        'name': name,
        'role': xbmc.getInfoLabel(f'ListItem.CastAndRole.{i}.Role'),
        'order': i - 1,
        'thumbnail': xbmc.getInfoLabel(f'ListItem.CastAndRole.{i}.Thumb')
    })
```

## Storage

### Database Storage
Images are stored in the SQLite database as part of the media item data. The URLs are stored directly in the relevant fields:

- Posters/thumbnails in the `thumbnail` field
- Fanart in the `fanart` field
- Art dictionary as a JSON string containing all art types
- Cast member photos as part of the cast JSON string

## ListItem Building

### Version-Specific Handling

#### Kodi 19+ (Matrix and later)
In Kodi 19+, the InfoTagVideo class is used for setting video information:

```python
info_tag = listitem.getVideoInfoTag()
```

Art is set using the setArt method:
```python
art = {
    'poster': format_art(url) if url else '',
    'thumb': format_art(url) if url else '',
    'banner': format_art(url) if url else '',
    'fanart': format_art(url) if url else ''
}
list_item.setArt(art)
```

Cast is set using the InfoTag API:
```python
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
```

#### Kodi 18 and Earlier
For earlier versions, the traditional setInfo method is used:

```python
listitem.setInfo('video', {
    'title': title,
    'plot': plot,
    # ... other metadata
})
```

### Art Priority
When setting art for ListItems, the following priority is used:

1. Dedicated art field from the specific type (poster, thumb, etc.)
2. Art dictionary value for the specific type
3. Generic thumbnail as fallback
4. Empty string if no art is available

### URL Formatting
Image URLs are formatted before being set on ListItems:

```python
def format_art(url):
    """Format art URL for Kodi display"""
    if not url:
        return ''
    if url.startswith('image://'):
        return url
    return f'image://{quote(url)}/'
```

## Best Practices

1. Always check for NULL/empty values before setting art
2. Use proper URL encoding for image paths
3. Implement fallbacks for missing art types
4. Limit cast member processing to 10 members for performance
5. Log art-related operations for debugging
6. Use version-specific APIs for better compatibility

## Common Issues

1. Image protocols: Ensure URLs are properly formatted with 'image://' protocol
2. URL encoding: Special characters in paths must be properly encoded
3. Missing art: Implement fallbacks for missing art types
4. Cast thumbnails: Handle missing cast member photos gracefully
5. Version compatibility: Use appropriate API based on Kodi version

## Test Considerations

1. Test with various image URL formats
2. Verify handling of missing/corrupt images
3. Check memory usage with large cast lists
4. Validate version-specific code paths
5. Monitor database storage efficiency
