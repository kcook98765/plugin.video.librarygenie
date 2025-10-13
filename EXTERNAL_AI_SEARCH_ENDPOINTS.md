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
Use **MAIN API ONLY** (endpoints 5-9 below). Do NOT mix with V1 API.

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
**Purpose:** Advanced multi-mode search with semantic understanding and intelligent fallback

**Overview:**
This endpoint provides three powerful search modes with automatic fallback handling:

1. **BM25 Mode** (keyword-based): Simple keyword search with fixed 70% minimum_should_match, used as fallback when LLM fails or is disabled
2. **Hybrid Mode** (recommended): Requires LLM to extract intent, combines BM25 keyword matching with multi-vector semantic search using LLM-provided weights
3. **LLM-Assisted Mode** (optional): GPT-4 extracts search intent from natural language queries - LLM is the single source of truth for all intent extraction

**Search Modes Explained:**

**BM25 Mode (Keyword Search):**
- Pure keyword-based search using OpenSearch BM25 algorithm
- Simple keyword matching with fixed 70% minimum_should_match
- Used as fallback when LLM fails or is disabled
- Fast and reliable for exact keyword matching
- Best for: Specific titles, director names, exact phrases

**Hybrid Mode (Semantic + Keyword):**
- **Requires `use_llm: true`** - LLM is mandatory for hybrid mode
- LLM extracts structured intent (must/should/exclude filters + semantic phrases)
- Combines BM25 keyword matching with multi-vector semantic search using LLM-provided weights
- Uses script_score in main query (not rescore) for vector scoring
- Semantic search uses 4 embedding facets:
  - Plot vectors (storyline/narrative similarity)
  - Mood/tone vectors (atmosphere/feel similarity)
  - Themes vectors (underlying concepts/messages)
  - Genre/trope vectors (category/conventions)
- No heuristic vector generation - all vectors come from LLM intent extraction
- Best for: Descriptive queries, finding similar vibes, semantic understanding

**LLM-Assisted Mode (Intent Extraction):**
- LLM is the single source of truth for all intent extraction
- Extracts structured search parameters: must/should/exclude filters, ranges (year/runtime/rating), languages, countries, semantic phrases, and weights
- No regex or heuristic parsing - zero fallback to heuristics
- Works with both BM25 and Hybrid modes (Hybrid requires LLM)
- Best for: Complex natural language queries, conversational search

**Basic Request (BM25 Mode - Default):**
```json
{
  "query": "inception",
  "limit": 20
}
```

**Advanced Request (Hybrid Mode with LLM):**
```json
{
  "query": "dark psychological thriller from the 90s",
  "mode": "hybrid",
  "use_llm": true,
  "limit": 50
}
```

**Natural Language Request (Using "vibe"):**
```json
{
  "vibe": "looking for mind-bending movies like inception with complex plots",
  "mode": "hybrid",
  "use_llm": true,
  "debug_intent": true
}
```

**Request Parameters:**

**Required:**
- `query` OR `vibe` (string): Search query
  - `query`: Standard search text
  - `vibe`: Natural language description (recommended with `use_llm: true`)

**Optional:**
- `mode` (string): Search mode - "bm25" (default) or "hybrid"
- `use_llm` (boolean): Enable GPT-4 intent extraction (default: false)
- `limit` (integer): Maximum results (default: 20, max: 100)
- `debug_intent` (boolean): Include detailed diagnostics in response (default: false)

**Success Response:**
```json
{
  "success": true,
  "query": "dark psychological thriller from the 90s",
  "mode": "hybrid",
  "total_results": 24,
  "max_score": 0.924,
  "results": [
    {
      "imdb_id": "tt0114369",
      "score": 0.924,
      "bm25_score": 0.856
    },
    {
      "imdb_id": "tt0117571",
      "score": 0.887,
      "bm25_score": 0.792
    },
    {
      "imdb_id": "tt0114814",
      "score": 0.863,
      "bm25_score": 0.845
    }
  ]
}
```

**Response with Diagnostics (debug_intent=true):**
```json
{
  "success": true,
  "query": "dark psychological thriller from the 90s",
  "mode": "hybrid",
  "total_results": 24,
  "max_score": 0.924,
  "results": [...],
  "diagnostics": {
    "llm_used": true,
    "fallback_used": false,
    "fallback_reason": null,
    "execution_mode": "llm_hybrid",
    "vector_weights": {
      "plot": 0.4,
      "mood": 0.3,
      "themes": 0.2,
      "genre": 0.1
    },
    "parsed_intent_summary": {
      "confidence": 0.92,
      "query_text": "dark psychological thriller",
      "vector_focus": {
        "plot": 0.4,
        "mood": 0.3,
        "themes": 0.2,
        "genre": 0.1
      }
    }
  }
}
```

**Response Fields:**
- `success`: Boolean indicating if search succeeded
- `query`: The search query used
- `mode`: Search mode executed ("bm25" or "hybrid")
- `total_results`: Number of results found
- `max_score`: Highest score in results (normalized to 0.0-1.0 range)
- `results`: Array of result objects:
  - `imdb_id`: IMDb identifier
  - `score`: Final ranking score normalized to 0.0-1.0 range (1.0 = perfect match, 0.0 = no match)
  - `bm25_score`: Original keyword score (hybrid mode only)

**Score Normalization:**
All scores are normalized to a consistent 0.0 to 1.0 range for easy comparison and ranking:
- **Search scores**: Calculated using dynamic maximum based on weights (BM25 contribution capped at 10.0, vector similarities up to 2.0 times weight, plus popularity boost), then normalized and clamped to 1.0
- **Score interpretation**: 
  - 0.9-1.0: Excellent match
  - 0.7-0.9: Good match
  - 0.5-0.7: Moderate match
  - Below 0.5: Weak match

**Diagnostics Fields (when debug_intent=true):**
- `llm_used`: Whether GPT-4 intent extraction was used
- `fallback_used`: Whether automatic fallback occurred
- `fallback_reason`: Why fallback happened (e.g., "hybrid_failed")
- `execution_mode`: Actual mode executed:
  - `"bm25"`: Simple keyword search (no LLM)
  - `"llm_bm25"`: LLM intent extraction used in BM25-only mode
  - `"llm_hybrid"`: LLM intent extraction with hybrid vector search
  - Note: `"hybrid"` without LLM is no longer supported
- `vector_weights`: LLM-provided semantic vector weights applied (hybrid only)
- `parsed_intent_summary`: LLM extraction results (when LLM used)

**Automatic Fallback Chain:**

The system automatically recovers from failures with simplified fallback logic:

1. **LLM Failure**: Falls back to simple BM25 keyword search (no vectors, no heuristics)
2. **Embeddings Failure**: Falls back to simple BM25 (drops vector portion entirely, sets `fallback_used: true`, `fallback_reason: "hybrid_failed"`)
3. **BM25 Failure**: Returns error (end of fallback chain)

Note: No auto-relaxation or complex fallback logic - BM25 uses fixed 70% minimum_should_match

**Error Responses:**
```json
// Missing query/vibe
{
  "success": false,
  "error": "query or vibe required",
  "results": []
}

// Invalid mode
{
  "success": false,
  "error": "mode must be \"bm25\" or \"hybrid\"",
  "results": []
}

// Service unavailable
{
  "success": false,
  "error": "Search service not available",
  "results": []
}

// Internal error (after all fallbacks exhausted)
{
  "success": false,
  "error": "Internal search error",
  "results": []
}
```

**Best Practices:**

1. **Start with Hybrid Mode**: Provides best results by combining keyword + semantic search
2. **Use LLM for Natural Language**: Enable `use_llm: true` when users type conversational queries
3. **Use "vibe" Parameter**: Better suited for natural language than "query"
4. **Enable Diagnostics in Development**: Use `debug_intent: true` to understand search behavior
5. **Handle Scores Appropriately**: 
   - In hybrid mode, use `score` for ranking (blended score)
   - Use `bm25_score` for fallback comparison or debugging
6. **Trust the Fallback**: System automatically degrades gracefully from Hybrid → BM25

**Example Kodi Integration:**
```python
import urllib.request
import json

def search_movies(api_key, user_query, semantic=True, use_ai=False):
    """
    Search for movies with configurable modes
    
    Args:
        api_key: User's API key
        user_query: Search query from user
        semantic: Use hybrid mode (True) or BM25 only (False)
        use_ai: Enable LLM intent extraction
    """
    url = "https://your-server.com:5020/kodi/search/movies"
    headers = {
        "Authorization": f"ApiKey {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "vibe" if use_ai else "query": user_query,
        "mode": "hybrid" if semantic else "bm25",
        "use_llm": use_ai,
        "limit": 50
    }
    
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    
    response = urllib.request.urlopen(request, timeout=30)
    result = json.loads(response.read().decode('utf-8'))
    
    if result['success']:
        return result['results']  # List of {imdb_id, score}
    return []

# Usage examples:
# Basic keyword search
results = search_movies(api_key, "inception", semantic=False)

# Semantic hybrid search
results = search_movies(api_key, "mind bending thriller", semantic=True)

# Natural language with AI
results = search_movies(api_key, "looking for dark moody films like blade runner", 
                       semantic=True, use_ai=True)
```

### 4. Find Similar Movies

**Endpoint:** `POST /similar_to`  
**Authentication:** Optional (API Key)  
**Purpose:** Find movies similar to a reference movie based on AI embeddings

**Description:**
This endpoint finds movies similar to a reference movie using the same advanced embedding system as MediaVault's search:
1. **Reference Movie Lookup**: The system retrieves embedding vectors for the specified IMDb ID
2. **Facet-Based Similarity**: Compare against selected embedding facets:
   - Plot embeddings (storyline/narrative similarity)
   - Mood/tone embeddings (atmosphere/feel similarity)
   - Theme embeddings (underlying messages/concepts similarity)
   - Genre/trope embeddings (category/convention similarity)
3. **Similarity Scoring**: Results are ranked by vector similarity scores
4. **User Filtering**: If authenticated, results are filtered to only show movies in the user's library

**Request:**
```json
{
  "reference_imdb_id": "tt0111161",
  "include_plot": true,
  "include_mood": true,
  "include_themes": false,
  "include_genre": true
}
```

**Parameters:**
- `reference_imdb_id` (required): IMDb ID of the reference movie (format: "tt" + digits, minimum 9 characters)
- `include_plot` (optional): Include plot/storyline similarity (default: false)
- `include_mood` (optional): Include mood/tone similarity (default: false)
- `include_themes` (optional): Include themes/subtext similarity (default: false)
- `include_genre` (optional): Include genre/trope similarity (default: false)

**Important:** At least one facet must be set to `true`

**Success Response (200):**
```json
{
  "success": true,
  "results": [
    {
      "imdb_id": "tt0068646",
      "score": 0.952
    },
    {
      "imdb_id": "tt0071562",
      "score": 0.887
    },
    {
      "imdb_id": "tt0468569",
      "score": 0.834
    },
    {
      "imdb_id": "tt0137523",
      "score": 0.791
    },
    {
      "imdb_id": "tt0110912",
      "score": 0.756
    }
  ]
}
```

**Response Format:**
- `success`: Boolean indicating if the search succeeded
- `results`: Array of result objects for similar movies (up to 50 results), sorted by similarity score (highest first)
  - `imdb_id`: IMDb identifier of similar movie
  - `score`: Similarity score normalized to 0.0-1.0 range (1.0 = most similar, 0.0 = not similar)

**Score Normalization:**
Similarity scores are normalized to a consistent 0.0 to 1.0 range:
- **Similarity scores**: Normalized by dividing by 2.0 (the theoretical maximum when all cosine similarities equal 1.0 and weights sum to 1.0), then clamped to ensure they never exceed 1.0
- **Score interpretation**: Same as search endpoint
  - 0.9-1.0: Extremely similar
  - 0.7-0.9: Very similar
  - 0.5-0.7: Moderately similar
  - Below 0.5: Weakly similar

**Error Responses:**
```json
// Missing reference IMDb ID
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

// Invalid JSON
{
  "success": false,
  "error": "Request must be JSON"
}
```

**Use Cases:**
- "Find movies like this" feature in Kodi addon
- Building recommendation lists based on user favorites
- Discovering similar titles for collection organization
- Creating dynamic playlists based on movie similarity

**Example Usage in Kodi:**
```python
import urllib.request
import json

def find_similar_movies(api_key, imdb_id):
    url = "https://your-server.com:5020/similar_to"
    headers = {
        "Authorization": f"ApiKey {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "reference_imdb_id": imdb_id,
        "include_plot": True,
        "include_mood": True,
        "include_genre": True
    }
    
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    
    response = urllib.request.urlopen(request)
    result = json.loads(response.read().decode('utf-8'))
    
    if result['success']:
        return result['results']  # List of similar IMDb IDs
    return []
```

### 5. Start Batch Upload Session

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

### 6. Upload Movie Chunk  

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

### 7. Commit Batch Session

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

### 8. Get Batch Status

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

### 9. Get Library Hash (Delta Sync)

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



### 10. Get Movie List

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

### 11. Get Batch History

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

### 12. Get Library Statistics

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
        "percentage": 93.2
      },
      "not_setup": {
        "count": 84,
        "percentage": 6.8,
        "breakdown": {
          "missing_tmdb_data": {
            "count": 12
          },
          "tmdb_errors": {
            "count": 3
          },
          "not_in_opensearch": {
            "count": 69
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
- `setup_status`: Breakdown of movies by completeness status with counts and percentages only
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

### 13. Clear Movie List

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
