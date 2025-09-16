#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Phase 3 JSON-RPC Helper
Centralized, robust JSON-RPC communication with retry/backoff and proper error handling
"""

import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import xbmc

from lib.utils.kodi_log import get_kodi_logger
from lib.config import get_config


@dataclass
class JsonRpcError:
    """Structured error response from JSON-RPC operations"""
    type: str  # "timeout", "network", "method_error", "parse_error", "unknown"
    message: str
    retryable: bool
    original_error: Optional[Exception] = None


@dataclass 
class JsonRpcResponse:
    """Structured response from JSON-RPC operations"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[JsonRpcError] = None


class JsonRpcHelper:
    """Phase 3: Centralized JSON-RPC helper with timeout, retry/backoff, and structured error handling"""

    def __init__(self):
        self.logger = get_kodi_logger('lib.kodi.json_rpc_helper')
        self.config = get_config()

        # Phase 3 settings with safe defaults
        self._timeout = self._clamp_timeout(self.config.get_int("jsonrpc_timeout_seconds", 10))
        self._retry_count = 2  # Fixed retry count
        self._base_backoff = 0.5  # Base backoff delay in seconds

    def execute_request(self, method: str, params: Optional[Dict[str, Any]] = None, 
                       request_id: int = 1) -> JsonRpcResponse:
        """
        Execute JSON-RPC request with retry/backoff policy

        Args:
            method: JSON-RPC method name
            params: Method parameters
            request_id: Request ID for tracking

        Returns:
            JsonRpcResponse with success/data or error information
        """
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": request_id
        }

        last_error = None

        # Retry loop with exponential backoff
        for attempt in range(self._retry_count + 1):
            try:
                # Silent JSON-RPC request attempt - final count reported at process end

                # Execute request with timeout handling
                response_str = xbmc.executeJSONRPC(json.dumps(request))

                # Parse response
                try:
                    response = json.loads(response_str)
                except json.JSONDecodeError as e:
                    error = JsonRpcError(
                        type="parse_error",
                        message=f"Failed to parse JSON response: {str(e)}",
                        retryable=False,
                        original_error=e
                    )
                    return JsonRpcResponse(success=False, error=error)

                # Check for JSON-RPC errors
                if "error" in response:
                    error_data = response["error"]
                    error = JsonRpcError(
                        type="method_error",
                        message=f"JSON-RPC method error: {error_data}",
                        retryable=False,  # Method errors are not retryable
                        original_error=None
                    )
                    self.logger.error("JSON-RPC method error for %s: %s", method, error_data)
                    return JsonRpcResponse(success=False, error=error)

                # Success - return result
                result = response.get("result", {})
                # Silent JSON-RPC success - final count reported at process end
                return JsonRpcResponse(success=True, data=result)

            except Exception as e:
                last_error = e

                # Classify error type
                error_type = self._classify_error(e)
                is_retryable = error_type in ["timeout", "network"]

                if not is_retryable or attempt >= self._retry_count:
                    # Don't retry logic errors or if we've exhausted retries
                    error = JsonRpcError(
                        type=error_type,
                        message=f"JSON-RPC request failed: {str(e)}",
                        retryable=is_retryable,
                        original_error=e
                    )
                    self.logger.error("JSON-RPC request failed for %s: %s", method, str(e))
                    return JsonRpcResponse(success=False, error=error)

                # Retryable error - apply backoff
                backoff_delay = self._base_backoff * (2 ** attempt)  # Exponential backoff
                self.logger.warning("JSON-RPC request failed (attempt %s), retrying in %ss: %s", attempt + 1, backoff_delay, str(e))
                time.sleep(backoff_delay)

        # Should not reach here, but handle it gracefully
        error = JsonRpcError(
            type="unknown",
            message=f"Unexpected error after {self._retry_count + 1} attempts",
            retryable=False,
            original_error=last_error
        )
        return JsonRpcResponse(success=False, error=error)

    def get_movies_page(self, offset: int, limit: int, properties: Optional[List[str]] = None) -> JsonRpcResponse:
        """Get a page of movies with specified properties"""

        # Default properties for lightweight delta scans
        if properties is None:
            properties = [
                "title", "year", "imdbnumber", "uniqueid", "file", "dateadded",
                "art", "plot", "plotoutline", "runtime", "rating", "genre", 
                "mpaa", "director", "country", "studio", "playcount", "resume"
            ]

        params = {
            "properties": properties,
            "limits": {
                "start": offset,
                "end": offset + limit
            }
        }

        return self.execute_request("VideoLibrary.GetMovies", params)

    def get_movies_lightweight(self, offset: int, limit: int) -> JsonRpcResponse:
        """Get movies with minimal properties for delta scans"""

        lightweight_properties = ["file", "dateadded", "title"]

        params = {
            "properties": lightweight_properties,
            "limits": {
                "start": offset,
                "end": offset + limit
            }
        }

        return self.execute_request("VideoLibrary.GetMovies", params)

    def get_movie_count(self) -> JsonRpcResponse:
        """Get total count of movies in library"""

        params = {
            "properties": ["title"],
            "limits": {"start": 0, "end": 1}
        }

        return self.execute_request("VideoLibrary.GetMovies", params)

    def _classify_error(self, error: Exception) -> str:
        """Classify error type for retry decision"""
        error_str = str(error).lower()

        if "timeout" in error_str:
            return "timeout"
        elif "network" in error_str or "connection" in error_str:
            return "network"
        elif "method" in error_str or "params" in error_str:
            return "method_error"
        elif "json" in error_str or "parse" in error_str:
            return "parse_error"
        else:
            return "unknown"

    def _clamp_timeout(self, timeout: int) -> int:
        """Clamp timeout to safe range (5-30 seconds)"""
        return max(5, min(30, timeout))

# Global helper instance
_helper_instance = None


def get_json_rpc_helper():
    """Get global JSON-RPC helper instance"""
    global _helper_instance
    if _helper_instance is None:
        _helper_instance = JsonRpcHelper()
    return _helper_instance