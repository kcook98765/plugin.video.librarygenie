
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LibraryGenie - Device Code Authorization
Implements OAuth2 device code flow for server authorization
"""

import json
import time
import urllib.request
import urllib.error
import xbmcgui
from ..config import get_config
from ..utils.logger import get_logger
from .state import save_tokens

logger = get_logger(__name__)


def _post_request(url, data, timeout=10):
    """Make a POST request with error handling"""
    try:
        json_data = json.dumps(data)
        req = urllib.request.Request(
            url,
            data=bytes(json_data, 'utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            response_data = response.read().decode('utf-8')
            return json.loads(response_data)
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else "No error details"
        logger.error(f"HTTP {e.code} error for {url}: {error_body}")
        raise Exception(f"Server error: {e.code} - {error_body}")
        
    except urllib.error.URLError as e:
        logger.error(f"Network error for {url}: {e}")
        raise Exception(f"Network error: {e}")
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response from {url}: {e}")
        raise Exception("Invalid server response")
        
    except Exception as e:
        logger.error(f"Request failed for {url}: {e}")
        raise


def run_authorize_flow():
    """
    Run the device code authorization flow
    Returns True if authorization succeeded, False otherwise
    """
    logger.info("Starting device authorization flow")
    
    try:
        cfg = get_config()
        base_url = cfg.get('remote_base_url', '').rstrip('/')
        device_name = cfg.get('device_name', 'Kodi')
        poll_interval = int(cfg.get('auth_poll_seconds', 3))
        
        if not base_url or base_url == 'https://YOUR-LIBRARYGENIE/api':
            xbmcgui.Dialog().ok(
                "Configuration Required",
                "Please configure the Remote API Base URL in addon settings before authorizing."
            )
            return False
        
        logger.debug(f"Using server: {base_url}")
        
        # Step 1: Initiate device code flow
        logger.info("Initiating device code flow")
        initiate_data = {"device_name": device_name}
        
        try:
            init_response = _post_request(f"{base_url}/pair/initiate", initiate_data)
        except Exception as e:
            logger.error(f"Failed to initiate authorization: {e}")
            xbmcgui.Dialog().ok(
                "Authorization Failed",
                f"Could not contact server:\n{str(e)[:100]}..."
            )
            return False
        
        # Extract required fields
        user_code = init_response.get('user_code')
        verification_uri = init_response.get('verification_uri')
        device_code = init_response.get('device_code')
        expires_in = int(init_response.get('expires_in', 600))
        
        if not all([user_code, verification_uri, device_code]):
            logger.error(f"Invalid initiate response: {init_response}")
            xbmcgui.Dialog().ok(
                "Authorization Failed",
                "Server returned incomplete authorization data"
            )
            return False
        
        logger.info(f"Device code flow initiated: user_code={user_code}, expires_in={expires_in}")
        
        # Step 2: Show user code and verification URI
        dialog = xbmcgui.Dialog()
        proceed = dialog.yesno(
            "Device Authorization",
            f"Go to: {verification_uri}\n\nEnter code: [B]{user_code}[/B]\n\nClick Yes when you've entered the code on the website.",
            nolabel="Cancel",
            yeslabel="I've Entered the Code"
        )
        
        if not proceed:
            logger.info("User cancelled authorization during code entry")
            return False
        
        # Step 3: Poll for authorization with finite window
        logger.info("Starting authorization polling")
        poll_data = {"device_code": device_code}
        deadline = time.time() + expires_in
        attempt = 0
        max_attempts = min(expires_in // poll_interval, 120)  # Cap at 120 attempts
        
        # Show progress dialog
        progress = xbmcgui.DialogProgress()
        progress.create("Device Authorization", "Waiting for authorization...")
        
        try:
            while time.time() < deadline and attempt < max_attempts:
                attempt += 1
                remaining = int(deadline - time.time())
                
                # Update progress
                percent = int((1 - remaining / expires_in) * 100)
                progress.update(
                    percent,
                    f"Waiting for authorization... (attempt {attempt}/{max_attempts})",
                    f"Time remaining: {remaining} seconds",
                    "Cancel to abort"
                )
                
                # Check if user cancelled
                if progress.iscanceled():
                    logger.info("Authorization cancelled by user")
                    return False
                
                # Poll the server
                try:
                    logger.debug(f"Polling attempt {attempt}, {remaining}s remaining")
                    poll_response = _post_request(f"{base_url}/pair/poll", poll_data)
                    
                    status = poll_response.get('status')
                    
                    if status == 'approved':
                        # Success! Save tokens
                        access_token = poll_response.get('access_token')
                        refresh_token = poll_response.get('refresh_token')
                        
                        if not access_token:
                            raise Exception("No access token in approval response")
                        
                        token_data = {
                            "access_token": access_token,
                            "token_type": poll_response.get('token_type', 'Bearer')
                        }
                        
                        if refresh_token:
                            token_data["refresh_token"] = refresh_token
                        
                        save_tokens(token_data)
                        
                        progress.close()
                        logger.info("Device authorization successful (token not logged for security)")
                        
                        xbmcgui.Dialog().notification(
                            "LibraryGenie",
                            "Device authorized successfully!",
                            xbmcgui.NOTIFICATION_INFO,
                            5000
                        )
                        return True
                        
                    elif status == 'pending':
                        # Still waiting, continue polling
                        logger.debug("Authorization still pending")
                        
                    elif status == 'denied':
                        # User denied authorization
                        progress.close()
                        logger.info("Authorization denied by user")
                        xbmcgui.Dialog().ok(
                            "Authorization Denied",
                            "You denied the authorization request."
                        )
                        return False
                        
                    elif status == 'expired':
                        # Code expired
                        progress.close()
                        logger.info("Authorization code expired")
                        xbmcgui.Dialog().ok(
                            "Authorization Expired",
                            "The authorization code has expired. Please try again."
                        )
                        return False
                        
                    else:
                        logger.warning(f"Unknown poll status: {status}")
                
                except Exception as e:
                    logger.warning(f"Poll attempt {attempt} failed: {e}")
                    # Continue polling unless it's a critical error
                    if "network" in str(e).lower() and attempt < 3:
                        logger.debug("Network error, will retry")
                    else:
                        progress.close()
                        xbmcgui.Dialog().ok(
                            "Authorization Failed",
                            f"Polling failed:\n{str(e)[:100]}..."
                        )
                        return False
                
                # Wait before next poll
                time.sleep(poll_interval)
        
        finally:
            if progress:
                progress.close()
        
        # Timeout reached
        logger.info("Authorization timed out")
        xbmcgui.Dialog().notification(
            "LibraryGenie",
            "Authorization timed out. Please try again.",
            xbmcgui.NOTIFICATION_ERROR,
            5000
        )
        return False
        
    except Exception as e:
        logger.error(f"Authorization flow failed: {e}")
        xbmcgui.Dialog().ok(
            "Authorization Error",
            f"Unexpected error during authorization:\n{str(e)[:100]}..."
        )
        return False


def test_authorization():
    """Test if the current authorization is working"""
    try:
        from ..ui.localization import L
        from .state import get_access_token
        
        token = get_access_token()
        if not token:
            return False, L(34106)  # "Authentication required"
        
        cfg = get_config()
        base_url = cfg.get('remote_base_url', '').rstrip('/')
        
        if not base_url:
            return False, L(30411)  # "Remote server URL"
        
        # Make a test request to verify the token
        req = urllib.request.Request(f"{base_url}/auth/test")
        req.add_header('Authorization', f'Bearer {token}')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.getcode() == 200:
                return True, L(34113)  # "Connection test successful"
            else:
                return False, f"{L(34114)}: {response.getcode()}"  # "Connection test failed"
                
    except Exception as e:
        logger.error(f"Authorization test failed: {e}")
        return False, str(e)
