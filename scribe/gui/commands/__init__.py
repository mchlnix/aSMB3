from PySide6.QtGui import QUndoCommand

from foundry.data_source.rom import ROM
from foundry.game.gfx.drawable.Block import get_worldmap_tile
from foundry.game.gfx.objects import LevelPointer, Lock
from foundry.game.gfx.objects.world_map.map_object import MapObject
from foundry.game.level.WorldMap import WorldMap
from smb3parse.constants import (
    MAPITEM_NAMES,
    MAPOBJ_NAMES,
    MUSIC_THEMES,
    SPRITE_COUNT,
    TILE_NAMES,
)
from smb3parse.data_points import LevelPointerData, Position, SpriteData, WorldMapData
from smb3parse.levels import FIRST_VALID_ROW, NO_MAP_SCROLLING, WORLD_MAP_BLANK_TILE_ID
from smb3parse.objects.object_set import OBJECT_SET_NAMES


class DirtyAdditionalDataMixin(object):
    def __init__(self, *args, **kwargs):
        self._dirty_before = ROM.additional_data.needs_refresh

        super().__init__(*args, **kwargs)

    def undo(self):
        ROM.additional_data.needs_refresh = self._dirty_before

        super().undo()  # type: ignore

    def redo(self):
        ROM.additional_data.needs_refresh = True

        super().redo()  # type: ignore


class MoveTile(QUndoCommand):
    def __init__(
        self,
        world: WorldMap,
        start: Position,
        tile_after: int,
        end: Position,
        parent=None,
    ):
        super(MoveTile, self).__init__(parent)

        self.world = world

        self.start = start
        self.tile_after = tile_after

        self.end = end

        if self.world.point_in(*end.xy):
            self.tile_before = self.world.objects[self.end.tile_data_index].type
        else:
            self.tile_before = WORLD_MAP_BLANK_TILE_ID

        self.setText(f"Move Tile '{TILE_NAMES[tile_after]}'")

    def undo(self):
        if 0 <= self.start.tile_data_index < len(self.world.objects):
            source_obj = self.world.objects[self.start.tile_data_index]
            source_obj.change_type(self.tile_after)
            source_obj.selected = True

        if 0 <= self.end.tile_data_index < len(self.world.objects):
            target_obj = self.world.objects[self.end.tile_data_index]
            target_obj.change_type(self.tile_before)
            target_obj.selected = False

    def redo(self):
        if 0 <= self.start.tile_data_index < len(self.world.objects):
            source_obj = self.world.objects[self.start.tile_data_index]
            source_obj.change_type(WORLD_MAP_BLANK_TILE_ID)
            source_obj.selected = False

        if 0 <= self.end.tile_data_index < len(self.world.objects):
            target_obj = self.world.objects[self.end.tile_data_index]
            target_obj.change_type(self.tile_after)
            target_obj.selected = True


class MoveMapObject(DirtyAdditionalDataMixin, QUndoCommand):
    def __init__(
        self,
        world: WorldMap,
        map_object: MapObject,
        end: Position,
        start: Position | None = None,
        parent=None,
    ):
        super(MoveMapObject, self).__init__(parent)

        self.world = world

        self.map_object = map_object

        if start is None:
            self.start: tuple[int, int] = map_object.get_position()
        else:
            self.start = start.xy

        self.end = end.xy

        self.setText(f"Move {self.map_object.name}")

    def undo(self):
        self._move_map_object(self.start)

        super().undo()

    def redo(self):
        self._move_map_object(self.end)

        super().redo()

    def _move_map_object(self, new_pos: tuple[int, int]):
        self.map_object.set_position(*new_pos)

        if isinstance(self.map_object, Lock):
            for lock in self.world.locks_and_bridges:
                if lock.data.index == self.map_object.data.index:
                    lock.set_position(*new_pos)

        self.world.data_changed.emit()


class PutTile(MoveTile):
    """Implemented by doing an illegal move from outside the Map. Should probably be the other way around."""

    def __init__(self, world: WorldMap, pos: Position, tile_index: int, parent=None):
        super(PutTile, self).__init__(
            world,
            start=Position.from_xy(-1, -1),
            tile_after=tile_index,
            end=pos,
            parent=parent,
        )

    def redo(self):
        super(PutTile, self).redo()

        for obj in self.world.objects:
            obj.selected = False


class WorldTickPerFrame(QUndoCommand):
    def __init__(self, world: WorldMap, new_tick_count: int):
        super(WorldTickPerFrame, self).__init__()

        self.world = world
        self.old_count = world.data.frame_tick_count
        self.new_count = new_tick_count

        if self.new_count == 0:
            self.setText("Deactivate Map Tile Animation")
        else:
            self.setText(f"Set Ticks per Tile Animation Frame to {self.new_count}")

    def undo(self):
        self.world.data.frame_tick_count = self.old_count

        self.world.palette_changed.emit()

    def redo(self):
        self.world.data.frame_tick_count = self.new_count

        self.world.palette_changed.emit()


class WorldPaletteIndex(QUndoCommand):
    def __init__(self, world: WorldMap, new_index: int):
        super(WorldPaletteIndex, self).__init__()

        self.world = world
        self.old_index = world.data.palette_index
        self.new_index = new_index

        self.setText(f"Setting Palette Index to {new_index:#x}")

    def undo(self):
        self.world.data.palette_index = self.old_index

        self.world.palette_changed.emit()

    def redo(self):
        self.world.data.palette_index = self.new_index

        self.world.palette_changed.emit()


class WorldMusicIndex(QUndoCommand):
    def __init__(self, world: WorldMap, new_index: int):
        super(WorldMusicIndex, self).__init__()

        self.world = world
        self.old_index = world.data.music_index
        self.new_index = new_index

        self.setText(f"Setting Music Theme to '{MUSIC_THEMES[new_index]}' ({new_index:#X})")

    def undo(self):
        self.world.data.music_index = self.old_index
        self.world.data.music_arrival_index = self.old_index

    def redo(self):
        self.world.data.music_index = self.new_index
        self.world.data.music_arrival_index = self.new_index


class WorldBottomTile(QUndoCommand):
    def __init__(self, world: WorldMap, new_index: int):
        super(WorldBottomTile, self).__init__()

        self.world = world
        self.old_index = world.data.bottom_border_tile
        self.new_index = new_index

        self.setText(f"Setting Bottom Tile to {new_index:#x}")

    def undo(self):
        self.world.data.bottom_border_tile = self.old_index

    def redo(self):
        self.world.data.bottom_border_tile = self.new_index


class SetLevelAddress(DirtyAdditionalDataMixin, QUndoCommand):
    def __init__(self, data: LevelPointerData, new_address: int, parent=None):
        super(SetLevelAddress, self).__init__(parent)

        self.data = data

        self.old_address = data.level_address
        self.new_address = new_address

        self.setText(f"Set LP #{self.data.index + 1} Level Address to {new_address:#x}")

    def undo(self):
        self.data.level_address = self.old_address

        super().undo()

    def redo(self):
        self.data.level_address = self.new_address

        super().redo()


class SetEnemyAddress(DirtyAdditionalDataMixin, QUndoCommand):
    def __init__(self, data: LevelPointerData, new_address: int, parent=None):
        super(SetEnemyAddress, self).__init__(parent)

        self.data = data

        self.old_address = data.enemy_address
        self.new_address = new_address

        self.setText(f"Set LP #{self.data.index + 1} Enemy Address to {new_address:#x}")

    def undo(self):
        self.data.enemy_address = self.old_address

        super().undo()

    def redo(self):
        self.data.enemy_address = self.new_address

        super().redo()


class SetObjectSet(DirtyAdditionalDataMixin, QUndoCommand):
    def __init__(self, data: LevelPointerData, object_set_number: int, parent=None):
        super(SetObjectSet, self).__init__(parent)

        self.data = data

        self.old_object_set = data.object_set
        self.new_object_set = object_set_number

        self.setText(f"Set LP #{self.data.index + 1} Object Set to {OBJECT_SET_NAMES[object_set_number]}")

    def undo(self):
        self.data.object_set = self.old_object_set

        super().undo()

    def redo(self):
        self.data.object_set = self.new_object_set

        super().redo()


class SetSpriteType(QUndoCommand):
    def __init__(self, data: SpriteData, new_type: int, parent=None):
        super(SetSpriteType, self).__init__(parent)

        self.data = data

        self.old_type = self.data.type
        self.new_type = new_type

        self.setText(f"Set Sprite #{self.data.index  +1} Type to {MAPOBJ_NAMES[new_type]}")

    def undo(self):
        self.data.type = self.old_type

    def redo(self):
        self.data.type = self.new_type


class SetSpriteItem(QUndoCommand):
    def __init__(self, data: SpriteData, new_item: int, parent=None):
        super(SetSpriteItem, self).__init__(parent)

        self.data = data

        self.old_item = self.data.item
        self.new_item = new_item

        self.setText(f"Set Sprite #{self.data.index + 1} Item to {MAPITEM_NAMES[new_item]}")

    def undo(self):
        self.data.item = self.old_item

    def redo(self):
        self.data.item = self.new_item


class SetScreenCount(DirtyAdditionalDataMixin, QUndoCommand):
    def __init__(
        self,
        world_data: WorldMapData,
        screen_count: int,
        world_map: WorldMap | None = None,
    ):
        super(SetScreenCount, self).__init__()

        self.world_data = world_data
        self.world_map = world_map

        self.old_screen_count = self.world_data.screen_count
        self.old_world_data = world_data.tile_data.copy()
        self.new_screen_count = screen_count

        self.setText(f"Set World {self.world_data.index + 1}'s screen count to {screen_count}")

    def undo(self):
        self.world_data.screen_count = self.old_screen_count
        self.world_data.tile_data = self.old_world_data

        if self.world_map is not None:
            self.world_map.reread_tiles()

        super().undo()

    def redo(self):
        self.world_data.screen_count = self.new_screen_count

        if self.world_map is not None:
            self.world_map.reread_tiles()

        super().redo()


class ChangeReplacementTile(QUndoCommand):
    def __init__(
        self,
        world: WorldMap,
        fortress_fx_index: int,
        replacement_tile_index: int,
        parent=None,
    ):
        super(ChangeReplacementTile, self).__init__(parent)

        self.world = world
        self.fx_index = fortress_fx_index
        self.replacement_tile_index = replacement_tile_index

        self.old_replacement_tile_index = -1
        self.old_tile_indexes = bytearray(4)

    def undo(self):
        for lock in self.world.locks_and_bridges:
            if lock.data.index == self.fx_index:
                lock.data.tile_indexes = self.old_tile_indexes
                lock.data.replacement_block_index = self.old_replacement_tile_index

    def redo(self):
        block = get_worldmap_tile(self.replacement_tile_index)

        for lock in self.world.locks_and_bridges:
            if lock.data.index == self.fx_index:
                self.old_tile_indexes = lock.data.tile_indexes
                self.old_replacement_tile_index = lock.data.replacement_block_index

                lock.data.tile_indexes = bytearray(
                    [
                        block.lu_tile.tile_index,
                        block.ru_tile.tile_index,
                        block.ld_tile.tile_index,
                        block.rd_tile.tile_index,
                    ]
                )
                lock.data.replacement_block_index = self.replacement_tile_index


class ChangeLockIndex(QUndoCommand):
    def __init__(self, world: WorldMap, lock: Lock, new_index: int, parent=None):
        super(ChangeLockIndex, self).__init__(parent)

        self.world = world
        self.lock = lock

        self.old_index = lock.data.index
        self.old_replacement_tile = lock.data.replacement_block_index
        self.new_index = new_index

    def undo(self):
        self._change_lock_index(self.old_index)

    def redo(self):
        self._change_lock_index(self.new_index)

    def _change_lock_index(self, new_index: int):
        if self.old_index == self.new_index:
            return

        for lock in self.world.locks_and_bridges:
            if lock is self.lock:
                continue

            if lock.data.index == new_index:
                self.lock.data.change_index(new_index)
                self.lock.data.replacement_block_index = lock.data.replacement_block_index
                self.lock.data.set_pos(lock.data.pos)

                break

        else:
            self.lock.data.change_index(new_index)
            self.lock.data.read_values()


class SetWorldScroll(QUndoCommand):
    def __init__(self, world_data: WorldMapData, should_scroll: bool):
        super(SetWorldScroll, self).__init__()

        self.world_data = world_data
        self.old_value = world_data.map_scroll
        self.new_value = world_data.screen_count << 4 if should_scroll else NO_MAP_SCROLLING

        if should_scroll:
            self.setText("Activate Map Scroll")
        else:
            self.setText("Deactivate Map Scroll")

    def undo(self):
        self.world_data.map_scroll = self.old_value
        self.world_data.write_back()

    def redo(self):
        self.world_data.map_scroll = self.new_value
        self.world_data.write_back()


class SetWorldIndex(DirtyAdditionalDataMixin, QUndoCommand):
    def __init__(
        self,
        world_data: WorldMapData,
        sprites: list[SpriteData],
        new_index: int,
        parent=None,
    ):
        super(SetWorldIndex, self).__init__(parent)

        self.world_data = world_data
        self.sprites = sprites

        self.old_index = world_data.index
        self.new_index = new_index

        self.setText(f"Set World {self.old_index + 1}'s index to {new_index + 1}")

    def undo(self):
        self._change_world_index(self.old_index)

        super().undo()

    def redo(self):
        self._change_world_index(self.new_index)

        super().redo()

    def _change_world_index(self, new_index: int):
        self.world_data.change_index(new_index)

        for sprite in self.sprites:
            sprite.calculate_addresses()


class SetStructureBlockAddress(DirtyAdditionalDataMixin, QUndoCommand):
    def __init__(self, world_data: WorldMapData, new_address: int):
        super(SetStructureBlockAddress, self).__init__()

        self.world_data = world_data
        self.old_address = world_data.structure_block_address
        self.new_address = new_address

    def undo(self):
        self.world_data.structure_block_address = self.old_address

        super().undo()

    def redo(self):
        self.world_data.structure_block_address = self.new_address

        super().redo()


class SetTileDataOffset(DirtyAdditionalDataMixin, QUndoCommand):
    def __init__(self, world_data: WorldMapData, new_offset: int):
        super(SetTileDataOffset, self).__init__()

        self.world_data = world_data
        self.old_offset = world_data.tile_data_offset
        self.new_offset = new_offset

    def undo(self):
        self.world_data.tile_data_offset = self.old_offset

        super().undo()

    def redo(self):
        self.world_data.tile_data_offset = self.new_offset

        super().redo()


class ChangeSpriteIndex(QUndoCommand):
    def __init__(self, world: WorldMap, old_index: int, new_index: int, parent=None):
        super(ChangeSpriteIndex, self).__init__(parent)
        self.world = world

        self.old_index = old_index
        self.new_index = new_index

        self.setText(f"Change Sprite Index {self.old_index} -> {self.new_index}")

    def undo(self):
        self.world.move_sprites(self.new_index, self.old_index)

    def redo(self):
        self.world.move_sprites(self.old_index, self.new_index)


class ChangeLevelPointerIndex(DirtyAdditionalDataMixin, QUndoCommand):
    def __init__(self, world: WorldMap, old_index: int, new_index: int, parent=None):
        super(ChangeLevelPointerIndex, self).__init__(parent)
        self.world = world

        self.old_index = old_index
        self.new_index = new_index

        self.setText(f"Change Level Pointer Index {self.old_index} -> {self.new_index}")

    def undo(self):
        self.world.move_level_pointers(self.new_index, self.old_index)

        super().undo()

    def redo(self):
        self.world.move_level_pointers(self.old_index, self.new_index)

        super().redo()


class AddLevelPointer(DirtyAdditionalDataMixin, QUndoCommand):
    def __init__(self, world_data: WorldMapData, world: WorldMap | None = None):
        super(AddLevelPointer, self).__init__()

        self.world = world
        self.world_data = world_data

        self.level_pointer_data = LevelPointerData(self.world_data, self.world_data.level_count)
        self.level_pointer_data.pos = Position(0, FIRST_VALID_ROW, 0)
        self.level_pointer_data.object_set = 1
        self.level_pointer_data.level_address = 0x0
        self.level_pointer_data.enemy_address = 0x0

        self.level_pointer = LevelPointer(self.level_pointer_data)

        self.setText("Add Level Pointer")

    def undo(self):
        self.world_data.level_count_screen_1 -= 1
        self.world_data.level_pointers.remove(self.level_pointer_data)

        if self.world is not None:
            self.world.level_pointers.remove(self.level_pointer)

        super().undo()

    def redo(self):
        self.world_data.level_count_screen_1 += 1

        self.world_data.level_pointers.append(self.level_pointer_data)

        if self.world is not None:
            self.world.level_pointers.append(self.level_pointer)

        super().redo()


class RemoveLevelPointer(DirtyAdditionalDataMixin, QUndoCommand):
    def __init__(self, world_data: WorldMapData, index=-1, world: WorldMap | None = None):
        super(RemoveLevelPointer, self).__init__()

        self.world = world
        self.world_data = world_data

        if index == -1:
            index = len(self.world_data.level_pointers) - 1

        self.index = index

        self.removed_level_pointer_data = self.world_data.level_pointers[index]

        if world is not None:
            self.removed_level_pointer = world.level_pointers[index]
        else:
            self.removed_level_pointer = None

        self.setText(f"Remove Level Pointer #{index}")

    def undo(self):
        # TODO not nice
        attr_name = f"level_count_screen_{self.removed_level_pointer_data.screen + 1}"

        lvls_on_screen = getattr(self.world_data, attr_name)

        setattr(self.world_data, attr_name, lvls_on_screen + 1)

        self.world_data.level_pointers.insert(self.index, self.removed_level_pointer_data)

        if self.world is not None:
            self.world.level_pointers.insert(self.index, self.removed_level_pointer)

        super().undo()

    def redo(self):
        # TODO not nice
        attr_name = f"level_count_screen_{self.removed_level_pointer_data.screen + 1}"

        lvls_on_screen = getattr(self.world_data, attr_name)

        assert lvls_on_screen > 0

        setattr(self.world_data, attr_name, lvls_on_screen - 1)

        self.world_data.level_pointers.pop(self.index)

        if self.world is not None:
            self.world.level_pointers.pop(self.index)

        super().redo()


class WorldDataStandIn:
    def __init__(self, world_data: WorldMapData):
        self.level_count = self._orig_level_count = world_data.level_count
        self.screen_count = self._orig_screen_count = world_data.screen_count
        self.index = self._orig_index = world_data.index

        self.sprites = [SpriteData(world_data, index) for index in range(SPRITE_COUNT)]

        self.data = world_data

    @property
    def changed(self):
        lc_changed = self.level_count != self._orig_level_count
        sc_changed = self.screen_count != self._orig_screen_count
        ind_changed = self.index != self._orig_index

        return lc_changed or sc_changed or ind_changed


class SaveWorldsOnUndo(QUndoCommand):
    def __init__(self, worlds: list[WorldDataStandIn]):
        super(SaveWorldsOnUndo, self).__init__()

        self.worlds = worlds

    def undo(self):
        for world in self.worlds:
            world.data.write_back()

            for sprite in world.sprites:
                sprite.write_back()


class SaveWorldsOnRedo(QUndoCommand):
    def __init__(self, worlds: list[WorldDataStandIn]):
        super(SaveWorldsOnRedo, self).__init__()

        self.worlds = worlds

    def redo(self):
        for world in self.worlds:
            world.data.write_back()

            for sprite in world.sprites:
                sprite.write_back()
