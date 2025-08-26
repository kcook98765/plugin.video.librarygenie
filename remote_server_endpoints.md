# Remote Server API — LibraryGenie
Version: v1 (draft)

This document specifies the HTTP endpoints used by LibraryGenie’s optional remote services. The server **never stores user lists**; it only stores a user’s **set of IMDb IDs** and serves **search/similarity** that return IMDb IDs. All endpoints are JSON unless noted. Timestamps are ISO-8601 (UTC).

---

## 0. Conventions

- Base URL: `https://api.example.com/v1` (example)
- Auth: Bearer token in `Authorization: Bearer <token>` unless otherwise stated.
- Content types:
  - `application/json` for standard requests
  - `application/x-ndjson` for bulk uploads (newline-delimited JSON)
- Idempotency: For mutating endpoints, clients **should** send `Idempotency-Key` header (UUID). The server **must** treat duplicates as safe retries.
- Rate limits: server returns headers `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
- Pagination: cursor-based with `?cursor=<token>&limit=<n>`; response includes `next_cursor` when more data exists.
- Scopes (examples): `library:write`, `library:read`, `search:read`, `admin:*`.

---

## 1. Pairing & Authentication (OTP → Token)

### 1.1 Start pairing (unauthenticated)
`POST /pair/start`

Starts an 8–10 digit OTP pairing session that the user will enter in the Kodi add-on.

Request JSON:
```json
{ "client_name": "kodi.LibraryGenie", "device_desc": "Living Room", "ttl_seconds": 300 }
```

Response JSON:
```json
{ "otp": "4831-9217", "session_id": "sess_abc123", "expires_at": "2025-08-24T18:10:00Z", "poll_after_ms": 2000 }
```

### 1.2 Complete pairing (user via browser)
`POST /pair/complete`

Web flow used by the user in a browser page to approve the device.

Request JSON:
```json
{ "otp": "4831-9217", "account_email": "user@example.com" }
```

Response JSON:
```json
{ "session_id": "sess_abc123", "status": "approved" }
```

### 1.3 Poll pairing (device)
`POST /pair/poll`

The Kodi device polls until approved or expired.

Request JSON:
```json
{ "session_id": "sess_abc123" }
```

Response JSON (approved):
```json
{ "status": "approved", "device_code": "dev_e9f...", "interval_ms": 2000 }
```

### 1.4 Exchange device code for token
`POST /auth/token`

Request JSON:
```json
{ "device_code": "dev_e9f...", "grant_type": "urn:ietf:params:oauth:grant-type:device_code" }
```

Response JSON:
```json
{ "access_token": "eyJhbGci...", "token_type": "Bearer", "expires_in": 2592000, "scope": "library:read library:write search:read" }
```

### 1.5 OTP-based pairing (alternative)
`POST /v1/auth/otp`

Simplified OTP exchange for bearer token. Used by CLIENT-KODI-SERVICE for direct token acquisition.

Request JSON:
```json
{ "otp": "4831-9217" }
```

Response JSON:
```json
{ "access_token": "eyJhbGci...", "token_type": "Bearer", "expires_in": 2592000, "scope": "library:read library:write search:read" }
```

### 1.6 Token validation
`GET /v1/auth/whoami`

Validates token and returns minimal user info for client state verification.

Response JSON:
```json
{ "user_id": "usr_123", "email_hash": "abc123", "token_expires_at": "2025-09-24T18:00:00Z" }
```

### 1.7 Token introspect (optional)
`POST /auth/introspect` → token validity & scopes.

---

## 2. Health & User

### 2.1 Health
`GET /health` → `{ "ok": true, "version": "v1", "uptime_s": 12345 }`

### 2.2 Current user
`GET /users/me` (auth) → profile minimal fields (id, email hash, created_at).

---

## 3. Library Sync (IMDb Set Only)

The server stores a **set** of IMDb IDs per user. No titles, paths, or playback info.

### 3.0 Differential Sync Endpoints (CLIENT-KODI-SERVICE)

These endpoints support efficient differential synchronization where the client computes and uploads only changes (adds/removes).

#### 3.0.1 Get library version
`GET /v1/library/version`

Lightweight endpoint to check server version/etag without fetching the full ID set.

Response JSON:
```json
{
  "version": "v1.2.345",
  "etag": "W/\"abc123def456\"",
  "item_count": 5123,
  "last_modified": "2025-08-24T18:00:00Z"
}
```

#### 3.0.2 Get library IDs (paged)
`GET /v1/library/ids?cursor=<token>&limit=<n>`

Returns normalized IMDb IDs in stable order for client diff computation. Supports If-None-Match (ETag).

Response JSON:
```json
{
  "imdb_ids": ["tt0111161", "tt0068646", "tt0468569"],
  "version": "v1.2.345",
  "etag": "W/\"abc123def456\"",
  "total_count": 5123,
  "next_cursor": "cursor_token_456"
}
```

#### 3.0.3 Add to library (batched)
`POST /v1/library/add`

Idempotent addition of IMDb IDs. Server ignores duplicates.

Headers: `Idempotency-Key` (required)

Request JSON:
```json
{
  "imdb_ids": ["tt1234567", "tt7654321"]
}
```

Response JSON:
```json
{
  "added": 2,
  "already_present": 0,
  "invalid": 0,
  "per_item_status": [
    {"imdb_id": "tt1234567", "status": "added"},
    {"imdb_id": "tt7654321", "status": "added"}
  ],
  "new_total_count": 5125,
  "version": "v1.2.346",
  "etag": "W/\"def456ghi789\""
}
```

#### 3.0.4 Remove from library (batched)
`POST /v1/library/remove`

Idempotent removal of IMDb IDs. Server ignores missing IDs.

Headers: `Idempotency-Key` (required)

Request JSON:
```json
{
  "imdb_ids": ["tt1234567", "tt7654321"]
}
```

Response JSON:
```json
{
  "removed": 1,
  "not_found": 1,
  "invalid": 0,
  "per_item_status": [
    {"imdb_id": "tt1234567", "status": "removed"},
    {"imdb_id": "tt7654321", "status": "not_found"}
  ],
  "new_total_count": 5124,
  "version": "v1.2.347",
  "etag": "W/\"ghi789jkl012\""
}
```

### 3.1 Replace library (authoritative)
`POST /library/replace`  
Headers: `Content-Type: application/x-ndjson` (preferred) or `application/json` with `{"imdb_ids":["tt..."]}`.

- NDJSON: one JSON object per line: `{ "imdb_id": "tt1234567" }`
- Supports **chunked uploads** with headers:
  - `X-Chunk-Index: 1`
  - `X-Chunk-Total: 10`
  - `X-Chunk-Id: "chunk-uuid"`
- Idempotent via `Idempotency-Key`.

Response JSON:
```json
{
  "mode": "replace",
  "accepted": 5000,
  "duplicates": 0,
  "invalid": 12,
  "finalized": true,
  "user_movie_count": 4988,
  "warnings": ["12 invalid imdb ids dropped"]
}
```

### 3.2 Merge library (delta)
`POST /library/merge` (same body semantics). Merges new IDs into the set.

Response JSON:
```json
{
  "mode": "merge",
  "accepted": 120,
  "duplicates": 87,
  "invalid": 3,
  "user_movie_count": 5123
}
```

### 3.3 Clear library
`POST /library/clear`

Response JSON: `{ "deleted_count": 5123 }`

### 3.4 Status
`GET /library/status`

Response JSON:
```json
{
  "user_movie_count": 5123,
  "last_replace_at": "2025-08-24T16:00:00Z",
  "last_merge_at": "2025-08-24T18:00:00Z",
  "processing_backlog": 431, 
  "coverage": { "total_known": 1_200_000, "user_known": 5100 }
}
```

### 3.5 Batch history
`GET /library/batches?cursor=&limit=50`

Response JSON (example):
```json
{
  "batches": [
    { "id":"b_1", "type":"replace", "started_at":"...", "successful_imports":4988, "invalid":12 },
    { "id":"b_2", "type":"merge", "started_at":"...", "successful_imports":33, "duplicates":87 }
  ],
  "next_cursor": null
}
```

### 3.6 Bulk upsert with versions
`POST /v1/library/bulk-upsert`

Upserts library records with IMDb IDs and optional version metadata. Supports idempotency via `Idempotency-Key` header.

Request JSON:
```json
{
  "records": [
    {
      "imdb_id": "tt1234567",
      "versions": [
        {
          "movieid": "movie_123",
          "file_hash": "sha256:abc123...",
          "path_hash": "sha256:def456...",
          "quality": "2160p",
          "hdr": true,
          "atmos": true
        }
      ]
    }
  ]
}
```

Response JSON:
```json
{
  "processed": 1,
  "upserted": 1,
  "versions_merged": 1,
  "errors": []
}
```

### 3.7 Bulk delete
`POST /v1/library/bulk-delete`

Bulk delete IMDb entries with optional mode control. Supports tombstones for replication.

Request JSON:
```json
{
  "imdb_ids": ["tt1234567", "tt7654321"],
  "mode": "remove_versions"
}
```

Modes:
- `remove_versions`: Remove specific versions but keep IMDb entry
- `remove_all`: Remove entire IMDb entry and all versions

Response JSON:
```json
{
  "deleted_entries": 2,
  "deleted_versions": 3,
  "tombstones_created": 2
}
```

### 3.8 Delta sync
`GET /v1/library/delta?cursor=<token>`

Returns incremental changes since the last cursor for efficient synchronization.

Response JSON:
```json
{
  "adds": [
    { "imdb_id": "tt1234567", "versions": [...] }
  ],
  "updates": [
    { "imdb_id": "tt7654321", "versions": [...] }
  ],
  "deletes": [
    { "imdb_id": "tt9999999", "deleted_at": "2025-08-24T18:00:00Z" }
  ],
  "next_cursor": "cursor_token_456"
}
```

### 3.9 Replace snapshot
`POST /v1/library/replace-snapshot`

Declares authoritative library state. Server computes diff and applies changes.

Request JSON:
```json
{
  "snapshot": [
    {
      "imdb_id": "tt1234567",
      "versions": [
        {
          "movieid": "movie_123",
          "quality": "2160p",
          "hdr": true
        }
      ]
    }
  ]
}
```

Response JSON:
```json
{
  "diff_computed": true,
  "added": 12,
  "updated": 5,
  "removed": 3,
  "final_count": 1247
}
```

---

## 4. Search & Similarity (IMDb Out Only)

All search endpoints return **only IMDb IDs** plus optional scores. Client maps to Kodi DB via local mapping.

### 4.1 Text search
`GET /search/movies?q=psychological%20thrillers&limit=200&cursor=`

Response JSON:
```json
{
  "results": [
    { "imdb_id": "tt1375666", "score": 0.92 },
    { "imdb_id": "tt1130884", "score": 0.90 }
  ],
  "next_cursor": null
}
```

Optional filter: `in_library=true` (server intersects with user’s IMDb set to return only owned titles).

### 4.1.1 Owned-filtered search (CLIENT-KODI-SERVICE)
`GET /v1/library/search?q=<query>&only_owned=true&limit=<n>`

Returns search results filtered to the user's allowlist. Response includes server version used for filtering.

Response JSON:
```json
{
  "results": [
    { "imdb_id": "tt1375666", "score": 0.92 },
    { "imdb_id": "tt1130884", "score": 0.90 }
  ],
  "server_version": "v1.2.347",
  "filtered_to_owned": true,
  "next_cursor": null
}
```

### 4.2 Similar by IMDb
`GET /similar?imdb_id=tt0114369&plot=true&mood=true&themes=false&genre=true&limit=200`

Response JSON (same structure as search).

### 4.3 Bulk relevance (optional)
`POST /relevance/bulk` → body: `{ "seeds":["tt...","tt..."], "limit": 200 }`

### 4.4 Enhanced search
`GET /v1/search`

Enhanced search endpoint supporting multiple query types and metadata resolution.

Query parameters:
- `q`: Text query for title/year/people/genres
- `imdb_id[]`: Array of IMDb IDs to resolve metadata
- `limit`: Maximum results (default: 50, max: 200)
- `cursor`: Pagination cursor

Response JSON:
```json
{
  "results": [
    {
      "imdb_id": "tt1234567",
      "score": 0.95,
      "title": "Example Movie",
      "year": 2023,
      "genres": ["Action", "Thriller"]
    }
  ],
  "next_cursor": "search_cursor_abc",
  "total_found": 1247
}
```

---

## 5. Movie Metadata

### 5.1 Get movie details
`GET /v1/movies/:imdb_id`

Returns minimal metadata needed for UI display plus versions summary.

Response JSON:
```json
{
  "imdb_id": "tt1234567",
  "title": "Example Movie",
  "year": 2023,
  "poster_url": "https://example.com/poster.jpg",
  "genres": ["Action", "Thriller"],
  "rating": 8.5,
  "versions_summary": {
    "total_versions": 2,
    "qualities": ["1080p", "2160p"],
    "has_hdr": true,
    "has_atmos": false
  }
}
```

---

## 6. Lists Management

### 6.1 Bulk upsert lists
`POST /v1/lists/bulk-upsert`

Upsert or replace user lists by name or stable list_id. Items contain IMDb IDs with optional ordering.

Request JSON:
```json
{
  "lists": [
    {
      "list_id": "list_123",
      "name": "My Favorites",
      "items": [
        {
          "imdb_id": "tt1234567",
          "order_score": 100
        },
        {
          "imdb_id": "tt7654321",
          "order_score": 95
        }
      ]
    }
  ]
}
```

Response JSON:
```json
{
  "processed_lists": 1,
  "total_items": 2,
  "upserted_lists": 1,
  "updated_items": 2
}
```

---

## 7. Utility & Reference

### 5.1 Validate IMDb IDs
`POST /utils/validate-imdb`  
Body: `{ "imdb_ids": ["tt1234567", "tt7654321"] }`  
Response: `{ "valid": ["tt1234567"], "invalid": ["tt7654321"] }`

### 5.2 Coverage / readiness
`GET /utils/coverage?imdb_id=tt1234567`  
Returns whether the item is in the server’s index and eligible for similarity/search. Useful to explain delays after initial upload.

---

## 8. Errors

Standardized error body:
```json
{
  "error": "invalid_request",
  "message": "X-Chunk-Index missing",
  "status": 400,
  "hint": "Provide chunk headers for NDJSON uploads"
}
```

Common errors:
- `401 unauthorized` (missing/expired token)
- `403 forbidden` (insufficient scope)
- `404 not_found`
- `409 conflict` (concurrent replace in progress; include `retry_after_ms`)
- `413 payload_too_large` (enforce chunk sizes, e.g., ≤ 5 MB or ≤ 10k lines)
- `422 unprocessable_entity` (invalid IMDb ID format)
- `429 too_many_requests` (rate limiting; include reset headers)
- `5xx` server errors (include `incident_id`)

---

## 9. Security & Abuse Prevention

- All endpoints behind TLS.
- Token scopes and expiration; refresh via pairing flow.
- Optional IP throttling and device fingerprinting fields.
- Idempotency keys required on mutating requests.
- NDJSON upload limits: e.g., ≤ 10,000 lines per chunk, ≤ 5 MB per request.
- Server **must** ignore duplicate IMDb IDs within the same request (set semantics).

---

## 10. Client Recommendations (Kodi Add-on)

### 10.1 Bulk sync (original approach)
- Use **NDJSON** uploads with chunks of ~5–10k IMDb IDs; include `Idempotency-Key` and chunk headers.
- For **replace**: start a session, upload chunks, then send a **finalize** flag or allow server to auto-finalize on last chunk.
- Poll `/library/status` for coverage as the backend ingests newly seen titles.

### 10.2 Differential sync (CLIENT-KODI-SERVICE)
- **Check version first**: Use `GET /v1/library/version` to avoid unnecessary full fetches.
- **Compute diffs locally**: Compare current Kodi library with stored snapshot to identify adds/removes.
- **Batch changes**: Group adds/removes into chunks (500-5k IDs) with `Idempotency-Key` headers.
- **Handle partial failures**: Store failed operations in pending queue for retry.
- **Respect rate limits**: Include generous sleep and jitter between operations.
- **Avoid playback interference**: Skip sync during video playback or pause.
- **Persist state**: Save local snapshots, server version/etag, and pending queues to disk.

### 10.3 General recommendations
- For search/similarity UI: call with `in_library=true` to get only owned results.
- Cache successful IMDb→Kodi DBID mappings locally; invalidate on library updates.
- Implement retry with exponential backoff on `409`, `429`, `5xx`.

---

## 11. Example NDJSON Lines

```
{ "imdb_id": "tt0111161" }
{ "imdb_id": "tt0068646" }
{ "imdb_id": "tt0468569" }
```

---

## 12. Future Extensions

- Webhook/Push: `/hooks/register` (receive batch-finished events).  
- Collections: `/collections/similar?imdb_id=...` (clustered results).  
- User export: `/library/dump` (full set as NDJSON).  
- Per-title notes/tags (client-supplied metadata) with strict size limits.  

---

**End of v1 draft**