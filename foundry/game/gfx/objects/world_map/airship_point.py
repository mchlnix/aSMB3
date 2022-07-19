from typing import Tuple

from PySide6.QtCore import QPoint
from PySide6.QtGui import QPainter

from foundry.game.gfx.drawable import load_from_png
from foundry.game.gfx.objects.world_map.map_object import MapObject
from smb3parse.levels import WORLD_MAP_SCREEN_WIDTH

AIRSHIP_TRAVEL_POINT_1 = load_from_png(59, 2)
AIRSHIP_TRAVEL_POINT_2 = load_from_png(60, 2)
AIRSHIP_TRAVEL_POINT_3 = load_from_png(61, 2)
AIRSHIP_TRAVEL_POINT_4 = load_from_png(62, 2)
AIRSHIP_TRAVEL_POINT_5 = load_from_png(59, 3)
AIRSHIP_TRAVEL_POINT_6 = load_from_png(60, 3)

AIRSHIP_TRAVEL_POINTS = [
    AIRSHIP_TRAVEL_POINT_1,
    AIRSHIP_TRAVEL_POINT_2,
    AIRSHIP_TRAVEL_POINT_3,
    AIRSHIP_TRAVEL_POINT_4,
    AIRSHIP_TRAVEL_POINT_5,
    AIRSHIP_TRAVEL_POINT_6,
]


class AirshipTravelPoint(MapObject):
    def __init__(self, pos, index):
        super(AirshipTravelPoint, self).__init__(pos)

        self.pos = pos
        self.index = index

    def draw(self, painter: QPainter, block_length, transparent):
        x, y = self.get_position()

        x *= block_length
        y *= block_length

        painter.drawImage(QPoint(x, y), AIRSHIP_TRAVEL_POINTS[self.index].scaled(block_length, block_length))

    def set_position(self, x, y):
        self.pos.x = x % WORLD_MAP_SCREEN_WIDTH
        self.pos.y = y
        self.pos.screen = x // WORLD_MAP_SCREEN_WIDTH

    def get_position(self) -> Tuple[int, int]:
        return self.pos.xy

    def point_in(self, x, y):
        return x, y == self.pos.xy

    def change_type(self, new_type):
        pass
