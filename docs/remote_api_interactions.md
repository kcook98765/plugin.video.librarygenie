# Movie Database API - End-User Guide

## Overview

The Movie Database API provides comprehensive access to movie data management, intelligent search, and AI-powered analysis features. This guide covers all available endpoints and how to use them effectively. Use the following to integrate the addon to this server.

## Base URL

All API endpoints are accessed through:
```
https://your-domain.com/api/v1/
```

## Authentication

### API Token Authentication
Most endpoints require authentication using an API token. Include the token in the X-API-Key header:

```bash
X-API-Key: YOUR_API_TOKEN
```

### Getting Started

1. **Administrator creates your account** with username and credentials via the web admin interface
2. **Administrator generates a one-time code** for your account via the web admin interface
3. **Your app sends the code** to the verify-code endpoint to get your authentication token
4. **Use your auth token** for all authenticated requests

## Available Endpoints

### 1. User Management

#### Verify One-Time Code
Verify a one-time code and get an authentication token for your pre-existing user account.

```http
POST /api/v1/api_info/verify-code
Content-Type: application/json
```

**Request Body:**
```json
{
  "code": "123456"
}
```

**Response:**
```json
{
  "status": "success",
  "auth_token": "your_auth_token_here",
  "expires_at": null,
  "user_id": 42,
  "username": "john_doe"
}
```

**Authentication Flow:**
1. Admin creates user account via web admin interface
2. Admin generates one-time code for user via web admin interface  
3. User enters code in their application
4. Application sends code to this endpoint
5. Server validates code and returns API token and username
6. Application uses API token for all future requests

**Important:** This is the recommended endpoint for remote applications. It returns only the authentication token for your existing user account, tied to the user the admin created the code for.

### 2. Movie Search

#### Intelligent Movie Search
Search your movie collection using natural language queries with intelligent relevance ranking.

```http
POST /api/v1/user_search/search
Content-Type: application/json
X-API-Key: YOUR_API_TOKEN
```

**Request Body:**
```json
{
  "query": "science fiction movies from the 1980s with time travel"
}
```

**Response:**
```json
{
  "results": [
    {
      "imdb_id": "tt0088763",
      "title": "Back to the Future",
      "year": 1985,
      "relevance_score": 0.95,
      "synopsis": "A teenager travels back in time..."
    }
  ],
  "total_results": 1,
  "query_time": 0.45
}
```

**Rate Limiting:** 10 requests per 24 hours (adjustable by admin)

### 3. AI-Powered Analysis

#### RAG (Retrieval-Augmented Generation) Query
Get intelligent analysis and recommendations based on your movie collection.

```http
POST /api/v1/movies_api/rag
Content-Type: application/json
X-API-Key: YOUR_API_TOKEN
```

**Request Body:**
```json
{
  "query": "What are my favorite sci-fi directors and what makes their style unique?"
}
```

**Response:**
```json
{
  "response": "Based on your movie collection, your favorite sci-fi directors include...",
  "relevant_movies": [
    {
      "id": 123,
      "title": "Blade Runner",
      "year": 1982
    }
  ]
}
```

**Rate Limiting:** 60 requests per minute (configurable by admin)

### 4. Data Management

#### List Available Exports
Get a list of all available data exports for your account.

```http
GET /api/v1/user_data/exports
X-API-Key: YOUR_API_TOKEN
```

**Response:**
```json
{
  "exports": [
    {
      "task_id": "task_12345",
      "created_at": "2025-07-13T20:30:00.000Z",
      "files": [
        {
          "filename": "movie_data.json",
          "path": "user_data_exports/123/movie_data.json",
          "size": 2048576,
          "created_at": "2025-07-13T20:30:00.000Z"
        }
      ]
    }
  ]
}
```

#### Download Export File
Download a specific export file from your account.

```http
GET /api/v1/user_data/exports/{export_path}
X-API-Key: YOUR_API_TOKEN
```

**Example:**
```http
GET /api/v1/user_data/exports/user_data_exports/123/movie_data.json
```

**Response:** File download (binary content)

### 5. System Operations

#### Get API Version Information
Get information about available API versions.

```http
GET /api/v1/api_info/versions
```

**Response:**
```json
{
  "versions": [1, 2],
  "current": 1,
  "deprecated": [],
  "supported": [1, 2]
}
```

## Error Handling

### Common Error Responses

#### 400 Bad Request
```json
{
  "error": "Invalid request format",
  "status": "error"
}
```

#### 401 Unauthorized
```json
{
  "error": "API token required",
  "status": "error"
}
```

#### 403 Forbidden
```json
{
  "error": "Admin access required",
  "status": "error"
}
```

#### 404 Not Found
```json
{
  "error": "Resource not found",
  "status": "error"
}
```

#### 429 Rate Limit Exceeded
```json
{
  "error": "Rate limit exceeded. Try again in 14.5 hours.",
  "status": "error"
}
```

#### 500 Internal Server Error
```json
{
  "error": "Internal server error",
  "status": "error"
}
```

## Rate Limiting

Different endpoints have different rate limits:

- **Movie Search** (`/user_search/search`): 10 requests per 24 hours
- **RAG Query** (`/movies_api/rag`): 60 requests per minute
- **Data Export endpoints**: No specific rate limits (subject to general server limits)

Rate limits can be adjusted by administrators through the admin interface.

## Usage Examples

### Complete Workflow Example

```bash
# 1. Admin creates user account (via admin web interface)
# 2. Admin generates a one-time code for the user (via admin web interface)
# 3. User enters code in their application
# 4. Application verifies the code and gets auth token
curl -X POST https://your-domain.com/api/v1/api_info/verify-code \
  -H "Content-Type: application/json" \
  -d '{"code": "123456"}'

# 5. Application uses auth token for API calls
# Example: User searches for movies using the auth token
curl -X POST https://your-domain.com/api/v1/user_search/search \
  -H "Content-Type: application/json" \
  -H "X-API-Key: AUTH_TOKEN" \
  -d '{"query": "action movies with cars"}'

# 4. User gets AI analysis
curl -X POST https://your-domain.com/api/v1/movies_api/rag \
  -H "Content-Type: application/json" \
  -H "X-API-Key: AUTH_TOKEN" \
  -d '{"query": "What are my favorite action movie themes?"}'

# 5. User downloads their data
curl -X GET https://your-domain.com/api/v1/user_data/exports \
  -H "X-API-Key: AUTH_TOKEN"
```

### Python Example

```python
import requests
import json

# Base configuration
BASE_URL = "https://your-domain.com/api/v1"

# Authentication flow:
# 1. Admin creates user account via web admin interface
# 2. Admin generates one-time code for user via web admin interface  
# 3. User enters code in application
# 4. Application sends code to server and gets auth token
def verify_code(code):
    response = requests.post(
        f"{BASE_URL}/api_info/verify-code",
        headers={"Content-Type": "application/json"},
        json={"code": code}
    )

    if response.status_code == 200:
        data = response.json()
        print(f"Authenticated as user: {data['username']}")
        return data["auth_token"]
    else:
        print(f"Error verifying code: {response.status_code} - {response.text}")
        return None

# Step 5: Use auth token for API calls
def search_movies(auth_token, query):
    headers = {
        "X-API-Key": auth_token,
        "Content-Type": "application/json"
    }

    search_data = {"query": query}

    response = requests.post(
        f"{BASE_URL}/user_search/search",
        headers=headers,
        json=search_data
    )

    if response.status_code == 200:
        results = response.json()
        print(f"Found {results['total_results']} movies")
        for movie in results['results']:
            print(f"- {movie['title']} ({movie['year']}) - Score: {movie['relevance_score']}")
        return results
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

# Example usage
if __name__ == "__main__":
    # Replace with your actual one-time code (provided by admin)
    ONE_TIME_CODE = "123456"

    # Step 4: Get auth token by verifying code
    auth_token = verify_code(ONE_TIME_CODE)

    if auth_token:
        # Step 5: Use auth token for API calls
        search_movies(auth_token, "romantic comedies from the 90s")
```

## Best Practices

### 1. Authentication
- Store API tokens securely (environment variables, secure storage)
- Never expose API tokens in client-side code
- Regenerate tokens if compromised

### 2. Rate Limiting
- Implement exponential backoff for rate-limited requests
- Cache results when possible to reduce API calls
- Monitor your usage to avoid hitting limits

### 3. Error Handling
- Always check response status codes
- Implement proper error handling for all possible responses
- Log errors for debugging purposes

### 4. Data Export
- Regularly export your data for backup purposes
- Check export availability before attempting downloads
- Handle large file downloads appropriately

### 5. Search Optimization
- Use descriptive, natural language queries for better results
- Combine multiple search terms for more precise results
- Consider relevance scores when processing results

## Support

For technical issues, API questions, or access requests:
- Check the admin interface documentation at `/admin/api-docs`
- Review the OpenAPI specification at `/api/docs/json`
- Contact your system administrator for account-related issues

## Changelog

### Version 1.0.0
- Initial API release
- Basic user management endpoints
- Movie search and RAG functionality
- Data export capabilities
- Vector database synchronization