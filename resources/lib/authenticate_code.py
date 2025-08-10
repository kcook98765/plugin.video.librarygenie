
import json
import urllib.request
import urllib.parse
import xbmc
import xbmcgui
from resources.lib.addon_ref import get_addon
from resources.lib.utils import log, show_notification, show_dialog_ok

def authenticate_with_code():
    """Handle one-time code authentication from settings"""
    addon = get_addon()
    dialog = xbmcgui.Dialog()
    
    # Get the one-time code from user input
    code = dialog.input("Enter One-Time Code", type=xbmcgui.INPUT_ALPHANUM)
    
    if not code or len(code) != 6:
        show_notification("LibraryGenie", "Invalid code format. Please enter a 6-digit code.", xbmcgui.NOTIFICATION_ERROR, 3000)
        return False
    
    # Get the API URL from settings
    api_base_url = addon.getSetting('lgs_upload_url').rstrip('/')
    verify_url = f"{api_base_url}/api/v1/api_info/verify-code"
    
    try:
        # Prepare the request data
        request_data = json.dumps({"code": code}).encode('utf-8')
        
        # Create the request
        req = urllib.request.Request(
            verify_url,
            data=request_data,
            headers={'Content-Type': 'application/json'}
        )
        
        # Make the API call
        log(f"Sending verification request to: {verify_url}", "INFO")
        
        with urllib.request.urlopen(req) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            
        log(f"Verification response: {response_data}", "DEBUG")
        
        if response_data.get('status') == 'success':
            # Extract the authentication data
            auth_token = response_data.get('auth_token')
            username = response_data.get('username')
            user_id = response_data.get('user_id')
            
            if auth_token and username:
                # Store the authentication data in addon settings
                addon.setSetting('lgs_upload_key', auth_token)
                addon.setSetting('lgs_username', username)
                
                # Clear the password field since we're using token authentication
                addon.setSetting('lgs_password', '')
                
                log(f"Authentication successful for user: {username}", "INFO")
                
                # Show success message
                success_message = f"Authentication successful!\nUsername: {username}\nAPI token has been saved."
                show_dialog_ok("Authentication Success", success_message)
                
                return True
            else:
                log("Missing auth_token or username in response", "ERROR")
                show_dialog_ok("Authentication Error", "Invalid response from server. Missing authentication data.")
                return False
        else:
            error_message = response_data.get('error', 'Unknown error occurred')
            log(f"Authentication failed: {error_message}", "ERROR")
            show_dialog_ok("Authentication Failed", f"Failed to verify code: {error_message}")
            return False
            
    except urllib.error.HTTPError as e:
        error_msg = f"HTTP Error {e.code}: {e.reason}"
        if e.code == 400:
            error_msg = "Invalid code format"
        elif e.code == 404:
            error_msg = "Code not found or expired"
        elif e.code == 429:
            error_msg = "Too many attempts. Please try again later"
        
        log(f"HTTP error during authentication: {error_msg}", "ERROR")
        show_dialog_ok("Authentication Error", error_msg)
        return False
        
    except urllib.error.URLError as e:
        error_msg = f"Network error: {e.reason}"
        log(f"Network error during authentication: {error_msg}", "ERROR")
        show_dialog_ok("Connection Error", "Unable to connect to the server. Please check your network connection.")
        return False
        
    except json.JSONDecodeError as e:
        log(f"JSON decode error: {e}", "ERROR")
        show_dialog_ok("Server Error", "Invalid response from server. Please try again.")
        return False
        
    except Exception as e:
        log(f"Unexpected error during authentication: {str(e)}", "ERROR")
        show_dialog_ok("Unexpected Error", f"An unexpected error occurred: {str(e)}")
        return False

if __name__ == '__main__':
    authenticate_with_code()
