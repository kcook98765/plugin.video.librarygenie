
import sys
import os

# Add the addon root directory to Python path
addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

from resources.lib.config.addon_helper import run_addon

if __name__ == "__main__":
    # This will receive ["setup_remote_api"] etc.
    run_addon()
