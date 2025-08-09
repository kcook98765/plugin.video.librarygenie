""" /main.py """
import os
import sys

# Add addon directory to Python path
addon_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(addon_dir)

from resources.lib.addon_helper import run_addon

if __name__ == '__main__':
    run_addon()