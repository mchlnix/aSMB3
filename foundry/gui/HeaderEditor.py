from typing import Optional

from PySide2.QtCore import Signal, SignalInstance
from PySide2.QtGui import QWindow
from PySide2.QtWidgets import QGroupBox, QComboBox, QCheckBox, QVBoxLayout, QFormLayout

from foundry.game.level.Level import Level
from foundry.game.level.LevelRef import LevelRef
from foundry.gui.CustomDialog import CustomDialog
from foundry.gui.LevelSelector import OBJECT_SET_ITEMS
from foundry.gui.Spinner import Spinner

LEVEL_LENGTHS = [0x10 * (i + 1) for i in range(0, 2 ** 4)]
STR_LEVEL_LENGTHS = [f"{length - 1:0=#4X} / {length} Blocks".replace("X", "x") for length in LEVEL_LENGTHS]

# todo check if correct order
X_POSITIONS = [0x01, 0x07, 0x08, 0x0D]
STR_X_POSITIONS = [f"{position:0=#4X} / {position}. Block".replace("X", "x") for position in X_POSITIONS]

# todo check if correct order
Y_POSITIONS = [0x01, 0x05, 0x08, 0x0C, 0x10, 0x14, 0x17, 0x18]
STR_Y_POSITIONS = [f"{position:0=#4X} / {position}. Block".replace("X", "x") for position in Y_POSITIONS]

ACTIONS = [
    "None",
    "Sliding",
    "Out of pipe ↑",
    "Out of pipe ↓",
    "Out of pipe ←",
    "Out of pipe →",
    "Running and climbing up ship",
    "Ship auto scrolling",
]

MUSIC_ITEMS = [
    "Plain level",
    "Underground",
    "Water level",
    "Fortress",
    "Boss",
    "Ship",
    "Battle",
    "P-Switch/Mushroom house (1)",
    "Hilly level",
    "Castle room",
    "Clouds/Sky",
    "P-Switch/Mushroom house (2)",
    "No music",
    "P-Switch/Mushroom house (1)",
    "No music",
    "World 7 map",
]

GRAPHIC_SETS = [
    "Mario graphics (1)",
    "Plain",
    "Fortress",
    "Underground (1)",
    "Sky",
    "Pipe/Water (1, Piranha Plant)",
    "Pipe/Water (2, Water)",
    "Mushroom house (1)",
    "Pipe/Water (3, Pipe)",
    "Desert",
    "Ship",
    "Giant",
    "Ice",
    "Clouds",
    "Underground (2)",
    "Spade bonus room",
    "Spade bonus",
    "Mushroom house (2)",
    "Pipe/Water (4)",
    "Hills",
    "Plain 2",
    "Tank",
    "Castle",
    "Mario graphics (2)",
    "Animated graphics (1)",
    "Animated graphics (2)",
    "Animated graphics (3)",
    "Animated graphics (4)",
    "Animated graphics (P-Switch)",
    "Game font/Course Clear graphics",
    "Animated graphics (5)",
    "Animated graphics (6)",
]

TIMES = ["300", "400", "200", "Unlimited"]

SCROLL_DIRECTIONS = [
    "Locked, unless climbing/flying",
    "Free vertical scrolling",
    "Locked 'by start coordinates'?",
    "Shouldn't appear in game, do not use.",
]


SPINNER_MAX_VALUE = 0x0F_FF_FF


class HeaderEditor(CustomDialog):
    header_change: SignalInstance = Signal()

    def __init__(self, parent: Optional[QWindow], level_ref: LevelRef):
        super(HeaderEditor, self).__init__(parent, "Level Header Editor")

        self.level: Level = level_ref.level
        self.level.data_changed.connect(self.update)
        self.header_change.connect(level_ref.save_level_state)
        self.header_change.connect(self.level.reload)

        main_layout = QVBoxLayout(self)

        # level settings

        self.length_dropdown = QComboBox()
        self.length_dropdown.addItems(STR_LEVEL_LENGTHS)
        self.length_dropdown.activated.connect(self.on_combo)

        self.music_dropdown = QComboBox()
        self.music_dropdown.addItems(MUSIC_ITEMS)
        self.music_dropdown.activated.connect(self.on_combo)

        self.time_dropdown = QComboBox()
        self.time_dropdown.addItems(TIMES)
        self.time_dropdown.activated.connect(self.on_combo)

        self.v_scroll_direction_dropdown = QComboBox()
        self.v_scroll_direction_dropdown.addItems(SCROLL_DIRECTIONS)
        self.v_scroll_direction_dropdown.activated.connect(self.on_combo)

        self.level_is_vertical_cb = QCheckBox()
        self.level_is_vertical_cb.clicked.connect(self.on_check_box)

        self.pipe_ends_level_cb = QCheckBox()
        self.pipe_ends_level_cb.clicked.connect(self.on_check_box)

        self.level_group_box = QGroupBox("Level Settings")

        form = QFormLayout(self.level_group_box)

        form.addRow("Level length: ", self.length_dropdown)
        form.addRow("Music: ", self.music_dropdown)
        form.addRow("Time: ", self.time_dropdown)
        form.addRow("Scroll direction: ", self.v_scroll_direction_dropdown)
        form.addRow("Is Vertical: ", self.level_is_vertical_cb)
        form.addRow("Pipe ends level: ", self.pipe_ends_level_cb)

        main_layout.addWidget(self.level_group_box)

        # player settings

        self.x_position_dropdown = QComboBox()
        self.x_position_dropdown.addItems(STR_X_POSITIONS)
        self.x_position_dropdown.activated.connect(self.on_combo)

        self.y_position_dropdown = QComboBox()
        self.y_position_dropdown.addItems(STR_Y_POSITIONS)
        self.y_position_dropdown.activated.connect(self.on_combo)

        self.action_dropdown = QComboBox()
        self.action_dropdown.addItems(ACTIONS)
        self.action_dropdown.activated.connect(self.on_combo)

        self.player_group_box = QGroupBox("Player Settings")

        form = QFormLayout(self.player_group_box)

        form.addRow("Starting X: ", self.x_position_dropdown)
        form.addRow("Starting Y: ", self.y_position_dropdown)
        form.addRow("Action: ", self.action_dropdown)

        main_layout.addWidget(self.player_group_box)

        # graphic settings

        self.object_palette_spinner = Spinner(self, maximum=7)
        self.object_palette_spinner.valueChanged.connect(self.on_spin)

        self.enemy_palette_spinner = Spinner(self, maximum=3)
        self.enemy_palette_spinner.valueChanged.connect(self.on_spin)

        self.graphic_set_dropdown = QComboBox()
        self.graphic_set_dropdown.addItems(GRAPHIC_SETS)
        self.graphic_set_dropdown.activated.connect(self.on_combo)

        self.graphic_group_box = QGroupBox("Graphic Settings")

        form = QFormLayout(self.graphic_group_box)

        form.addRow("Object Palette: ", self.object_palette_spinner)
        form.addRow("Enemy Palette: ", self.enemy_palette_spinner)
        form.addRow("Graphic Set: ", self.graphic_set_dropdown)

        main_layout.addWidget(self.graphic_group_box)

        # next area settings

        self.level_pointer_spinner = Spinner(self, maximum=SPINNER_MAX_VALUE)
        self.enemy_pointer_spinner = Spinner(self, maximum=SPINNER_MAX_VALUE)

        self.next_area_object_set_dropdown = QComboBox()
        self.next_area_object_set_dropdown.addItems(OBJECT_SET_ITEMS)
        self.next_area_object_set_dropdown.activated.connect(self.on_combo)

        self.next_area_group_box = QGroupBox("Next Area")

        form = QFormLayout(self.next_area_group_box)

        form.addRow("Address of Objects: ", self.level_pointer_spinner)
        form.addRow("Address of Enemies: ", self.enemy_pointer_spinner)
        form.addRow("Object Set: ", self.next_area_object_set_dropdown)

        main_layout.addWidget(self.next_area_group_box)

        self.update()

    def update(self):
        length_index = LEVEL_LENGTHS.index(self.level.length)

        self.length_dropdown.setCurrentIndex(length_index)
        self.music_dropdown.setCurrentIndex(self.level.music_index)
        self.time_dropdown.setCurrentIndex(self.level.time_index)
        self.v_scroll_direction_dropdown.setCurrentIndex(self.level.scroll_type)
        self.level_is_vertical_cb.setChecked(self.level.is_vertical)
        self.pipe_ends_level_cb.setChecked(self.level.pipe_ends_level)

        self.x_position_dropdown.setCurrentIndex(self.level.start_x_index)
        self.y_position_dropdown.setCurrentIndex(self.level.start_y_index)
        self.action_dropdown.setCurrentIndex(self.level.start_action)

        self.object_palette_spinner.setValue(self.level.object_palette_index)
        self.enemy_palette_spinner.setValue(self.level.enemy_palette_index)
        self.graphic_set_dropdown.setCurrentIndex(self.level.graphic_set)

        self.level_pointer_spinner.setValue(self.level.next_area_objects)
        self.enemy_pointer_spinner.setValue(self.level.next_area_enemies)
        self.next_area_object_set_dropdown.setCurrentIndex(self.level.next_area_object_set)

    def on_spin(self, _):
        if self.level is None:
            return

        spinner = self.sender()

        if spinner == self.object_palette_spinner:
            new_index = self.object_palette_spinner.value()
            self.level.object_palette_index = new_index

        elif spinner == self.enemy_palette_spinner:
            new_index = self.enemy_palette_spinner.value()
            self.level.enemy_palette_index = new_index

        elif spinner == self.level_pointer_spinner:
            new_offset = self.level_pointer_spinner.value()
            self.level.next_area_objects = new_offset

        elif spinner == self.enemy_pointer_spinner:
            new_offset = self.enemy_pointer_spinner.value()
            self.level.next_area_enemies = new_offset

        self.header_change.emit()

    def on_combo(self, _):
        dropdown = self.sender()

        if dropdown == self.length_dropdown:
            new_length = LEVEL_LENGTHS[self.length_dropdown.currentIndex()]
            self.level.length = new_length

        elif dropdown == self.music_dropdown:
            new_music = self.music_dropdown.currentIndex()
            self.level.music_index = new_music

        elif dropdown == self.time_dropdown:
            new_time = self.time_dropdown.currentIndex()
            self.level.time_index = new_time

        elif dropdown == self.v_scroll_direction_dropdown:
            new_scroll = self.v_scroll_direction_dropdown.currentIndex()
            self.level.scroll_type = new_scroll

        elif dropdown == self.x_position_dropdown:
            new_x = self.x_position_dropdown.currentIndex()
            self.level.start_x_index = new_x

        elif dropdown == self.y_position_dropdown:
            new_y = self.y_position_dropdown.currentIndex()
            self.level.start_y_index = new_y

        elif dropdown == self.action_dropdown:
            new_action = self.action_dropdown.currentIndex()
            self.level.start_action = new_action

        elif dropdown == self.graphic_set_dropdown:
            new_gfx_set = self.graphic_set_dropdown.currentIndex()
            self.level.graphic_set = new_gfx_set

        elif dropdown == self.next_area_object_set_dropdown:
            new_object_set = self.next_area_object_set_dropdown.currentIndex()
            self.level.next_area_object_set = new_object_set

        self.header_change.emit()

    def on_check_box(self, _):
        checkbox = self.sender()

        if checkbox == self.pipe_ends_level_cb:
            self.level.pipe_ends_level = self.pipe_ends_level_cb.isChecked()
        elif checkbox == self.level_is_vertical_cb:
            self.level.is_vertical = self.level_is_vertical_cb.isChecked()

        self.header_change.emit()
