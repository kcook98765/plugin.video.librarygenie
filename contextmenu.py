
import xbmcaddon

# This file exists to make Kodi recognize this as a context menu addon
# The actual context menu logic is in context.py

def main():
    """Context menu entry point - delegates to context.py"""
    import context
    context.main()

if __name__ == '__main__':
    main()
