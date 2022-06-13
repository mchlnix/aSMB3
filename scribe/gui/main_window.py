from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMenu, QMessageBox

from foundry.game.File import ROM
from foundry.game.level.LevelRef import LevelRef
from foundry.gui.MainWindow import ROM_FILE_FILTER
from foundry.gui.WorldView import WorldView
from scribe.gui.world_view_context_menu import WorldContextMenu
from smb3parse.levels.world_map import WorldMap
from smb3parse.objects.object_set import WORLD_MAP_OBJECT_SET


class MainWindow(QMainWindow):
    def __init__(self, path_to_rom: str):
        super(MainWindow, self).__init__()

        self.on_open_rom(path_to_rom)

        self.world = WorldMap.from_world_number(ROM(), 1)

        self.level_ref = LevelRef()
        self.level_ref.load_level("World", self.world.layout_address, 0x0, WORLD_MAP_OBJECT_SET)

        self.world_view = WorldView(self, self.level_ref, WorldContextMenu(self.level_ref))
        self.world_view.zoom_in()
        self.world_view.zoom_in()

        self.view_menu = QMenu("View")
        self.view_menu.triggered.connect(self.on_view_menu)

        self.level_pointer_action = self.view_menu.addAction("Show Level Pointers")
        self.level_pointer_action.setCheckable(True)
        self.level_pointer_action.setChecked(self.world_view.draw_level_pointers)

        self.sprite_action = self.view_menu.addAction("Show Overworld Sprites")
        self.sprite_action.setCheckable(True)
        self.sprite_action.setChecked(self.world_view.draw_sprites)

        self.starting_point_action = self.view_menu.addAction("Show Starting Point")
        self.starting_point_action.setCheckable(True)
        self.starting_point_action.setChecked(self.world_view.draw_start)

        self.menuBar().addMenu(self.view_menu)

        self.setCentralWidget(self.world_view)

        self.show()

    def on_open_rom(self, path_to_rom="") -> bool:
        if not path_to_rom:
            # otherwise ask the user what new file to open
            path_to_rom, _ = QFileDialog.getOpenFileName(self, caption="Open ROM", filter=ROM_FILE_FILTER)

            if not path_to_rom:
                return False

        # Proceed loading the file chosen by the user
        try:
            ROM.load_from_file(path_to_rom)
        except IOError as exp:
            QMessageBox.warning(self, type(exp).__name__, f"Cannot open file '{path_to_rom}'.")
            return False

    def on_view_menu(self, action: QAction):
        if action is self.level_pointer_action:
            self.world_view.draw_level_pointers = action.isChecked()
        elif action is self.sprite_action:
            self.world_view.draw_sprites = action.isChecked()
        elif action is self.starting_point_action:
            self.world_view.draw_start = action.isChecked()

        self.world_view.update()
