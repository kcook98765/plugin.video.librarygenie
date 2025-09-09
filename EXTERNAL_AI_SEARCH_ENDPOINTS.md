# Kodi Addon API Integration Guide

This document provides complete API documentation for developing Kodi addons that integrate with the search-api service.

## Base URL and Authentication

### Base URL
```
Search API Service: https://your-server.com:5020/
```

**Important:** All documented endpoints run on the **search-api service** (port 5020)

### User Authentication System

The system uses **Auth0** for secure user authentication with a Kodi-friendly pairing process:

**For Users (Web Browser):**
1. Users visit the MediaVault web interface 
2. Click "Sign In" and authenticate via Auth0 (passwordless email login)
3. Auth0 creates a secure user session with role-based permissions
4. Users can generate pairing codes or view API keys from their dashboard

**For Kodi Addons:**
- Use API key authentication (Auth0 sessions don't work in Kodi)
- Obtain API keys through pairing codes or manual setup
- All requests require: `Authorization: ApiKey YOUR_64_CHARACTER_API_KEY`

### Integration Methods for Kodi

**Method 1: Pairing Code Flow (Recommended)**

This is the user-friendly approach for non-technical users:

1. **User authenticates** with Auth0 in web browser
2. **User generates 8-digit pairing code** from their dashboard 
3. **Kodi addon prompts** user to enter the pairing code
4. **Addon exchanges** pairing code for permanent API key via `/pairing-code/exchange`
5. **Addon stores** API key securely for future requests

Benefits: Simple setup, no manual copying of long API keys, secure token exchange

**Method 2: Manual API Key Setup**

For advanced users who prefer direct configuration:

1. **User authenticates** with Auth0 in web browser
2. **User copies full API key** from dashboard settings
3. **User manually enters** API key in Kodi addon settings
4. **User configures** server URL in addon settings

Benefits: Direct control, works offline after initial setup

### Auth0 Integration Notes

- **User Roles**: Auth0 manages user permissions (admin/user roles)
- **Session Management**: Web interface uses Auth0 sessions; Kodi uses derived API keys
- **Security**: API keys inherit user permissions from Auth0 account
- **Account Linking**: Each API key is permanently linked to a specific Auth0 user account

### Error Handling for Kodi Addons

**Authentication Errors:**
- `401 Unauthorized` - API key invalid/expired, prompt user to re-pair
- `403 Forbidden` - User lacks permissions for endpoint
- `429 Too Many Requests` - Implement exponential backoff retry

**Connection Errors:**
- Network timeouts - Retry with exponential backoff
- Server unavailable - Show user-friendly error, suggest checking server status
- Invalid server URL - Validate URL format before making requests

**Best Practices for Addon Development:**
- Store API keys securely in Kodi addon settings (encrypted if possible)
- Cache server URL and validate format (https://domain.com)
- Implement graceful degradation when search API is unavailable
- Show clear progress indicators for long operations (batch uploads)
- Provide meaningful error messages to users
- Test with both admin and regular user accounts

### Development Testing

**Local Testing:**
```python
# Test API connectivity (Kodi 19+ with Python 3)
import xbmc
import xbmcaddon
import urllib.request
import urllib.error

def test_api_connection(server_url, api_key):
    try:
        request = urllib.request.Request(f"{server_url}/")
        request.add_header("Authorization", f"ApiKey {api_key}")
        response = urllib.request.urlopen(request, timeout=10)
        if response.getcode() == 200:
            xbmc.log("API connection successful", xbmc.LOGINFO)
            return True
    except Exception as e:
        xbmc.log(f"API connection failed: {str(e)}", xbmc.LOGERROR)
        return False
```

**Production Considerations:**
- Always use HTTPS in production
- Validate all user inputs before sending to API
- Handle network timeouts gracefully (30+ second operations)
- Cache movie search results locally when appropriate
- Respect rate limits and implement backoff strategies
- Target Kodi 19+ (Python 3) - no backward compatibility needed

### Typical Kodi Addon Workflow

**1. Initial Setup (First Run)**
```
User Setup → Auth0 Login → Generate Pairing Code → Kodi Entry → API Key Exchange → Store Credentials
```

**2. Library Sync (Periodic)**
```
Scan Kodi Library → Extract IMDb IDs → Check Delta with /library/hash → Upload Movies via Main API Batch → Monitor Progress
```

**3. Movie Search (User-Initiated)**
```
User Search Query → /kodi/search/movies → Filter by User's Library → Present Results → User Selection
```

**4. Error Recovery**
```
API Errors → Check Connectivity → Validate API Key → Re-pair if Needed → Retry Operation
```

### Key Integration Points

**Authentication Flow:**
- Auth0 handles user identity and permissions in web browser
- Pairing codes bridge the gap between Auth0 sessions and Kodi API keys
- API keys provide stateless authentication for all Kodi requests

**Data Synchronization:**
- Use delta sync (`/library/hash`) to minimize bandwidth on subsequent runs
- Chunked uploads ensure reliability for large movie collections
- Idempotency keys prevent duplicate processing during retries

**Search Integration:**
- Search results are filtered by user's uploaded movie collection
- Results include similarity scores for ranking/presentation
- Search operates on AI-generated embeddings for semantic matching

## API Endpoints for Kodi Integration

### 🚨 **CRITICAL: API Selection Guide**

**FOR REPLACE-SYNC (Complete Library Replacement):**
Use **MAIN API ONLY** (endpoints 4-8 below). Do NOT mix with V1 API.

✅ **CORRECT Replace-Sync Flow:**
```
1. POST /library/batch/start (mode: "replace")
2. PUT /library/batch/{upload_id}/chunk (multiple calls)  
3. POST /library/batch/{upload_id}/commit (REQUIRED!)
```

❌ **INCORRECT - Will NOT Work:**
```
1. POST /library/batch/start (mode: "replace") 
2. POST /v1/library/add (Wrong API!)
3. [No commit - replace-sync never happens]
```

**FOR SIMPLE ADD/REMOVE (Individual Movies):**
Use **Main API** with batch size of 1 for individual operations.

**Key Rules:**
- **All operations use Main API consistently**
- **Individual operations = batch size of 1**  
- **Collections = larger batches with chunked upload**

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
  "server_url": "https://your-server.com",
  "message": "Pairing successful - your Kodi addon is now configured"
}
```

**Error Responses:**
```json
// Missing JSON data
{
  "success": false,
  "error": "JSON data required"
}

// Missing pairing code
{
  "success": false,
  "error": "Pairing code required"
}

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
  "max_score": 0.924,
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
- `max_score`: Highest similarity score in the result set
- `results`: Array of objects containing:
  - `imdb_id`: IMDb identifier (e.g., "tt1375666")
  - `score`: Semantic similarity score (0.0 to 1.0, higher is better match)

**Error Responses:**
```json
// Missing query
{
  "success": false,
  "error": "Search query required",
  "results": []
}

// Service unavailable
{
  "success": false,
  "error": "Search service not available",
  "results": []
}

// Internal error
{
  "success": false,
  "error": "Internal search error",
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
  "mode": "replace",
  "total_count": 1234,
  "source": "kodi"
}
```

**Parameters:**
- `mode` (required): "merge" or "replace"
  - **"merge"**: Adds to existing collection (preserves existing items)
  - **"replace"**: Authoritative replacement (removes items not in this upload)

**🚨 REPLACE MODE REQUIREMENTS:**
When using `"mode": "replace"`, you MUST:
1. Use Main API for ALL subsequent operations (never V1 API)
2. Upload ALL movies you want to keep via chunk endpoints  
3. Call the commit endpoint to finalize the replacement
4. **Any movies not uploaded in chunks will be DELETED**
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

**🚨 CRITICAL FOR REPLACE MODE:**  
This endpoint is **MANDATORY** for replace-sync. Without calling commit:
- Your uploaded movies will remain in limbo
- Old movies will NOT be deleted  
- Replace-sync will not occur

**Replace Mode Behavior:**
- Deletes ALL movies not uploaded in this batch
- Keeps ONLY movies that were uploaded via chunk endpoints
- Updates user collection to exactly match batch content

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

### 11. Get Library Statistics

**Endpoint:** `GET /users/me/library/stats`  
**Authentication:** Required (API Key)  
**Purpose:** Get comprehensive statistics about user's movie library including setup completeness, data quality metrics, and system context

**Success Response (200):**
```json
{
  "success": true,
  "stats": {
    "library_overview": {
      "total_uploaded": 1234,
      "upload_date_range": {
        "earliest": "2024-01-15T10:30:00Z",
        "latest": "2024-12-01T14:45:00Z"
      }
    },
    "setup_status": {
      "completely_setup": {
        "count": 1150,
        "percentage": 93.2,
        "movies": ["tt0111161", "tt0068646", "tt0071562"]
      },
      "not_setup": {
        "count": 84,
        "percentage": 6.8,
        "breakdown": {
          "missing_tmdb_data": {
            "count": 12,
            "movies": ["tt9999999", "tt8888888"]
          },
          "tmdb_errors": {
            "count": 3,
            "movies": ["tt7777777"]
          },
          "not_in_opensearch": {
            "count": 69,
            "movies": ["tt6666666", "tt5555555"]
          }
        }
      }
    },
    "data_quality": {
      "tmdb_data_available": {
        "count": 1219,
        "percentage": 98.8
      },
      "tmdb_errors": {
        "count": 3,
        "percentage": 0.2
      },
      "opensearch_indexed": {
        "count": 1150,
        "percentage": 93.2
      }
    },
    "batch_history": {
      "total_batches": 5,
      "successful_batches": 4,
      "failed_batches": 1,
      "recent_batches": [
        {
          "batch_id": "uuid-recent-1",
          "status": "completed",
          "total_movies": 500,
          "successful_imports": 500,
          "completed_at": "2024-12-01T14:45:00Z"
        }
      ]
    },
    "system_context": {
      "total_movies_in_system": 125000,
      "completed_movies": 124500,
      "failed_movies": 500,
      "tmdb_fetched_movies": 124450,
      "opensearch_connection": true,
      "tmdb_detailed_stats": {
        "total_records": 124450,
        "successful_fetches": 123800,
        "fetch_errors": 650,
        "complete_metadata": 123500,
        "with_release_dates": 123200,
        "success_rate": 99.48
      },
      "opensearch_detailed_stats": {
        "movies_indexed": 123000,
        "indexing_completion_rate": 98.79,
        "estimated_searchable_movies": 122800,
        "index_status": "connected"
      },
      "user_lists_stats": {
        "total_users_with_lists": 45,
        "total_user_movie_entries": 12800,
        "average_movies_per_user": 284.4,
        "largest_user_collection": 2100
      }
    }
  },
  "generated_at": "2024-12-15T16:20:00Z"
}
```

**Response Fields:**
- `library_overview`: Basic library information (total count, date range)
- `setup_status`: Breakdown of movies by completeness status with sample IMDb IDs
- `data_quality`: Percentages for TMDB data availability and OpenSearch indexing
- `batch_history`: Upload batch statistics and recent batch details
- `system_context`: System-wide statistics and service availability with enhanced metrics:
  - `tmdb_detailed_stats`: Comprehensive TMDB statistics including success rates and data completeness
  - `opensearch_detailed_stats`: OpenSearch indexing metrics and search readiness
  - `user_lists_stats`: Community statistics showing user collection patterns

**Enhanced Statistics Explained:**

*TMDB Detailed Stats:*
- `total_records`: Total TMDB database entries across all users
- `successful_fetches`: Movies with complete TMDB metadata (no errors)
- `fetch_errors`: Movies that failed TMDB API retrieval
- `complete_metadata`: Movies with both title and plot overview
- `with_release_dates`: Movies that include release date information
- `success_rate`: Percentage of successful TMDB operations

*OpenSearch Detailed Stats:*
- `movies_indexed`: Total movies available for semantic search
- `indexing_completion_rate`: % of completed movies that are searchable
- `estimated_searchable_movies`: Movies with both search indexing and good TMDB data
- `index_status`: Current OpenSearch service connectivity

*User Lists Stats:*
- `total_users_with_lists`: Number of users with movie collections
- `total_user_movie_entries`: Sum of all uploaded movies across users
- `average_movies_per_user`: Mean collection size per user
- `largest_user_collection`: Size of biggest individual library

**Use Cases:**
- Display comprehensive system health in Kodi addon settings
- Show setup progress during initial sync
- Identify movies needing additional processing
- Monitor data quality over time
- Compare user's collection size to community averages
- Display search readiness and system capacity metrics

### 12. Clear Movie List

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

## Simplified API Architecture

**✅ SINGLE API APPROACH**

The search-api now uses **one unified Main API** for all operations:

- **Individual movies**: Use Main API with batch size of 1
- **Collections**: Use Main API with chunked uploads  
- **Replace-sync**: Use Main API batch operations with commit

**Benefits:**
- No API confusion or mixing
- Consistent transaction handling
- Better error recovery and logging
- Simplified client implementation

## Example: Adding Individual Movie

**For single movie operations**, use the Main API with batch size of 1:

```javascript
// 1. Start batch session
POST /library/batch/start
{
  "mode": "merge",
  "total_count": 1,
  "source": "kodi"
}
// Returns: {"upload_id": "u_abc123", "max_chunk": 1000}

// 2. Upload single movie
PUT /library/batch/u_abc123/chunk
{
  "chunk_index": 0,
  "items": [{"imdb_id": "tt1234567"}]
}

// 3. Commit batch
POST /library/batch/u_abc123/commit
// Movie is now added to user's collection
```

This provides the same functionality as the old individual endpoints, but with consistent error handling and logging.

## Implementation Examples

### 1. Replace-Sync Example (Recommended)

```javascript
// Complete library replacement with all user's movies
function performReplacSync(movies) {
    // 1. Start batch session
    const batchResponse = await fetch('/library/batch/start', {
        method: 'POST',
        headers: { 'Authorization': `ApiKey ${apiKey}` },
        body: JSON.stringify({
            mode: 'replace',
            total_count: movies.length,
            source: 'kodi'
        })
    });

    const batch = await batchResponse.json();
    const uploadId = batch.upload_id;

    // 2. Upload movies in chunks
    const chunkSize = 1000;
    for (let i = 0; i < movies.length; i += chunkSize) {
        const chunk = movies.slice(i, i + chunkSize);
        const chunkIndex = Math.floor(i / chunkSize);

        await fetch(`/library/batch/${uploadId}/chunk`, {
            method: 'PUT',
            headers: { 
                'Authorization': `ApiKey ${apiKey}`,
                'Idempotency-Key': generateUUID()
            },
            body: JSON.stringify({
                chunk_index: chunkIndex,
                items: chunk.map(movie => ({imdb_id: movie.imdb_id}))
            })
        });
    }

    // 3. Commit batch (REQUIRED!)
    const commitResponse = await fetch(`/library/batch/${uploadId}/commit`, {
        method: 'POST',
        headers: { 'Authorization': `ApiKey ${apiKey}` }
    });

    const result = await commitResponse.json();
    console.log(`Replace-sync complete: ${result.user_movie_count} movies`);
    return result;
}
```

### 2. Delta Sync Example (Efficient Updates)

```javascript
// Only upload movies not already on server
function performDeltaSync() {
    // Get server fingerprints
    const hashResponse = await fetch('/library/hash', {
        headers: { 'Authorization': `ApiKey ${apiKey}` }
    });
    const serverData = await hashResponse.json();
    const serverFingerprints = new Set(serverData.fingerprints);

    // Get local movies and calculate fingerprints
    const localMovies = getUserMovieCollection();
    const newMovies = localMovies.filter(movie => {
        const fingerprint = calculateFingerprint(movie.imdb_id);
        return !serverFingerprints.has(fingerprint);
    });

    if (newMovies.length === 0) {
        console.log('Collection already up to date');
        return;
    }

    // Upload only new movies using merge mode
    return performReplacSync(newMovies, 'merge');
}
```

## Summary

The search-api now uses a **single, unified Main API** that eliminates confusion and provides:

✅ **Consistent behavior** across all operations  
✅ **Proper transaction handling** with commit/rollback  
✅ **Enhanced error recovery** and detailed logging  
✅ **Replace-sync functionality** that works correctly  

**Key Takeaways for Kodi Developers:**
- Use Main API for all operations (individual or batch)
- Always call commit endpoint for replace-sync
- Use merge mode for adding movies, replace mode for authoritative replacement
- Implement proper error handling and retry logic

For technical support, contact your system administrator with API logs and specific error messages.  
