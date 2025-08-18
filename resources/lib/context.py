
import os
import sys

# Add addon directory to Python path for proper module resolution
addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if addon_dir not in sys.path:
    sys.path.insert(0, addon_dir)

# Now import the actual implementation
from resources.lib.core.context import main as _main

def run(*args, **kwargs):
    return _main(*args, **kwargs)

if __name__ == "__main__":
    run()
