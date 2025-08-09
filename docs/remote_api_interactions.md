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

### 3. Search Movies (Kodi Endpoint)

**Endpoint:** `POST /kodi/search/movies`  
**Authentication:** Required (API Key)  
**Purpose:** Search for movies using MediaVault's semantic search system

**Description:**
This endpoint uses the same advanced search process as MediaVault:
1. **Embedding Generation**: Your search query is converted to a vector using OpenAI's text-embedding-3-small model
2. **Semantic Search**: The vector is used to search against 4 embedding facets stored in OpenSearch:
   - Plot vectors (40% weight)
   - Mood/tone vectors (30% weight)  
   - Theme vectors (20% weight)
   - Genre/trope vectors (10% weight)
3. **Similarity Scoring**: Results are ranked by semantic similarity scores

**Request:**
```json
{
  "query": "psychological thriller with mind bending plot twists",
  "limit": 50
}
```

**Response:**
```json
{
  "success": true,
  "query": "psychological thriller with mind bending plot twists",
  "total_results": 15,
  "results": [
    {
      "imdb_id": "tt1375666",
      "score": 0.924
    },
    {
      "imdb_id": "tt0816692", 
      "score": 0.887
    },
    {
      "imdb_id": "tt0468569",
      "score": 0.863
    }
  ]
}
```

**Parameters:**
- `query` (required): Natural language search query describing the movie you want
- `limit` (optional): Maximum number of results (default: 20, max: 100)

**Response Format:**
- `success`: Boolean indicating if search succeeded
- `query`: The original search query  
- `total_results`: Number of results returned
- `results`: Array of objects containing:
  - `imdb_id`: IMDb identifier (e.g., "tt1375666")
  - `score`: Semantic similarity score (0.0 to 1.0, higher is better match)

**Error Response:**
```json
{
  "success": false,
  "error": "Search query required",
  "results": []
}
```

### 4. Start Batch Upload Session

**Endpoint:** `POST /library/batch/start`  
**Authentication:** Required (API Key)  
**Purpose:** Start a chunked movie upload session with resumability

**Request:**
```json
{
  "mode": "merge",
  "total_count": 1234,
  "source": "kodi"
}
```

**Parameters:**
- `mode` (optional): "merge" (default) or "replace"
  - **"merge"**: Adds to existing collection (preserves existing items)
  - **"replace"**: Authoritative replacement (removes items not in this upload)
- `total_count` (required): Total number of movies to upload
- `source` (optional): Upload source identifier (default: "kodi")

**Limits:**
- Maximum 10,000 movies per user
- Mode "merge": Current collection + new items ≤ 10,000

**Success Response (200):**
```json
{
  "success": true,
  "upload_id": "u_abc123-456-789",
  "max_chunk": 1000
}
```

### 5. Upload Movie Chunk  

**Endpoint:** `PUT /library/batch/{upload_id}/chunk`  
**Authentication:** Required (API Key)  
**Purpose:** Upload a chunk of movies to an active batch session

**Headers:**
```
Idempotency-Key: <uuid-per-chunk>
```

**Request:**
```json
{
  "chunk_index": 0,
  "items": [
    {"imdb_id": "tt1234567"},
    {"imdb_id": "tt7654321"}
  ]
}
```

**Parameters:**
- `chunk_index` (required): 0-based chunk sequence number
- `items` (required): Array of movie objects
  - `imdb_id` (required): Valid IMDb ID (tt format) - must be provided and valid

**Validation:**
- Only valid IMDb IDs are accepted (format: `tt` + digits)
- Items without valid IMDb IDs will be marked as `invalid`
- No ID resolution or title/year lookup is supported

**Success Response (200):**
```json
{
  "success": true,
  "chunk_index": 0,
  "items_processed": 500,
  "results": {
    "accepted": 495,
    "invalid": 2,
    "duplicates": 3
  },
  "item_details": [
    {"imdb_id": "tt1234567", "status": "accepted"},
    {"imdb_id": "tt7654321", "status": "duplicate"}
  ],
  "status": "processed"
}
```

### 6. Commit Batch Session

**Endpoint:** `POST /library/batch/{upload_id}/commit`  
**Authentication:** Required (API Key)  
**Purpose:** Finalize the batch upload and apply changes

**Success Response (200):**
```json
{
  "success": true,
  "upload_id": "u_abc123-456-789", 
  "mode": "replace",
  "final_tallies": {
    "accepted": 1498,
    "duplicates": 0,
    "invalid": 2
  },
  "user_movie_count": 1498,
  "chunks_processed": 3,
  "removed_count": 150
}
```

### 7. Get Batch Status

**Endpoint:** `GET /library/batch/{upload_id}/status`  
**Authentication:** Required (API Key)  
**Purpose:** Check upload session status and progress

**Success Response (200):**
```json
{
  "success": true,
  "upload_id": "u_abc123-456-789",
  "status": "active",
  "mode": "replace", 
  "total_count": 1500,
  "chunks_received": 2,
  "processed_chunks": [0, 1],
  "stats": {
    "accepted": 995,
    "duplicates": 3,
    "invalid": 2
  },
  "started_at": "2025-08-09T00:30:00",
  "committed_at": null
}
```

### 8. Get Library Hash (Delta Sync)

**Endpoint:** `GET /library/hash`  
**Authentication:** Required (API Key)  
**Purpose:** Get collection fingerprints for efficient delta synchronization

**Success Response (200):**
```json
{
  "success": true,
  "count": 1498,
  "fingerprints": ["a1b2c3d4", "e5f6g7h8", "..."]
}
```



### 9. Get Movie List

**Endpoint:** `GET /kodi/movies/list`  
**Authentication:** Required (API Key)  
**Purpose:** Retrieve user's current movie list with pagination

**Query Parameters:**
- `page` (optional): Page number (default: 1)
- `per_page` (optional): Items per page (default: 100, max: 1000)

**Success Response (200):**
```json
{
  "success": true,
  "movies": ["tt1234567", "tt7654321", "tt9876543"],
  "pagination": {
    "page": 1,
    "pages": 15,
    "per_page": 100,
    "total": 1498,
    "has_next": true,
    "has_prev": false
  },
  "user_movie_count": 1498
}
```

### 10. Get Batch History

**Endpoint:** `GET /kodi/movies/batches`  
**Authentication:** Required (API Key)  
**Purpose:** Get user's movie upload batch history

**Success Response (200):**
```json
{
  "success": true,
  "batches": [{
    "batch_id": "uuid-1234-5678-9abc",
    "batch_type": "replace",
    "status": "completed",
    "total_movies": 1500,
    "successful_imports": 1498,
    "failed_imports": 2,
    "started_at": "2025-08-09T00:30:00",
    "completed_at": "2025-08-09T00:31:15"
  }]
}
```

### 11. Clear Movie List

**Endpoint:** `DELETE /kodi/movies/clear`  
**Authentication:** Required (API Key)  
**Purpose:** Clear user's entire movie list

**Success Response (200):**
```json
{
  "success": true,
  "message": "Cleared 1498 movies from your list",
  "deleted_count": 1498
}
```

### 12. Get Similar Movies (Future Endpoint)

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
    elif method == 'DELETE':
        response = requests.delete(url, headers=headers)
    
    if response.status_code == 401:
        # API key invalid - prompt for reconfiguration
        reconfigure_addon()
        return None
    
    return response.json() if response.status_code == 200 else None
```

### 4. Chunked Movie Collection Upload

```python
import uuid
import math

def chunked_movie_upload(movie_list, mode='merge', chunk_size=500):
    """Upload user's movie collection using chunked batch upload"""
    
    # Step 1: Start batch session
    session = make_api_request('library/batch/start', 'POST', {
        'mode': mode,
        'total_count': len(movie_list),
        'source': 'kodi'
    })
    
    if not session or not session.get('success'):
        return {'success': False, 'error': 'Failed to start batch session'}
    
    upload_id = session['upload_id']
    max_chunk = session['max_chunk']
    effective_chunk_size = min(chunk_size, max_chunk)
    
    # Step 2: Split into chunks and upload
    chunks = [movie_list[i:i + effective_chunk_size] 
              for i in range(0, len(movie_list), effective_chunk_size)]
    
    failed_chunks = []
    
    for chunk_index, chunk in enumerate(chunks):
        idempotency_key = str(uuid.uuid4())
        
        # Format items for API - only IMDb IDs accepted
        items = []
        for movie in chunk:
            if isinstance(movie, str):
                # Just IMDb ID
                items.append({'imdb_id': movie})
            elif isinstance(movie, dict) and 'imdb_id' in movie:
                # Movie object - extract only the IMDb ID  
                items.append({'imdb_id': movie['imdb_id']})
            else:
                # Skip invalid items - only valid IMDb IDs accepted
                continue
        
        # Upload chunk with retry logic
        success = False
        for attempt in range(3):  # 3 retry attempts
            try:
                headers = {'Idempotency-Key': idempotency_key}
                result = make_api_request_with_headers(
                    f'library/batch/{upload_id}/chunk',
                    'PUT',
                    {
                        'chunk_index': chunk_index,
                        'items': items
                    },
                    headers
                )
                
                if result and result.get('success'):
                    success = True
                    break
                    
            except Exception as e:
                time.sleep(2 ** attempt)  # Exponential backoff
        
        if not success:
            failed_chunks.append(chunk_index)
    
    # Step 3: Commit the batch
    if not failed_chunks:
        commit_result = make_api_request(
            f'library/batch/{upload_id}/commit', 'POST'
        )
        
        if commit_result and commit_result.get('success'):
            return {
                'success': True,
                'upload_id': upload_id,
                'final_tallies': commit_result['final_tallies'],
                'user_movie_count': commit_result['user_movie_count']
            }
    
    return {
        'success': False,
        'upload_id': upload_id,
        'failed_chunks': failed_chunks,
        'error': 'Some chunks failed to upload'
    }

def make_api_request_with_headers(endpoint, method, data, headers=None):
    """Enhanced API request helper with custom headers"""
    base_headers = {
        'Authorization': f"ApiKey {addon.getSetting('api_key')}",
        'Content-Type': 'application/json'
    }
    
    if headers:
        base_headers.update(headers)
    
    url = f"{addon.getSetting('server_url')}/{endpoint}"
    
    if method == 'PUT':
        response = requests.put(url, headers=base_headers, json=data)
    elif method == 'POST':
        response = requests.post(url, headers=base_headers, json=data)
    elif method == 'GET':
        response = requests.get(url, headers=base_headers)
    elif method == 'DELETE':
        response = requests.delete(url, headers=base_headers)
    
    return response.json() if response.status_code == 200 else None

def delta_sync_movies():
    """Efficient delta sync using library fingerprints"""
    # Get current server fingerprints
    server_hash = make_api_request('library/hash')
    if not server_hash or not server_hash.get('success'):
        return full_sync_movies()
    
    server_fingerprints = set(server_hash['fingerprints'])
    
    # Get local movie collection
    local_movies = get_user_movie_collection()
    local_fingerprints = set()
    
    import hashlib
    for movie in local_movies:
        imdb_id = movie['imdb_id'] if isinstance(movie, dict) else movie
        hash_obj = hashlib.sha1(imdb_id.encode())
        local_fingerprints.add(hash_obj.hexdigest()[:8])
    
    # Find movies to upload (not on server)
    new_fingerprints = local_fingerprints - server_fingerprints
    
    if not new_fingerprints:
        return {'success': True, 'message': 'Collection already up to date'}
    
    # Filter movies to upload
    movies_to_upload = []
    for movie in local_movies:
        imdb_id = movie['imdb_id'] if isinstance(movie, dict) else movie
        hash_obj = hashlib.sha1(imdb_id.encode())
        if hash_obj.hexdigest()[:8] in new_fingerprints:
            movies_to_upload.append(movie)
    
    # Upload only new movies
    return chunked_movie_upload(movies_to_upload, mode='merge')

def full_sync_movies():
    """Full collection sync (authoritative replacement)"""
    user_collection = get_user_movie_collection()
    return chunked_movie_upload(user_collection, mode='replace')

def get_upload_status(upload_id):
    """Check status of an ongoing upload"""
    return make_api_request(f'library/batch/{upload_id}/status')
```

### 4. Connection Testing

```python
def test_connection():
    response = make_api_request('kodi/test')
    return response and response.get('kodi_ready', False)
```


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