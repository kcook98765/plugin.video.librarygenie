import json
import pyxbmct
import xbmcgui
from resources.lib.database_manager import DatabaseManager
from resources.lib.config_manager import Config
from resources.lib.window_results import ResultsWindow
from resources.lib import utils

class GenieWindow(pyxbmct.AddonDialogWindow):
    _instance = None
    _initialized = False

    def __new__(cls, list_id, title="Genie List Setup"):
        if cls._instance is None:
            cls._instance = super(GenieWindow, cls).__new__(cls)
            if not GenieWindow._initialized:
                utils.log("Genie Window module initialized", "INFO")
                GenieWindow._initialized = True
        return cls._instance

    def __init__(self, list_id, title="Genie List Setup"):
        super().__init__(title)
        self.setGeometry(800, 600, 10, 10)
        self.list_id = list_id
        self.db_manager = DatabaseManager(Config().db_path)  # Use Config to get the db_path
        self.genie_list = self.db_manager.get_genie_list(self.list_id)
        self.setup_ui()
        self.populate_fields()
        self.set_navigation()

    def setup_ui(self):
        self.description_label = pyxbmct.Label("GenieList Description")
        self.placeControl(self.description_label, 0, 0, columnspan=10, pad_x=10, pad_y=10)

        self.description_input = pyxbmct.Edit(self.genie_list['description'] if self.genie_list else "")
        self.placeControl(self.description_input, 1, 0, rowspan=1, columnspan=10, pad_x=10, pad_y=10)

        self.submit_button = pyxbmct.Button('Submit')
        self.placeControl(self.submit_button, 2, 3, columnspan=4)  # Increase columnspan to make the button wider
        self.connect(self.submit_button, self.on_submit_button_click)

        if self.genie_list:
            self.remove_button = pyxbmct.Button('Remove')
            self.placeControl(self.remove_button, 3, 3, columnspan=4)  # Increase columnspan to make the button wider
            self.connect(self.remove_button, self.on_remove_button_click)

        self.close_button = pyxbmct.Button('Close')
        self.placeControl(self.close_button, 4, 3, columnspan=4)  # Increase columnspan to make the button wider
        self.connect(self.close_button, self.close)

    def populate_fields(self):
        if self.genie_list:
            self.description_input.setText(self.genie_list['description'])

    def set_navigation(self):
        self.description_input.controlDown(self.submit_button)
        self.description_input.controlUp(self.close_button)
        self.submit_button.controlDown(self.close_button)
        self.submit_button.controlUp(self.description_input)
        if self.genie_list:
            self.submit_button.controlRight(self.remove_button)
            self.remove_button.controlDown(self.close_button)
            self.remove_button.controlUp(self.description_input)
            self.remove_button.controlLeft(self.submit_button)
        self.close_button.controlDown(self.description_input)
        self.close_button.controlUp(self.submit_button)
        self.setFocus(self.description_input)

    def on_submit_button_click(self):
        description = self.description_input.getText()

        # Ensure the description is not empty
        if not description:
            xbmcgui.Dialog().notification("LibraryGenie", "Description cannot be empty", xbmcgui.NOTIFICATION_WARNING, 5000)
            return

        rpc, name, movies = self.llm_api_manager.generate_query(description)

        # Check if rpc and name are valid before proceeding
        if not rpc or not name:
            utils.log(f"Invalid RPC or Name returned from LLMApiManager. RPC: {rpc}, Name: {name}")
            return

        if self.genie_list:
            self.db_manager.update_genie_list(self.list_id, description, rpc)
        else:
            self.db_manager.insert_genie_list(self.list_id, description, rpc)

        self.display_results(rpc, name, movies)
        self.close()

    def display_results(self, rpc, name, movies):
        window_results = ResultsWindow(
            rpc=rpc,
            name=name,
            list_id=self.list_id,
            movies=movies
        )
        window_results.doModal()
        del window_results

    def on_remove_button_click(self):
        confirm = xbmcgui.Dialog().yesno("Confirm Removal", "Do you want to remove the GenieList?")
        if confirm:
            self.db_manager.delete_genie_list(self.list_id)
            self.close()

    def close(self):
        utils.log("Closing GenieWindow")
        pyxbmct.AddonDialogWindow.close(self)
        del self

    def __del__(self):
        utils.log("Deleting GenieWindow instance")