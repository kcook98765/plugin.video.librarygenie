""" /resources/lib/addon_helper.py """
import sys
import urllib.parse
import xbmc
from resources.lib.config_manager import Config
from resources.lib.database_manager import DatabaseManager
from resources.lib.kodi_helper import KodiHelper
from resources.lib.llm_api_manager import LLMApiManager
from resources.lib.user_interaction_manager import UserInteractionManager
from resources.lib.window_main import MainWindow
from resources.lib.utils import get_addon_handle, log # Added import for utils.log

from resources.lib import utils

class AddonContext:
    def __init__(self):
        self.ADDON_HANDLE = get_addon_handle()
        self.CONFIG = Config()
        self.db_manager = DatabaseManager(self.CONFIG.db_path)
        self.ui_manager = UserInteractionManager(self.ADDON_HANDLE)
        self.llm_api_manager = LLMApiManager()
        self.kodihelper = KodiHelper(self.ADDON_HANDLE)
        self.base_path = self.CONFIG.addon.getAddonInfo('path')
        self.db_manager.setup_database()

    def log_arguments(self):
        for i, arg in enumerate(sys.argv):
            utils.log(f"sys.argv[{i}] = {arg}", "DEBUG")

    def parse_args(self):
        return urllib.parse.parse_qs(sys.argv[2][1:]) if len(sys.argv) > 2 else {}

def run_addon():
    log("Running addon...", "DEBUG")
    context = AddonContext()
    context.log_arguments()
    args = context.parse_args()
    log(f"Args - {args}", "DEBUG")
    action = args.get('action', [None])[0] or sys.argv[1] if len(sys.argv) > 1 else None
    log(f"Action - {action}", "DEBUG")
    action_handlers = {
        "show_folder": lambda: show_folder(context.db_manager, context.kodihelper, args),
        "show_list": lambda: show_list(context.db_manager, context.kodihelper, args),
        "show_main_window": lambda: show_main_window(context.kodihelper),
        "show_info": lambda: show_info(context.kodihelper),
        "context_action": lambda: context.ui_manager.context_menu_action(args.get("context_action", [None])[0]) if args.get("context_action") else utils.show_notification("Error", "No context action specified"),
        "play_item": lambda: context.kodihelper.play_item({'title': xbmc.getLocalizedString(30011)}),
        "save_item": lambda: context.ui_manager.save_list_item(int(args.get('list_id', [0])[0]), context.kodihelper.get_focused_item_details()),
        "flag_item": lambda: context.ui_manager.flag_list_item(int(args.get('item_id', [0])[0])),
        "default": lambda: list_root_folders_and_lists(context.db_manager, context.kodihelper)
    }
    try:
        action_handlers.get(action, action_handlers["default"])()
    except Exception as e:
        log(f"Error running addon: {str(e)}", "ERROR") # Updated error logging
        import xbmcgui #Import here to avoid circular dependency
        xbmcgui.Dialog().notification("LibraryGenie", "Error running addon", xbmcgui.NOTIFICATION_ERROR, 5000)

def show_folder(db_manager, kodihelper, args):
    folder_id = int(args.get('folder_id', [None])[0])
    utils.log(f"Showing folder ID {folder_id}...", "DEBUG")
    folders = db_manager.fetch_folders(folder_id)
    lists = db_manager.fetch_lists(folder_id)
    kodihelper.list_folders_and_lists(folders, lists)

def show_list(db_manager, kodihelper, args):
    utils.log("Showing list...", "DEBUG")
    list_id = int(args.get('list_id', [0])[0])
    items = db_manager.fetch_list_items(list_id)
    kodihelper.list_items(items)

def show_main_window(kodihelper):
    utils.log("Showing Main window...", "DEBUG")
    db_id = xbmc.getInfoLabel('ListItem.DBID')
    item_info = kodihelper.get_focused_item_details() if db_id.isdigit() and int(db_id) > 0 else kodihelper.get_focused_item_basic_info()
    window = MainWindow(item_info)
    window.doModal()

def show_info(kodihelper):
    utils.log("Showing info...", "DEBUG")
    kodihelper.show_information()

def list_root_folders_and_lists(db_manager, kodihelper):
    utils.log("Default action - listing root folders and lists", "DEBUG")
    root_folders = db_manager.fetch_folders(None)
    root_lists = db_manager.fetch_lists(None)
    kodihelper.list_folders_and_lists(root_folders, root_lists)

def show_window(window_class):
    window = window_class()
    window.doModal()
    del window