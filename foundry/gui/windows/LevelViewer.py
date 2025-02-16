import math
from dataclasses import dataclass
from random import randint, seed

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import (
    QBrush,
    QColor,
    QColorConstants,
    QMouseEvent,
    QPainter,
    QPaintEvent,
)
from PySide6.QtWidgets import (
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from foundry import get_level_thumbnail, pixmap_to_base64
from foundry.data_source.rom import ROM
from foundry.gui.windows.CustomChildWindow import CustomChildWindow
from smb3parse.constants import BASE_OFFSET, Constants
from smb3parse.data_points import WorldMapData
from smb3parse.levels import WORLD_COUNT
from smb3parse.objects.object_set import (
    ENEMY_ITEM_OBJECT_SET,
    OBJECT_SET_NAMES,
    PLAINS_OBJECT_SET,
    SPADE_BONUS_OBJECT_SET,
)
from smb3parse.util.parser import FoundLevel
from smb3parse.util.rom import PRG_BANK_SIZE


def _gen_level_name(level_address: int, level: FoundLevel) -> str:
    """
    Takes the given Level at the given address and tries to construct a meaningful level description from it.

    :param level_address: The absolute address the level data can be found at.
    :param level: A FoundLevel instance describing the level.

    :return: The constructed Level name.
    """
    world_data = WorldMapData(ROM(), level.world_number - 1)

    if world_data.big_q_block_level_address == level_address:
        return "Big Question Mark Block Level"

    if world_data.airship_level_address == level_address:
        return "Airship Level"

    if world_data.coin_ship_level_address == level_address:
        return "Coin Ship Level"

    if world_data.generic_exit_level_address == level_address:
        return "Generic Exit Level"

    if world_data.toad_warp_level_address == level_address:
        return "Toad Warp Level"

    return f"{OBJECT_SET_NAMES[level.object_set_number]} Level"


class LevelViewer(CustomChildWindow):
    def __init__(
        self,
        parent,
        addresses_by_object_set: dict[int, set[int]],
        levels_by_address: dict[int, FoundLevel],
    ):
        super(LevelViewer, self).__init__(parent, "Level Viewer")

        self.addresses_by_object_set = addresses_by_object_set
        self.levels_by_address = levels_by_address

        self._tab_widget = QTabWidget(self)

        self.setCentralWidget(self._tab_widget)

        # get prg numbers for object sets and sort them
        prg_banks_by_object_set = ROM().read(Constants.OFFSET_BY_OBJECT_SET_A000, 16)
        sorted_prg_bank_numbers = list(set(prg_banks_by_object_set[PLAINS_OBJECT_SET:SPADE_BONUS_OBJECT_SET]))
        sorted_prg_bank_numbers.sort()

        # create tab widgets with PRG numbers in their titles
        for prg_number in sorted_prg_bank_numbers:
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setWidget(LevelBlockView([]))

            self._tab_widget.addTab(scroll_area, f"PRG #{prg_number}")

        # got through all levels and assign them to their respective prg tab widget, based on their object set
        for address in sorted(levels_by_address.keys()):
            level = levels_by_address[address]
            tab_index_from_object_set = sorted_prg_bank_numbers.index(prg_banks_by_object_set[level.object_set_number])

            byte_view = self._tab_widget.widget(tab_index_from_object_set).widget()
            byte_view.levels_in_order.append((level.object_set_number, address, level.object_data_length))

        # insert tree view with all levels at the start of the tabs
        self._tab_widget.insertTab(0, self._gen_tree_view(levels_by_address), "Levels")

    @staticmethod
    def _gen_tree_view(levels_by_address: dict[int, FoundLevel]) -> QTreeWidget:
        tree_widget = QTreeWidget()

        world_tree_items = []
        level_item_by_address: dict[int, QTreeWidgetItem] = {}

        def _get_level_item(address_: int, level_: FoundLevel, parent_: QTreeWidgetItem):
            if address_ in level_item_by_address:
                return level_item_by_address[address_]

            if any(position_ not in levels_by_address for position_ in level_.level_offset_positions):
                print(f"{address_:#x}", "accessible from world map")

            print(
                hex(address_),
                level_.object_set_number,
                f"From World: {level_.found_in_world}, Jump: {level_.found_as_jump}, "
                f"World Specific: {level_.is_world_specific}",
            )

            level_item = QTreeWidgetItem()
            level_item.setText(0, _gen_level_name(address_, level_) + f" @ 0x{address_:x} / 0x{level.enemy_offset:x}")
            parent_.addChild(level_item)

            level_item_by_address[address_] = level_item

            return level_item

        # Step 1: Make world tree items
        for world_num in range(WORLD_COUNT - 1):
            world_item = QTreeWidgetItem(tree_widget)
            world_item.setText(0, f"World {world_num + 1}")

            world_tree_items.append(world_item)

        # Step 2.1: Make Top Level Tree Items
        for address, level in levels_by_address.items():
            if level.found_in_world:
                parent = world_tree_items[level.world_number - 1]
                _get_level_item(address, level, parent)

        # Step 2.2: Make Generic Level Tree Items
        for address, level in levels_by_address.items():
            if level.is_world_specific:
                parent = world_tree_items[level.world_number - 1]
                _get_level_item(address, level, parent)

        # Step 3: Make Jump Level Tree Widgets
        jump_destinations = [(address, level) for address, level in levels_by_address.items() if level.found_as_jump]

        # it is not always a given, that jumped to levels come after jumped from levels, so we might need to go through
        # them multiple times
        while jump_destinations:
            address, level = jump_destinations.pop(0)

            if not all(
                position in level_item_by_address
                for position in level.level_offset_positions
                if position in levels_by_address
            ):
                # not all levels, that jump to this one have widgets yet, so put it back at the end of the list
                jump_destinations.append((address, level))
                continue

            for position in level.level_offset_positions:
                if position in levels_by_address:
                    assert position in level_item_by_address, (
                        hex(address),
                        level,
                        levels_by_address[position],
                        hex(position),
                    )
                    _get_level_item(address, level, level_item_by_address[position])

        tree_widget.expandAll()

        return tree_widget


class ByteView(QWidget):
    def __init__(self, levels_in_order: list[tuple[int, int, int]]):
        super(ByteView, self).__init__()

        self.levels_in_order = levels_in_order
        seed(0)
        self._random_colors = [
            QColor(randint(0, 255), randint(0, 255), randint(0, 255)) for _ in range(ENEMY_ITEM_OBJECT_SET)
        ]

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self.setMouseTracking(True)

    def sizeHint(self):
        return QSize(1000, self.heightForWidth(self.parentWidget().width()))

    @property
    def first_level_start(self):
        if not self.levels_in_order:
            return PRG_BANK_SIZE

        return self.levels_in_order[0][1]

    def paintEvent(self, event: QPaintEvent):
        if not self.levels_in_order:
            return

        painter = QPainter(self)

        byte_side_length = 8

        width = self.width() // byte_side_length
        height = self.height() // byte_side_length

        level_start = level_length = 0

        # draw all level data from 0
        for object_set, level_start, level_length in self.levels_in_order:
            color = self._random_colors[object_set]
            level_start -= self.first_level_start

            for level_byte in range(level_length):
                cur_pos = level_start + level_byte
                x = (cur_pos % width) * byte_side_length
                y = (cur_pos // width) * byte_side_length

                painter.fillRect(x, y, byte_side_length, byte_side_length, color)

        # draw the rest of the memory left in the ROM bank in red
        last_drawn_index = level_start + level_length + 1
        end_of_bank = PRG_BANK_SIZE - ((self.first_level_start - BASE_OFFSET) % PRG_BANK_SIZE)

        print(f"Drawing rest of the bank from {last_drawn_index} to {end_of_bank}")

        for level_byte in range(end_of_bank - last_drawn_index):
            cur_pos = last_drawn_index + level_byte
            x = (cur_pos % width) * byte_side_length
            y = (cur_pos // width) * byte_side_length

            painter.fillRect(x, y, byte_side_length, byte_side_length, QColorConstants.Red)

        # draw the grid over everything
        painter.setPen(QColorConstants.Black)

        for x in range(1, width):
            x *= byte_side_length

            painter.drawLine(x, 0, x, self.height())

        for y in range(1, height):
            y *= byte_side_length

            painter.drawLine(0, y, self.width(), y)


@dataclass
class _Block:
    color: QColor
    name: str
    size: int
    level: tuple[int, int, int] | None = None


class LevelBlockView(ByteView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.block_height = 100  # px
        self.block_width = 170  # px

    def heightForWidth(self, width):
        if not self.levels_in_order:
            return 600

        block_count = len(self._parse_levels_for_blocks())

        blocks_per_line = max(1, width // self.block_width)

        lines = math.ceil(block_count / blocks_per_line)

        return lines * self.block_height

    def _parse_levels_for_blocks(self):
        potential_blocks: list[_Block] = []

        current_pos = self.first_level_start

        prg_start = (self.first_level_start // PRG_BANK_SIZE) * PRG_BANK_SIZE

        if self.first_level_start != prg_start:
            potential_blocks.append(
                _Block(QColorConstants.Gray, f"0x{prg_start:x}: Code/Unknown", current_pos % PRG_BANK_SIZE)
            )

        for object_set, abs_level_start, level_length in self.levels_in_order:
            if current_pos != abs_level_start:
                potential_blocks.append(
                    _Block(QColorConstants.Red, f"0x{current_pos:x}: Unused Space", abs_level_start - current_pos)
                )
                current_pos = abs_level_start

            potential_blocks.append(
                _Block(
                    self._random_colors[object_set],
                    f"0x{abs_level_start:x}: {OBJECT_SET_NAMES[object_set]}",
                    level_length,
                    (object_set, abs_level_start, level_length),
                )
            )
            current_pos += level_length + 1

        if current_pos % PRG_BANK_SIZE != 0:
            rest = PRG_BANK_SIZE - current_pos % PRG_BANK_SIZE

            potential_blocks.append(_Block(QColorConstants.Red, "Unused Space", rest))

        return potential_blocks

    def _starting_point_by_index(self, index: int):
        view_width = self.width() // self.block_width * self.block_width

        if view_width < self.block_width:
            x = 0
            y = index

        else:
            blocks_per_line = view_width // self.block_width
            assert blocks_per_line >= 1

            x = index % blocks_per_line
            y = index // blocks_per_line

        return QPoint(x * self.block_width, y * self.block_height)

    def _get_block_at(self, x, y) -> _Block | None:
        blocks_per_line = max(1, self.width() // self.block_width)

        if blocks_per_line * self.block_width < x:
            return None

        blocks = self._parse_levels_for_blocks()
        lines = math.ceil(len(blocks) / blocks_per_line)

        if lines * self.block_height < y:
            return None

        x_offset = x // self.block_width
        y_offset = y // self.block_height

        index = y_offset * blocks_per_line + x_offset

        if index >= len(blocks):
            return None

        return blocks[index]

    def mouseMoveEvent(self, event: QMouseEvent):
        self._set_thumbnail(event.x(), event.y())

        super().mouseMoveEvent(event)

    def _set_thumbnail(self, x, y):
        block = self._get_block_at(x, y)

        if block is None or block.level is None:
            self.setToolTip(None)
            return

        image_data = get_level_thumbnail(
            block.level[0],
            block.level[1],
            0x0,
        )

        self.setToolTip(
            f"<b>{block.name}</b><br/>"
            f"<u>Type:</u> {OBJECT_SET_NAMES[block.level[0]]} "
            f"<u>Objects:</u> {block.level[1]:#x} "
            f"<img src='data:image/png;base64,{pixmap_to_base64(image_data)}'>"
        )

    def _paint_block(self, painter: QPainter, pos: QPoint, block: _Block):
        rect = QRect(pos, QSize(self.block_width, self.block_height))

        painter.fillRect(rect, QBrush(block.color))

        painter.setPen(QColorConstants.Black)
        painter.drawRect(rect)

        name_pos = pos + QPoint(5, self.block_height // 3)
        size_pos = pos + QPoint(5, 2 * self.block_height // 3)

        painter.drawText(name_pos, block.name)
        painter.drawText(size_pos, f"Size: {block.size} Bytes ({round(100 / PRG_BANK_SIZE * block.size, 1)} %)")

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)

        for index, block in enumerate(self._parse_levels_for_blocks()):
            self._paint_block(p, self._starting_point_by_index(index), block)
