from bisect import bisect_right
from typing import List, Optional, Tuple, cast

from PySide6.QtCore import QPoint, QSize
from PySide6.QtGui import QMouseEvent, QWheelEvent, Qt
from PySide6.QtWidgets import QToolTip, QWidget

from foundry import ctrl_is_pressed
from foundry.game import EXPANDS_BOTH, EXPANDS_HORIZ, EXPANDS_VERT
from foundry.game.gfx.objects import EnemyItem, LevelObject
from foundry.game.gfx.objects.in_level.in_level_object import InLevelObject
from foundry.game.level.Level import Level
from foundry.game.level.LevelRef import LevelRef
from foundry.game.level.WorldMap import WorldMap
from foundry.gui.ContextMenu import LevelContextMenu
from foundry.gui.LevelDrawer import LevelDrawer
from foundry.gui.MainView import (
    MODE_DRAG,
    MODE_FREE,
    MODE_RESIZE_DIAG,
    MODE_RESIZE_HORIZ,
    MODE_RESIZE_VERT,
    MainView,
    RESIZE_MODES,
    undoable,
)
from foundry.gui.settings import RESIZE_LEFT_CLICK, RESIZE_RIGHT_CLICK, SETTINGS


class LevelView(MainView):
    def __init__(self, parent: Optional[QWidget], level: LevelRef, context_menu: Optional[LevelContextMenu]):
        self.drawer = LevelDrawer()

        super(LevelView, self).__init__(parent, level, context_menu)

        self.draw_grid = SETTINGS["draw_grid"]
        self.draw_jumps = SETTINGS["draw_jumps"]
        self.draw_expansions = SETTINGS["draw_expansion"]
        self.draw_mario = SETTINGS["draw_mario"]
        self.transparency = SETTINGS["block_transparency"]
        self.draw_jumps_on_objects = SETTINGS["draw_jump_on_objects"]
        self.draw_items_in_blocks = SETTINGS["draw_items_in_blocks"]
        self.draw_invisible_items = SETTINGS["draw_invisible_items"]
        self.draw_autoscroll = SETTINGS["draw_autoscroll"]

        self.changed = False

        self.mouse_mode = MODE_FREE

        self.last_mouse_position = 0, 0

        self.drag_start_point = 0, 0

        self.dragging_happened = True

        self.resize_mouse_start_x = 0
        self.resize_obj_start_point = 0, 0

        self.resizing_happened = False

        self.setWhatsThis(
            "<b>Level View</b><br/>"
            "This renders the level as it would appear in game plus additional information, that can be "
            "toggled in the View menu.<br/>"
            "It supports selecting multiple objects, moving, copy/pasting and resizing them using the "
            "mouse or the usual keyboard shortcuts.<br/>"
            "There are still occasional rendering errors, or small inconsistencies. If you find them, "
            "please report the kind of object (name or values in the SpinnerPanel) and the level or "
            "object set they appear in, in the discord and @Michael or on the github page under Help."
            "<br/><br/>"
            ""
            "If all else fails, click the play button up top to see your level in game in seconds."
        )

    @property
    def draw_grid(self):
        return self.drawer.draw_grid

    @draw_grid.setter
    def draw_grid(self, value):
        self.drawer.draw_grid = value

    @property
    def draw_jumps(self):
        return self.drawer.draw_jumps

    @draw_jumps.setter
    def draw_jumps(self, value):
        self.drawer.draw_jumps = value

    @property
    def draw_mario(self):
        return self.drawer.draw_mario

    @draw_mario.setter
    def draw_mario(self, value):
        self.drawer.draw_mario = value

    @property
    def draw_expansions(self):
        return self.drawer.draw_expansions

    @draw_expansions.setter
    def draw_expansions(self, value):
        self.drawer.draw_expansions = value

    @property
    def draw_jumps_on_objects(self):
        return self.drawer.draw_jumps_on_objects

    @draw_jumps_on_objects.setter
    def draw_jumps_on_objects(self, value):
        self.drawer.draw_jumps_on_objects = value

    @property
    def draw_items_in_blocks(self):
        return self.drawer.draw_items_in_blocks

    @draw_items_in_blocks.setter
    def draw_items_in_blocks(self, value):
        self.drawer.draw_items_in_blocks = value

    @property
    def draw_invisible_items(self):
        return self.drawer.draw_invisible_items

    @draw_invisible_items.setter
    def draw_invisible_items(self, value):
        self.drawer.draw_invisible_items = value

    @property
    def draw_autoscroll(self):
        return self.drawer.draw_autoscroll

    @draw_autoscroll.setter
    def draw_autoscroll(self, value):
        self.drawer.draw_autoscroll = value

    def sizeHint(self) -> QSize:
        if self.level_ref.level is None:
            return super(LevelView, self).sizeHint()

        w, h = self.level_ref.level.size

        w *= self.block_length
        h *= self.block_length

        return QSize(w, h)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.mouse_mode == MODE_DRAG:
            self.setCursor(Qt.ClosedHandCursor)
            self._dragging(event)

        elif self.mouse_mode in RESIZE_MODES:
            previously_selected_objects = self.level_ref.selected_objects

            self._resizing(event)

            self.level_ref.selected_objects = previously_selected_objects

        elif self.selection_square.active:
            self._set_selection_end(event.pos())

        elif SETTINGS["resize_mode"] == RESIZE_LEFT_CLICK:
            self._set_cursor_for_position(event)

        object_under_cursor = self.object_at(event.pos())

        if SETTINGS["object_tooltip_enabled"] and object_under_cursor is not None:
            self.setToolTip(str(object_under_cursor))
        else:
            self.setToolTip("")
            QToolTip.hideText()

        return super(LevelView, self).mouseMoveEvent(event)

    def _set_cursor_for_position(self, event: QMouseEvent):
        level_object = self.object_at(event.pos())

        if isinstance(level_object, (EnemyItem, LevelObject)):
            is_resizable = not level_object.is_single_block

            edges = self._cursor_on_edge_of_object(level_object, event.pos())

            if is_resizable and edges:
                if edges == Qt.RightEdge and level_object.expands() & EXPANDS_HORIZ:
                    cursor = Qt.SizeHorCursor
                elif edges == Qt.BottomEdge and level_object.expands() & EXPANDS_VERT:
                    cursor = Qt.SizeVerCursor
                elif (level_object.expands() & EXPANDS_BOTH) == EXPANDS_BOTH:
                    cursor = Qt.SizeFDiagCursor
                else:
                    return

                if self.mouse_mode not in RESIZE_MODES:
                    self.setCursor(cursor)

                return

        if self.mouse_mode not in RESIZE_MODES:
            self.setCursor(Qt.ArrowCursor)

    def _cursor_on_edge_of_object(self, level_object: InLevelObject, pos: QPoint, edge_width: int = 4) -> Qt.Edges:
        right = (level_object.get_rect().left() + level_object.get_rect().width()) * self.block_length
        bottom = (level_object.get_rect().top() + level_object.get_rect().height()) * self.block_length

        on_right_edge = pos.x() in range(right - edge_width, right)
        on_bottom_edge = pos.y() in range(bottom - edge_width, bottom)

        edges = Qt.Edges()

        if on_right_edge:
            edges |= Qt.RightEdge

        if on_bottom_edge:
            edges |= Qt.BottomEdge

        return edges

    def wheelEvent(self, event: QWheelEvent):
        if SETTINGS["object_scroll_enabled"]:
            pos = event.position().toPoint()
            obj_under_cursor = self.object_at(pos)

            if obj_under_cursor is None:
                return False

            if isinstance(self.level_ref.level, WorldMap):
                return False

            # scrolling through the level could unintentionally change objects, if the cursor would wander onto them.
            # this is annoying (to me) so only change already selected objects
            if obj_under_cursor not in self.level_ref.selected_objects:
                return False

            self._change_object_on_mouse_wheel(pos, event.angleDelta().y())

            return True
        else:
            super(LevelView, self).wheelEvent(event)
            return False

    @undoable
    def _change_object_on_mouse_wheel(self, cursor_position: QPoint, y_delta: int):
        obj_under_cursor = self.object_at(cursor_position)

        if not isinstance(obj_under_cursor, InLevelObject):
            return

        if y_delta > 0:
            obj_under_cursor.increment_type()
        else:
            obj_under_cursor.decrement_type()

        obj_under_cursor.selected = True

    def _on_right_mouse_button_down(self, event: QMouseEvent):
        if self.mouse_mode == MODE_DRAG:
            return

        level_x, level_y = self._to_level_point(event.pos())

        self.last_mouse_position = level_x, level_y

        if self._select_objects_on_click(event) and SETTINGS["resize_mode"] == RESIZE_RIGHT_CLICK:
            self._try_start_resize(MODE_RESIZE_DIAG, event)

    def _try_start_resize(self, resize_mode: int, event: QMouseEvent):
        if resize_mode not in RESIZE_MODES:
            return

        level_x, level_y = self._to_level_point(event.pos())

        self.mouse_mode = resize_mode

        self.resize_mouse_start_x = level_x

        obj = self.object_at(event.pos())

        if not isinstance(obj, InLevelObject):
            return

        if obj is not None:
            self.resize_obj_start_point = obj.x_position, obj.y_position

    def _resizing(self, event: QMouseEvent):
        self.resizing_happened = True

        if isinstance(self.level_ref.level, WorldMap):
            return

        level_x, level_y = self._to_level_point(event.pos())

        dx = dy = 0

        if self.mouse_mode & MODE_RESIZE_HORIZ:
            dx = level_x - self.resize_obj_start_point[0]

        if self.mouse_mode & MODE_RESIZE_VERT:
            dy = level_y - self.resize_obj_start_point[1]

        self.last_mouse_position = level_x, level_y

        selected_objects = self.get_selected_objects()

        for obj in selected_objects:
            obj.resize_by(dx, dy)

            self.level_ref.level.changed = True

        self.update()

    def get_selected_objects(self) -> List[InLevelObject]:
        return cast(List[InLevelObject], super(LevelView, self).get_selected_objects())

    def _on_right_mouse_button_up(self, event):
        if self.resizing_happened:
            resize_end_x, _ = self._to_level_point(event.pos())

            if self.resize_mouse_start_x != resize_end_x:
                self._stop_resize(event)
        elif self.context_menu is not None:
            if self.get_selected_objects():
                menu = self.context_menu.as_object_menu()
            else:
                menu = self.context_menu.as_background_menu()

            self.context_menu.set_position(event.pos())

            menu_pos = self.mapToGlobal(event.pos())

            menu.popup(menu_pos)

        self.resizing_happened = False
        self.mouse_mode = MODE_FREE
        self.setCursor(Qt.ArrowCursor)

    def _stop_resize(self, _):
        if self.resizing_happened:
            self.level_ref.save_level_state()

        self.resizing_happened = False
        self.mouse_mode = MODE_FREE
        self.setCursor(Qt.ArrowCursor)

    def _on_left_mouse_button_down(self, event: QMouseEvent):
        # 1 if clicking on background: deselect everything, start selection square
        # 2 if clicking on background and ctrl: start selection_square
        # 3 if clicking on selected object: deselect everything and select only this object
        # 4 if clicking on selected object and ctrl: do nothing, deselect this object on release
        # 5 if clicking on unselected object: deselect everything and select only this object
        # 6 if clicking on unselected object and ctrl: select this object

        if self._select_objects_on_click(event):
            obj = self.object_at(event.pos())

            if not isinstance(obj, InLevelObject):
                return

            # enable all drag functionality
            if obj is not None:
                edge = self._cursor_on_edge_of_object(obj, event.pos())

                if SETTINGS["resize_mode"] == RESIZE_LEFT_CLICK and edge:

                    self._try_start_resize(self._resize_mode_from_edge(edge), event)
                else:
                    self.drag_start_point = obj.x_position, obj.y_position
        else:
            self._start_selection_square(event.pos())

    @staticmethod
    def _resize_mode_from_edge(edge: Qt.Edges):
        mode = 0

        if edge & Qt.RightEdge:
            mode |= MODE_RESIZE_HORIZ

        if edge & Qt.BottomEdge:
            mode |= MODE_RESIZE_VERT

        return mode

    def _dragging(self, event: QMouseEvent):
        self.dragging_happened = True

        level_x, level_y = self._to_level_point(event.pos())

        dx = level_x - self.last_mouse_position[0]
        dy = level_y - self.last_mouse_position[1]

        self.last_mouse_position = level_x, level_y

        selected_objects = self.get_selected_objects()

        for obj in selected_objects:
            obj.move_by(dx, dy)

            self.level_ref.level.changed = True

        self.update()

    def object_at(self, q_point: QPoint) -> Optional[InLevelObject]:
        return cast(Optional[InLevelObject], super(LevelView, self).object_at(q_point))

    def _on_left_mouse_button_up(self, event: QMouseEvent):
        obj = self.object_at(event.pos())

        if self.mouse_mode == MODE_DRAG and self.dragging_happened:
            if not isinstance(obj, InLevelObject):
                return

            if obj is not None:
                drag_end_point = obj.x_position, obj.y_position

                if self.drag_start_point != drag_end_point:
                    self._stop_drag()
                else:
                    self.dragging_happened = False
        elif self.selection_square.active:
            self._stop_selection_square()

        elif obj and obj.selected and not self._object_was_selected_on_last_click:
            # handle selected object on release to allow dragging

            if ctrl_is_pressed():
                # take selected object under cursor out of current selection
                selected_objects = self.get_selected_objects().copy()
                selected_objects.remove(obj)
                self.select_objects(selected_objects, replace_selection=True)
            else:
                # replace selection with only selected object
                self.select_objects([obj], replace_selection=True)

        self.mouse_mode = MODE_FREE
        self._object_was_selected_on_last_click = False
        self.setCursor(Qt.ArrowCursor)

    def _stop_drag(self):
        if self.dragging_happened:
            self.level_ref.save_level_state()

        self.dragging_happened = False

    def remove_selected_objects(self):
        for obj in self.level_ref.selected_objects:
            self.level_ref.remove_object(obj)

    def scroll_to_objects(self, objects: List[LevelObject]):
        if not objects:
            return

        min_x = min([obj.x_position for obj in objects]) * self.block_length
        min_y = min([obj.y_position for obj in objects]) * self.block_length

        self.parent().parent().ensureVisible(min_x, min_y)

    def level_safe_to_save(self) -> Tuple[bool, str, str]:
        is_safe = True
        reason = ""
        additional_info = ""

        if self.level_ref.too_many_level_objects():
            level = self._cuts_into_other_objects()

            is_safe = False
            reason = "Too many level objects."

            if level:
                additional_info = f"Would overwrite data of '{level}'."
            else:
                additional_info = (
                    "It wouldn't overwrite another level, " "but it might still overwrite other important data."
                )

        elif self.level_ref.too_many_enemies_or_items():
            level = self._cuts_into_other_enemies()

            is_safe = False
            reason = "Too many enemies or items."

            if level:
                additional_info = f"Would probably overwrite enemy/item data of '{level}'."
            else:
                additional_info = (
                    "It wouldn't overwrite enemy/item data of another level, "
                    "but it might still overwrite other important data."
                )

        return is_safe, reason, additional_info

    def _cuts_into_other_enemies(self) -> str:
        if self.level_ref is None:
            raise ValueError("Level is None")

        enemies_end = self.level_ref.enemies_end

        levels_by_enemy_offset = sorted(Level.offsets, key=lambda level: level.enemy_offset)

        level_index = bisect_right([level.enemy_offset for level in levels_by_enemy_offset], enemies_end) - 1

        found_level = levels_by_enemy_offset[level_index]

        if found_level.enemy_offset == self.level_ref.enemy_offset:
            return ""
        else:
            return f"World {found_level.game_world} - {found_level.name}"

    def _cuts_into_other_objects(self) -> str:
        if self.level_ref is None:
            raise ValueError("Level is None")

        end_of_level_objects = self.level_ref.objects_end

        level_index = (
            bisect_right(
                [level.rom_level_offset - Level.HEADER_LENGTH for level in Level.sorted_offsets], end_of_level_objects
            )
            - 1
        )

        found_level = Level.sorted_offsets[level_index]

        if found_level.rom_level_offset == self.level_ref.object_offset:
            return ""
        else:
            return f"World {found_level.game_world} - {found_level.name}"

    def add_jump(self):
        self.level_ref.add_jump()

    def from_m3l(self, data: bytearray):
        self.level_ref.from_m3l(data)

    def add_object(self, domain: int, obj_index: int, q_point: QPoint, length: int, index: int = -1):
        level_x, level_y = self._to_level_point(q_point)

        self.level_ref.add_object(domain, obj_index, level_x, level_y, length, index)

    def add_enemy(self, enemy_index: int, q_point: QPoint, index=-1):
        level_x, level_y = self._to_level_point(q_point)

        if index == -1:
            index = len(self.level_ref.level.enemies)

        self.level_ref.add_enemy(enemy_index, level_x, level_y, index)

    def replace_object(self, obj: LevelObject, domain: int, obj_index: int, length: int):
        self.remove_object(obj)

        x, y = obj.get_position()

        new_obj = self.level_ref.add_object(domain, obj_index, x, y, length, obj.index_in_level)
        new_obj.selected = obj.selected

    # @undoable
    def replace_enemy(self, old_enemy: EnemyItem, enemy_index: int):
        index_in_level = self.level_ref.index_of(old_enemy)

        self.remove_object(old_enemy)

        x, y = old_enemy.get_position()

        new_enemy = self.level_ref.add_enemy(enemy_index, x, y, index_in_level)

        new_enemy.selected = old_enemy.selected

    def remove_object(self, obj):
        self.level_ref.remove_object(obj)

    def remove_jump(self, index: int):
        del self.level_ref.jumps[index]

        self.update()

    @undoable
    def dropEvent(self, event):
        x, y = self._to_level_point(event.pos())

        level_object = self._object_from_mime_data(event.mimeData())

        if isinstance(level_object, LevelObject):
            self.level_ref.level.add_object(level_object.domain, level_object.obj_index, x, y, None)
        else:
            self.level_ref.level.add_enemy(level_object.obj_index, x, y)

        event.accept()

        self.currently_dragged_object = None

        self.level_ref.data_changed.emit()
