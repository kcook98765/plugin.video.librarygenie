# Kodi Addon API Integration Guide

This document provides complete API documentation for developing Kodi addons that integrate with the search-api service.

## Base URL and Authentication

### Base URL
```
https://your-server.com/
```

### Authentication Methods

The API supports two authentication methods:

1. **API Key Authentication** (Recommended for Kodi)
   ```
   Authorization: ApiKey YOUR_64_CHARACTER_API_KEY
   ```

2. **Session Authentication** (Browser-based)
   - Uses Auth0 session cookies (not suitable for Kodi)

## Kodi Addon Integration Flow

### Method 1: Easy Pairing (Recommended)

1. **User generates pairing code** via web dashboard
2. **Kodi addon prompts user** for 8-digit pairing code
3. **Addon exchanges code** for API key automatically
4. **Addon stores API key** for future requests

### Method 2: Manual Setup

1. **User copies API key** from web dashboard
2. **User manually enters** API key in Kodi addon settings
3. **User manually sets** server URL in addon settings

## API Endpoints for Kodi Integration

### 1. Exchange Pairing Code (Setup)

**Endpoint:** `POST /pairing-code/exchange`  
**Authentication:** None (public endpoint)  
**Purpose:** Exchange 8-digit pairing code for API key

**Request:**
```json
{
  "pairing_code": "12345678"
}
```

**Success Response (200):**
```json
{
  "success": true,
  "api_key": "abc123...xyz789",
  "user_email": "user@example.com",
  "server_url": "https://your-server.com/api",
  "message": "Pairing successful - your Kodi addon is now configured"
}
```

**Error Responses:**
```json
// Invalid code
{
  "success": false,
  "error": "Invalid pairing code"
}

// Expired/used code
{
  "success": false,
  "error": "Pairing code has expired or been used"
}
```

### 2. Test Connection

**Endpoint:** `GET /kodi/test`  
**Authentication:** Required (API Key)  
**Purpose:** Verify API key works and connection is established

**Headers:**
```
Authorization: ApiKey YOUR_API_KEY
```

**Success Response (200):**
```json
{
  "status": "success",
  "message": "API key authentication successful",
  "user": {
    "email": "user@example.com",
    "role": "user",
    "is_active": true
  },
  "service": "search-api",
  "kodi_ready": true
}
```

**Error Response (401):**
```json
{
  "error": "Invalid or missing API key"
}
```

### 3. Search Movies (Future Endpoint)

**Endpoint:** `POST /api/search/movies`  
**Authentication:** Required (API Key)  
**Purpose:** Search for movies in the database

**Request:**
```json
{
  "query": "inception",
  "limit": 20,
  "offset": 0,
  "filters": {
    "year_min": 2000,
    "year_max": 2023,
    "genre": "sci-fi"
  }
}
```

**Response:**
```json
{
  "success": true,
  "results": [
    {
      "id": "tt1375666",
      "title": "Inception",
      "year": 2010,
      "poster_url": "https://image.tmdb.org/...",
      "overview": "A thief who steals...",
      "rating": 8.8,
      "genres": ["Action", "Sci-Fi", "Thriller"]
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

### 4. Get Movie Details (Future Endpoint)

**Endpoint:** `GET /api/movies/{imdb_id}`  
**Authentication:** Required (API Key)  
**Purpose:** Get detailed information about a specific movie

**Response:**
```json
{
  "success": true,
  "movie": {
    "id": "tt1375666",
    "title": "Inception",
    "year": 2010,
    "runtime": 148,
    "plot": "A thief who steals corporate secrets...",
    "director": "Christopher Nolan",
    "cast": [
      {
        "name": "Leonardo DiCaprio",
        "character": "Dom Cobb",
        "profile_url": "https://image.tmdb.org/..."
      }
    ],
    "genres": ["Action", "Sci-Fi", "Thriller"],
    "rating": 8.8,
    "poster_url": "https://image.tmdb.org/...",
    "backdrop_url": "https://image.tmdb.org/...",
    "trailer_url": "https://youtube.com/...",
    "ai_analysis": {
      "plot_summary": "Complex narrative about...",
      "mood_tone": "Dark, mysterious, thought-provoking",
      "themes": ["Reality vs dreams", "Memory", "Guilt"],
      "genre_tropes": ["Mind bending", "Heist movie", "Multiple timelines"]
    }
  }
}
```

### 5. Get Similar Movies (Future Endpoint)

**Endpoint:** `GET /api/movies/{imdb_id}/similar`  
**Authentication:** Required (API Key)  
**Purpose:** Get movies similar to the specified movie using AI embeddings

**Response:**
```json
{
  "success": true,
  "similar_movies": [
    {
      "id": "tt0816692",
      "title": "Interstellar", 
      "similarity_score": 0.89,
      "poster_url": "https://image.tmdb.org/...",
      "year": 2014,
      "rating": 8.6
    }
  ]
}
```

### 6. User Activity Logging (Future Endpoint)

**Endpoint:** `POST /api/activity/log`  
**Authentication:** Required (API Key)  
**Purpose:** Log user activity for analytics

**Request:**
```json
{
  "action": "movie_viewed",
  "movie_id": "tt1375666",
  "duration_seconds": 120,
  "kodi_version": "20.0",
  "addon_version": "1.0.0"
}
```

## Error Handling

### Standard HTTP Status Codes

- **200**: Success
- **400**: Bad Request (missing/invalid parameters)
- **401**: Unauthorized (invalid/missing API key)
- **404**: Not Found (resource doesn't exist)
- **429**: Too Many Requests (rate limiting)
- **500**: Internal Server Error

### Error Response Format

All error responses follow this format:
```json
{
  "success": false,
  "error": "Description of the error",
  "error_code": "OPTIONAL_ERROR_CODE"
}
```

## Rate Limiting

- **Search requests**: 60 per minute per API key
- **Detail requests**: 120 per minute per API key  
- **Test/health checks**: 10 per minute per API key

## Kodi Addon Implementation Guidelines

### 1. Configuration Storage

Store these settings in Kodi addon settings:
```python
# Settings
server_url = addon.getSetting('server_url')
api_key = addon.getSetting('api_key')
pairing_code = addon.getSetting('pairing_code')  # Temporary
```

### 2. Initial Setup Flow

```python
def setup_addon():
    # Check if already configured
    if addon.getSetting('api_key'):
        return test_connection()
    
    # Prompt for pairing code
    pairing_code = xbmcgui.Dialog().input('Enter pairing code from website:')
    
    if pairing_code:
        return exchange_pairing_code(pairing_code)
    
    return False

def exchange_pairing_code(code):
    response = requests.post(f'{BASE_URL}/pairing-code/exchange', 
                           json={'pairing_code': code})
    
    if response.status_code == 200:
        data = response.json()
        addon.setSetting('api_key', data['api_key'])
        addon.setSetting('server_url', data['server_url'])
        return True
    
    return False
```

### 3. API Request Helper

```python
def make_api_request(endpoint, method='GET', data=None):
    headers = {
        'Authorization': f"ApiKey {addon.getSetting('api_key')}",
        'Content-Type': 'application/json'
    }
    
    url = f"{addon.getSetting('server_url')}/{endpoint}"
    
    if method == 'GET':
        response = requests.get(url, headers=headers)
    elif method == 'POST':
        response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 401:
        # API key invalid - prompt for reconfiguration
        reconfigure_addon()
        return None
    
    return response.json() if response.status_code == 200 else None
```

### 4. Connection Testing

```python
def test_connection():
    response = make_api_request('kodi/test')
    return response and response.get('kodi_ready', False)
```

## Future API Endpoints (Planned)

These endpoints are planned for future implementation:

- `GET /api/movies/trending` - Get trending movies
- `GET /api/movies/random` - Get random movie recommendations  
- `POST /api/favorites/add` - Add movie to user favorites
- `GET /api/favorites` - Get user's favorite movies
- `POST /api/watchlist/add` - Add movie to watchlist
- `GET /api/collections` - Get movie collections/franchises
- `GET /api/stats/user` - Get user viewing statistics
- `POST /api/ratings/submit` - Submit user rating for movie

## Support and Debugging

### Debug Mode

Enable debug logging in your Kodi addon to capture API responses:

```python
import xbmc

def log_debug(message):
    if addon.getSetting('debug_mode') == 'true':
        xbmc.log(f"[MovieSearch] {message}", xbmc.LOGDEBUG)
```

### Common Issues

1. **401 Unauthorized**: API key expired or invalid
   - Solution: Regenerate API key or re-pair addon

2. **404 Not Found**: Movie not in database
   - Solution: Check IMDb ID format, request movie addition

3. **429 Rate Limited**: Too many requests
   - Solution: Implement request throttling in addon

### Contact

For Kodi addon development support, contact your system administrator with:
- API request/response logs
- Kodi version and addon version
- Specific error messages or behavior