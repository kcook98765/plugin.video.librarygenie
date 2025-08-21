import json
import os
import sys
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib.core.logging import Log
from resources.lib.core.plugin import Plugin
from resources.lib.core.requests import Requests
from resources.lib.modules.utils import get_keyboard, get_settings
from resources.lib.config.config_manager import Config
from resources.lib.data.database_manager import DatabaseManager
from resources.lib.data.query_manager import QueryManager

# plugin = Plugin()
# router = plugin.get_router()

# @router.route('/')
# def index():
#     plugin.set_content('files')
#     return browse()

# @router.route('/browse')
# def browse():
#     plugin.set_content('files')
#     items = []
#     items.extend(get_directory(get_settings('music_dirs'), 'Music'))
#     items.extend(get_directory(get_settings('video_dirs'), 'Video'))
#     items.extend(get_directory(get_settings('tv_show_dirs'), 'TV Shows'))
#     items.extend(get_directory(get_settings('movie_dirs'), 'Movies'))
#     return items

# def get_directory(dirs, type):
#     items = []
#     if dirs:
#         for directory in dirs:
#             items.append(
#                 {
#                     'label': directory,
#                     'path': router.url_for('browse_directory', directory=directory, type=type),
#                     'thumbnail': plugin.get_icon('folder.png'),
#                     'type': 'folder'
#                 }
#             )
#     return items

# @router.route('/browse_directory')
# def browse_directory(directory, type):
#     plugin.set_content('files')
#     items = []
#     for f in os.listdir(directory):
#         path = os.path.join(directory, f)
#         if os.path.isdir(path):
#             items.append(
#                 {
#                     'label': f,
#                     'path': router.url_for('browse_directory', directory=path, type=type),
#                     'thumbnail': plugin.get_icon('folder.png'),
#                     'type': 'folder'
#                 }
#             )
#         else:
#             items.append(
#                 {
#                     'label': f,
#                     'path': router.url_for('play_media', path=path, type=type),
#                     'thumbnail': plugin.get_icon('file.png'),
#                     'type': 'file'
#                 }
#             )
#     return items

# @router.route('/play_media')
# def play_media(path, type):
#     plugin.set_content('movies') if type == 'Movies' else plugin.set_content('tvshows')
#     from resources.lib.player import Player
#     player = Player(path)
#     player.play()
#     return []

# @router.route('/create_subfolder')
# def create_subfolder():
#     plugin.set_content('files')
#     folder_name = get_keyboard('Folder Name', 'Enter folder name')
#     if folder_name:
#         from resources.lib.core.navigation_manager import get_navigation_manager
#         nav_manager = get_navigation_manager()
#         nav_manager.refresh_current_container("Subfolder Created")
#         return xbmc.executebuiltin('Container.Refresh')

# def run():
#     plugin.run()

# if __name__ == '__main__':
#     run()