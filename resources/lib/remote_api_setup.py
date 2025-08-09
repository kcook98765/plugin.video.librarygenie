
import xbmcgui
from resources.lib import utils
from resources.lib.remote_api_client import RemoteAPIClient
from resources.lib.config_manager import Config

def setup_remote_api():
    """Setup wizard for remote API integration"""
    config = Config()
    remote_client = RemoteAPIClient()
    
    # Check if already configured
    if config.get_setting('remote_api_key'):
        if remote_client.test_connection():
            xbmcgui.Dialog().ok("Remote API", "Remote API is already configured and working!")
            return True
        else:
            # API key exists but doesn't work - offer to reconfigure
            if xbmcgui.Dialog().yesno("Remote API", "Existing API key is not working. Reconfigure?"):
                config.set_setting('remote_api_key', '')
                config.set_setting('remote_api_url', '')
            else:
                return False
    
    # Show setup instructions
    instructions = (
        "Remote API Setup\n\n"
        "1. Visit the web dashboard\n"
        "2. Generate a pairing code\n"
        "3. Enter the 8-digit code below\n\n"
        "This will automatically configure your addon."
    )
    
    xbmcgui.Dialog().ok("Setup Instructions", instructions)
    
    # Prompt for pairing code
    pairing_code = xbmcgui.Dialog().input("Enter Pairing Code", type=xbmcgui.INPUT_ALPHANUM)
    
    if not pairing_code or len(pairing_code) != 8:
        xbmcgui.Dialog().ok("Invalid Code", "Please enter a valid 8-digit pairing code.")
        return False
    
    # Show progress dialog
    progress = xbmcgui.DialogProgress()
    progress.create("Setting up Remote API", "Exchanging pairing code...")
    progress.update(50)
    
    # Exchange pairing code
    success = remote_client.exchange_pairing_code(pairing_code)
    
    progress.close()
    
    if success:
        # Test connection
        if remote_client.test_connection():
            xbmcgui.Dialog().ok("Setup Complete", "Remote API has been successfully configured!")
            return True
        else:
            xbmcgui.Dialog().ok("Setup Error", "Pairing successful but connection test failed.")
            return False
    else:
        xbmcgui.Dialog().ok("Setup Failed", "Failed to exchange pairing code. Please try again.")
        return False

def manual_setup_remote_api():
    """Manual setup for advanced users"""
    config = Config()
    
    # Get server URL
    server_url = xbmcgui.Dialog().input("Server URL", defaultt="https://your-server.com")
    if not server_url:
        return False
    
    # Get API key
    api_key = xbmcgui.Dialog().input("API Key", type=xbmcgui.INPUT_ALPHANUM)
    if not api_key or len(api_key) != 64:
        xbmcgui.Dialog().ok("Invalid API Key", "API key should be 64 characters long.")
        return False
    
    # Save settings
    config.set_setting('remote_api_url', server_url)
    config.set_setting('remote_api_key', api_key)
    
    # Test connection
    remote_client = RemoteAPIClient()
    if remote_client.test_connection():
        xbmcgui.Dialog().ok("Setup Complete", "Remote API has been manually configured!")
        return True
    else:
        xbmcgui.Dialog().ok("Setup Failed", "Connection test failed. Please check your settings.")
        return False
