from operator import itemgetter
from typing import List, Optional, Tuple

from PySide6.QtCore import QPoint
from PySide6.QtGui import QUndoCommand

from foundry.game.ObjectSet import OBJECT_SET_NAMES
from foundry.game.gfx.objects import EnemyItem, LevelObject
from foundry.game.gfx.objects.in_level.in_level_object import InLevelObject
from foundry.game.level.Level import Level
from foundry.gui.LevelView import LevelView


class SetLevelAddressData(QUndoCommand):
    def __init__(self, level: Level, header_offset: int, enemy_offset: int):
        super(SetLevelAddressData, self).__init__()

        self.level = level

        self.old_header_offset = self.level.header_offset
        self.old_enemy_offset = self.level.enemy_offset

        self.new_header_offset = header_offset
        self.new_enemy_offset = enemy_offset

        self.setText(f"Save Level to {hex(self.new_header_offset)} and {hex(self.new_enemy_offset)}")

    def undo(self):
        self.level.set_addresses(self.old_header_offset, self.old_enemy_offset)

    def redo(self):
        self.level.set_addresses(self.new_header_offset, self.new_enemy_offset)


class AttachLevelToRom(SetLevelAddressData):
    def __init__(self, level: Level, header_offset: int, enemy_offset: int):
        super(AttachLevelToRom, self).__init__(level, header_offset, enemy_offset)

        self.setText(f"Attach Level to {hex(self.new_header_offset)} and {hex(self.new_enemy_offset)}")


class DetachLevelFromRom(SetLevelAddressData):
    def __init__(self, level: Level):
        super(DetachLevelFromRom, self).__init__(level, 0x0, 0x0)

        self.setText("Detach Level from Rom")


class SetLevelAttribute(QUndoCommand):
    def __init__(self, level: Level, name: str, new_value, display_name="", display_value=""):
        super(SetLevelAttribute, self).__init__()

        self.level = level

        self.name = name
        self.old_value = getattr(level, name)
        self.new_value = new_value

        if not display_name:
            display_name = f"Level {' '.join(name.split('_')).capitalize()}"

        if not display_value:
            display_value = str(new_value)

        self.setText(f"{display_name} to {display_value}")

    def undo(self):
        setattr(self.level, self.name, self.old_value)

    def redo(self):
        setattr(self.level, self.name, self.new_value)


class SetNextAreaObjectAddress(SetLevelAttribute):
    def __init__(self, level: Level, new_address: int):
        super(SetNextAreaObjectAddress, self).__init__(level, "next_area_objects", new_address)

        self.setText(f"Object Address of Next Area to {hex(new_address)}")


class SetNextAreaEnemyAddress(SetLevelAttribute):
    def __init__(self, level: Level, new_address: int):
        super(SetNextAreaEnemyAddress, self).__init__(level, "next_area_enemies", new_address)

        self.setText(f"Enemy Address of Next Area to {hex(new_address)}")


class SetNextAreaObjectSet(SetLevelAttribute):
    def __init__(self, level: Level, new_object_set: int):
        super(SetNextAreaObjectSet, self).__init__(level, "next_area_object_set", new_object_set)

        self.setText(f"Object Set of Next Area to {OBJECT_SET_NAMES[new_object_set]}")


class ToForeground(QUndoCommand):
    def __init__(self, level: Level, objects: List[InLevelObject]):
        super(ToForeground, self).__init__()

        self.level = level
        self.objects = objects

        self.indexes_before: List[Tuple[int, InLevelObject]] = []

        for obj in objects:
            if isinstance(obj, LevelObject):
                index = self.level.objects.index(obj)

            else:
                assert isinstance(obj, EnemyItem)
                index = self.level.enemies.index(obj)

            self.indexes_before.append((index, obj))

        self.indexes_before.sort(key=itemgetter(0))

        if len(self.objects) == 1:
            self.setText(f"Bring '{objects[0].name}' to the foreground")
        else:
            self.setText(f"Bring {len(objects)} objects to the foreground")

    def undo(self):
        for index, obj in self.indexes_before:
            if isinstance(obj, LevelObject):
                self.level.objects.remove(obj)
                self.level.objects.insert(index, obj)

            else:
                assert isinstance(obj, EnemyItem)
                self.level.enemies.remove(obj)
                self.level.enemies.insert(index, obj)

        self.level.data_changed.emit()

    def redo(self):
        self.level.bring_to_foreground(self.objects)


class ToBackground(ToForeground):
    def __init__(self, level: Level, objects: List[InLevelObject]):
        super(ToBackground, self).__init__(level, objects)

        self.indexes_before.reverse()

        if len(self.objects) == 1:
            self.setText(f"Put '{objects[0].name}' in the background")
        else:
            self.setText(f"Put {len(objects)} objects in the background")

    def redo(self):
        self.level.bring_to_background(self.objects)


class AddObjectAt(QUndoCommand):
    def __init__(
        self, level_view: LevelView, pos: QPoint, domain=0, obj_type=0, length: Optional[int] = None, index=-1
    ):
        super(AddObjectAt, self).__init__()

        self.view = level_view
        self.level = level_view.level_ref.level

        self.pos = pos

        self.domain = domain
        self.obj_type = obj_type
        self.length = length

        self.index = index

    def undo(self):
        self.level.objects.pop(self.index)

        self.level.data_changed.emit()

    def redo(self):
        self.view.add_object(self.domain, self.obj_type, self.pos, self.length, self.index)

        self.index = len(self.level.objects) - 1

        level_obj = self.level.objects[-1]

        # TODO use level coordinates, possibly by using level directly, instead of level view
        self.setText(f"Add {level_obj.name} at {level_obj.x_position}, {level_obj.y_position}")


class AddEnemyAt(QUndoCommand):
    def __init__(self, level_view: LevelView, pos: QPoint, enemy_type=0, index=-1):
        super(AddEnemyAt, self).__init__()

        self.view = level_view
        self.level = level_view.level_ref.level

        self.pos = pos

        self.enemy_type = enemy_type

        self.index = index

    def undo(self):
        self.level.enemies.pop(self.index)

        self.level.data_changed.emit()

    def redo(self):
        self.view.add_enemy(self.enemy_type, self.pos, self.index)

        if self.index == -1:
            self.index = len(self.level.enemies) - 1

        enemy = self.level.enemies[self.index]

        # TODO use level coordinates, possibly by using level directly, instead of level view
        self.setText(f"Add {enemy.name} at {enemy.x_position}, {enemy.y_position}")
