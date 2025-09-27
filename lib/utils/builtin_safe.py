"""
Safe builtin command execution utility to prevent command injection vulnerabilities.

This module provides secure wrappers around xbmc.executebuiltin to prevent
URL-based command injection attacks where malicious URLs could break out of
builtin command arguments and inject unintended commands.
"""
import xbmc
import logging

logger = logging.getLogger(__name__)

def safe_executebuiltin(command_template, *args):
    """
    Safely execute builtin command with proper argument escaping.
    
    Args:
        command_template (str): Command template with {} placeholders for arguments
        *args: Arguments to safely insert into the template
        
    Example:
        safe_executebuiltin('Container.Update("{}")', some_url)
        safe_executebuiltin('ActivateWindow(Videos,"{}",return)', path)
        safe_executebuiltin('PlayMedia("{}")', media_path)
    """
    # Escape dangerous characters in all arguments
    escaped_args = []
    for arg in args:
        if isinstance(arg, str):
            # Escape quotes, backslashes, and other characters that could break builtin syntax
            escaped_arg = (
                str(arg)
                .replace('\\', '\\\\')  # Escape backslashes first
                .replace('"', '\\"')    # Escape double quotes
                .replace("'", "\\'")    # Escape single quotes
                .replace('(', '\\(')    # Escape parentheses
                .replace(')', '\\)')
                .replace(',', '\\,')    # Escape commas
            )
            escaped_args.append(escaped_arg)
        else:
            escaped_args.append(str(arg))
    
    # Format the command safely
    try:
        command = command_template.format(*escaped_args)
        logger.debug("Executing safe builtin command: %s", command)
        xbmc.executebuiltin(command)
    except Exception as e:
        logger.error("Failed to execute builtin command '%s': %s", command_template, e)
        raise

def safe_container_update(url, replace=False):
    """Safely update container to a URL."""
    if replace:
        safe_executebuiltin('Container.Update("{}", replace)', url)
    else:
        safe_executebuiltin('Container.Update("{}")', url)

def safe_activate_window(window, path=None, return_focus=False):
    """Safely activate a window with optional path."""
    if path and return_focus:
        safe_executebuiltin('ActivateWindow({},"{}", return)', window, path)
    elif path:
        safe_executebuiltin('ActivateWindow({},"{}")', window, path)
    else:
        safe_executebuiltin('ActivateWindow({})', window)

def safe_run_plugin(plugin_url):
    """Safely run a plugin URL."""
    safe_executebuiltin('RunPlugin("{}")', plugin_url)

def safe_play_media(media_path):
    """Safely play media from a path."""
    safe_executebuiltin('PlayMedia("{}")', media_path)

def safe_set_property(property_name, value):
    """Safely set a window property with proper value escaping."""
    safe_executebuiltin('SetProperty({},"{}")', property_name, value)