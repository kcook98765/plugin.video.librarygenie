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
Scan Kodi Library → Extract IMDb IDs → Check Delta with /library/hash → Upload New Movies via Chunked Batch → Monitor Progress
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

## V1 Library Synchronization API

The V1 API provides efficient client-server synchronization for IMDB movie lists, designed specifically for the Kodi addon sync protocol. These endpoints support version tracking, delta sync, and idempotent batch operations.

### V1.1. Exchange OTP for Token

**Endpoint:** `POST /v1/auth/otp`  
**Authentication:** None (public endpoint)  
**Purpose:** Exchange OTP (pairing code) for bearer token using V1 auth flow

**Request:**
```json
{
  "otp": "12345678"
}
```

**Success Response (200):**
```json
{
  "access_token": "abc123...xyz789",
  "token_type": "bearer", 
  "expires_in": null,
  "user_email": "user@example.com"
}
```

**Error Responses:**
```json
// Missing OTP
{
  "error": "OTP required"
}

// Invalid or expired OTP
{
  "error": "Invalid or expired OTP"
}
```

### V1.2. Validate Token

**Endpoint:** `GET /v1/auth/whoami`  
**Authentication:** Required (Bearer Token or API Key)  
**Purpose:** Validate token and return user information

**Headers:**
```
Authorization: Bearer YOUR_ACCESS_TOKEN
# OR
Authorization: ApiKey YOUR_API_KEY
```

**Success Response (200):**
```json
{
  "user_id": "auth0|abc123",
  "email": "user@example.com",
  "role": "user",
  "is_active": true,
  "token_valid": true
}
```

### V1.3. Get Library Version

**Endpoint:** `GET /v1/library/version`  
**Authentication:** Required (Bearer Token or API Key)  
**Purpose:** Get current library version/etag for efficient delta sync

**Success Response (200):**
```json
{
  "version": 42,
  "etag": "a1b2c3d4e5f6",
  "item_count": 1234,
  "last_modified": "2025-08-25T14:30:00Z"
}
```

**Headers:**
- `ETag: "a1b2c3d4e5f6"` - Version identifier for caching
- `Cache-Control: private, max-age=0` - Caching policy

**Usage:**
- Check if client's cached version matches current server version
- Avoid unnecessary data transfer when library unchanged
- Essential for efficient sync protocol implementation

### V1.4. Get Library IDs (Paginated)

**Endpoint:** `GET /v1/library/ids`  
**Authentication:** Required (Bearer Token or API Key)  
**Purpose:** Get user's IMDB IDs with pagination and ETag support

**Query Parameters:**
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 500, max: 1000)

**Headers (Optional):**
- `If-None-Match: "a1b2c3d4e5f6"` - Returns 304 if ETag matches

**Success Response (200):**
```json
{
  "version": 42,
  "etag": "a1b2c3d4e5f6",
  "imdb_ids": ["tt0111161", "tt0068646", "tt0071562"],
  "pagination": {
    "page": 1,
    "page_size": 500,
    "total_items": 1234,
    "total_pages": 3,
    "has_next": true,
    "has_prev": false
  }
}
```

**304 Not Modified Response:**
Returns empty body with 304 status when ETag matches client's version.

### V1.5. Add Movies to Library

**Endpoint:** `POST /v1/library/add`  
**Authentication:** Required (Bearer Token or API Key)  
**Purpose:** Add movies to library with idempotent batch processing

**Headers:**
```
Idempotency-Key: <unique-uuid-per-batch>
```

**Request:**
```json
{
  "imdb_ids": ["tt1234567", "tt7654321", "tt9876543"]
}
```

**Limits:**
- Maximum 5,000 movies per batch
- Valid IMDB IDs only (format: tt + 7-8 digits)

**Success Response (200):**
```json
{
  "success": true,
  "results": {
    "added": 2,
    "already_present": 1,
    "invalid": 0
  },
  "items": [
    {"imdb_id": "tt1234567", "status": "added"},
    {"imdb_id": "tt7654321", "status": "already_present"},
    {"imdb_id": "tt9876543", "status": "added"}
  ],
  "version": 43,
  "etag": "b2c3d4e5f6g7",
  "item_count": 1236
}
```

**Item Status Values:**
- `added`: Movie successfully added to library
- `already_present`: Movie was already in library (idempotent)
- `invalid`: Invalid IMDB ID format

### V1.6. Remove Movies from Library

**Endpoint:** `POST /v1/library/remove`  
**Authentication:** Required (Bearer Token or API Key)  
**Purpose:** Remove movies from library with idempotent batch processing

**Headers:**
```
Idempotency-Key: <unique-uuid-per-batch>
```

**Request:**
```json
{
  "imdb_ids": ["tt1234567", "tt7654321"]
}
```

**Success Response (200):**
```json
{
  "success": true,
  "results": {
    "removed": 1,
    "not_found": 1,
    "invalid": 0
  },
  "items": [
    {"imdb_id": "tt1234567", "status": "removed"},
    {"imdb_id": "tt7654321", "status": "not_found"}
  ],
  "version": 44,
  "etag": "c3d4e5f6g7h8",
  "item_count": 1235
}
```

**Item Status Values:**
- `removed`: Movie successfully removed from library
- `not_found`: Movie was not in library (idempotent)
- `invalid`: Invalid IMDB ID format

### V1.7. Search Owned Movies

**Endpoint:** `GET /v1/library/search`  
**Authentication:** Required (Bearer Token or API Key)  
**Purpose:** Search within user's owned movie collection only

**Query Parameters:**
- `q` (required): Search query string
- `limit` (optional): Results limit (default: 20, max: 100)
- `only_owned` (required): Must be "true" for this endpoint

**Success Response (200):**
```json
{
  "success": true,
  "query": "psychological thriller",
  "results": [
    {"imdb_id": "tt1375666", "score": 0.924},
    {"imdb_id": "tt0816692", "score": 0.887}
  ],
  "total_results": 15,
  "library_version": 44,
  "library_etag": "c3d4e5f6g7h8"
}
```

**Features:**
- Semantic search using AI embeddings
- Results limited to user's movie collection
- Includes library version for sync state awareness
- Returns similarity scores for ranking

## V1 Sync Protocol Example

**Efficient Client Sync Workflow:**

1. **Check for Changes:**
   ```bash
   GET /v1/library/version
   # Compare ETag with cached version
   ```

2. **Get Current Server State (if changed):**
   ```bash
   GET /v1/library/ids?page=1&page_size=1000
   # With If-None-Match header for 304 responses
   ```

3. **Compute Differences:**
   ```javascript
   const local_ids = getLocalMovieIds();
   const server_ids = response.imdb_ids;
   const to_add = local_ids.filter(id => !server_ids.includes(id));
   const to_remove = server_ids.filter(id => !local_ids.includes(id));
   ```

4. **Apply Changes:**
   ```bash
   # Add new movies
   POST /v1/library/add
   Idempotency-Key: add-batch-uuid
   {"imdb_ids": to_add}

   # Remove deleted movies  
   POST /v1/library/remove
   Idempotency-Key: remove-batch-uuid
   {"imdb_ids": to_remove}
   ```

**Benefits:**
- Minimal bandwidth usage with ETag caching
- Idempotent operations safe for retries
- Version tracking for conflict detection
- Batch processing for efficiency

### 13. Find Similar Movies

**Endpoint:** `POST /similar_to`  
**Authentication:** None (public endpoint)  
**Purpose:** Find movies similar to a reference movie based on selected embedding facets

**Description:**
This endpoint uses vector similarity search to find movies that match specific aspects of a reference movie:
1. **Dynamic Facet Selection**: Choose which movie aspects to compare (plot, mood, themes, genre)
2. **Equal Weight Distribution**: Selected facets receive equal weighting (e.g., 2 facets = 50% each)
3. **Vector Similarity**: Uses cosine similarity on OpenAI embeddings stored in OpenSearch
4. **Sorted Results**: Returns up to 50 IMDb IDs ranked by similarity score

**Request:**
```json
{
  "reference_imdb_id": "tt0111161",
  "include_plot": true,
  "include_mood": true,
  "include_themes": false,
  "include_genre": false
}
```

**Parameters:**
- `reference_imdb_id` (required): IMDb ID of the reference movie (format: "tt" + digits)
- `include_plot` (optional): Include plot similarity (default: false)
- `include_mood` (optional): Include mood/tone similarity (default: false)
- `include_themes` (optional): Include themes/subtext similarity (default: false)
- `include_genre` (optional): Include genre/tropes similarity (default: false)

**Requirements:**
- At least one facet must be set to `true`
- Reference movie must exist in the system with embedding data
- Valid IMDb ID format required

**Success Response (200):**
```json
{
  "success": true,
  "results": [
    "tt0068646",
    "tt0071562", 
    "tt0468569",
    "tt0816692",
    "tt1375666"
  ]
}
```

**Error Responses:**
```json
// Missing reference ID
{
  "success": false,
  "error": "reference_imdb_id is required"
}

// No facets selected
{
  "success": false,
  "error": "At least one facet must be included"
}

// Invalid IMDb ID format
{
  "success": false,
  "error": "Invalid IMDb ID format"
}

// Search service unavailable
{
  "success": false,
  "error": "Search service not available"
}
```

**Usage Example (Python):**
```python
def find_similar_movies(reference_imdb, facets):
    payload = {
        "reference_imdb_id": reference_imdb,
        "include_plot": facets.get("plot", False),
        "include_mood": facets.get("mood", False), 
        "include_themes": facets.get("themes", False),
        "include_genre": facets.get("genre", False)
    }

    response = requests.post(f"{BASE_URL}/similar_to", json=payload)

    if response.status_code == 200:
        data = response.json()
        if data["success"]:
            return data["results"]  # List of IMDb IDs

    return []

# Example usage
similar_movies = find_similar_movies("tt0111161", {
    "plot": True,
    "mood": True
})
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
import json
import time
import urllib.request
import urllib.error
from urllib.parse import urljoin

def chunked_movie_upload(movie_list, mode='merge', chunk_size=500):
    """Upload user's movie collection using chunked batch upload"""

    # Step 1: Start batch session
    session = make_kodi_api_request('library/batch/start', 'POST', {
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
        # Generate unique idempotency key (without uuid dependency)
        import random
        import time
        idempotency_key = f"{int(time.time())}-{random.randint(10000, 99999)}-{chunk_index}"

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
                result = make_kodi_api_request_with_headers(
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
        commit_result = make_kodi_api_request(
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

def make_kodi_api_request_with_headers(endpoint, method, data=None, headers=None):
    """Kodi 19+ API request helper using Python 3 libraries"""
    import xbmcaddon
    import json
    import xbmc

    addon = xbmcaddon.Addon()
    api_key = addon.getSetting('api_key')
    server_url = addon.getSetting('server_url').rstrip('/')

    url = f"{server_url}/{endpoint}"

    # Prepare headers
    request_headers = {
        'Authorization': f"ApiKey {api_key}",
        'Content-Type': 'application/json'
    }
    if headers:
        request_headers.update(headers)

    try:
        # Create request object
        if data:
            json_data = json.dumps(data).encode('utf-8')
            request = urllib.request.Request(url, data=json_data)
        else:
            request = urllib.request.Request(url)

        # Add headers
        for key, value in request_headers.items():
            request.add_header(key, value)

        # Set method for non-GET requests
        if method in ['PUT', 'POST', 'DELETE']:
            request.get_method = lambda: method

        # Make request
        response = urllib.request.urlopen(request, timeout=30)

        if response.getcode() == 200:
            response_data = response.read().decode('utf-8')
            return json.loads(response_data)

    except Exception as e:
        xbmc.log(f"API request failed: {str(e)}", xbmc.LOGERROR)

    return None

def make_kodi_api_request(endpoint, method='GET', data=None):
    """Simplified API request without custom headers"""
    return make_kodi_api_request_with_headers(endpoint, method, data)

def delta_sync_movies():
    """Efficient delta sync using library fingerprints"""
    # Get current server fingerprints
    server_hash = make_kodi_api_request('library/hash')
    if not server_hash or not server_hash.get('success'):
        return full_sync_movies()

    server_fingerprints = set(server_hash['fingerprints'])

    # Get local movie collection
    local_movies = get_user_movie_collection()
    local_fingerprints = set()

    # Use Kodi's built-in hash function (simple approach)
    import hashlib
    for movie in local_movies:
        imdb_id = movie['imdb_id'] if isinstance(movie, dict) else movie
        # Create simple hash using available libraries
        hash_obj = hashlib.sha1(imdb_id.encode('utf-8'))
        local_fingerprints.add(hash_obj.hexdigest()[:8])

    # Find movies to upload (not on server)
    new_fingerprints = local_fingerprints - server_fingerprints

    if not new_fingerprints:
        return {'success': True, 'message': 'Collection already up to date'}

    # Filter movies to upload
    movies_to_upload = []
    for movie in local_movies:
        imdb_id = movie['imdb_id'] if isinstance(movie, dict) else movie
        hash_obj = hashlib.sha1(imdb_id.encode('utf-8'))
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
    return make_kodi_api_request(f'library/batch/{upload_id}/status')
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