from bisect import bisect_right
from typing import Optional, cast

from PySide6.QtCore import QPoint, QSize, QTimer
from PySide6.QtGui import QMouseEvent, Qt, QUndoStack, QWheelEvent
from PySide6.QtWidgets import QScrollArea, QToolTip, QWidget

from foundry import ctrl_is_pressed, make_macro
from foundry.data_source.rom import ROM
from foundry.game import EXPANDS_BOTH, EXPANDS_HORIZ, EXPANDS_VERT
from foundry.game.gfx.drawable.Block import get_tile
from foundry.game.gfx.objects import EnemyItem, LevelObject
from foundry.game.gfx.objects.in_level.in_level_object import InLevelObject
from foundry.game.level.Level import Level
from foundry.game.level.LevelRef import LevelRef
from foundry.game.level.WorldMap import WorldMap
from foundry.gui.commands import (
    AddEnemyAt,
    AddLevelObjectAt,
    AddObject,
    MoveObjects,
    RemoveObject,
    ResizeObjects,
    SetLevelAttribute,
)
from foundry.gui.ContextMenu import LevelContextMenu
from foundry.gui.settings import RESIZE_LEFT_CLICK, RESIZE_RIGHT_CLICK, Settings
from foundry.gui.visualization.level.LevelDrawer import LevelDrawer
from foundry.gui.visualization.MainView import (
    MODE_DRAG,
    MODE_FREE,
    MODE_MOVE_MARIO,
    MODE_RESIZE_DIAG,
    MODE_RESIZE_HORIZ,
    MODE_RESIZE_VERT,
    RESIZE_MODES,
    MainView,
)
from smb3parse.data_points import Position
from smb3parse.levels import HEADER_LENGTH


class LevelView(MainView):
    def __init__(
        self,
        parent: Optional[QWidget],
        level: LevelRef,
        settings: Settings,
        context_menu: Optional[LevelContextMenu],
    ):
        self.drawer = LevelDrawer()
        self.redraw_timer: Optional[QTimer] = None

        super(LevelView, self).__init__(parent, level, settings, context_menu)

        level.palette_changed.connect(self.update_anim_timer)
        level.level_changed.connect(self.update_anim_timer)
        self.update_anim_timer()

        self.mouse_mode = MODE_FREE

        self.last_mouse_position: Position = Position.from_xy(0, 0)

        self.dragging_happened = True
        self.resizing_happened = False

        self.resize_obj_start_point = Position.from_xy(0, 0)
        self.drag_start_point = Position.from_xy(0, 0)

        self._last_mario_indexes = 0, 0

        self.objects_before_resizing: list[InLevelObject] = []
        self.objects_before_moving: list[InLevelObject] = []

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
    def level(self) -> Level:
        return self.level_ref.level

    @property
    def level_header(self):
        return self.level.header

    @property
    def undo_stack(self) -> QUndoStack:
        return cast(QUndoStack, self.window().findChild(QUndoStack, "undo_stack"))

    def next_anim_step(self):
        self.drawer.anim_frame += 1
        self.drawer.anim_frame %= 4
        get_tile.cache_clear()

        self.repaint()

    def update_anim_timer(self):
        if not self.level_ref:
            return

        if self.redraw_timer is not None:
            self.redraw_timer.stop()
            self.drawer.anim_frame = 0
            get_tile.cache_clear()

        if self.settings.value("level view/block_animation"):
            self.redraw_timer = QTimer(self)
            self.redraw_timer.setInterval(120)
            self.redraw_timer.timeout.connect(self.next_anim_step)
            self.redraw_timer.start()

    def sizeHint(self) -> QSize:
        if self.level is None:
            return super(LevelView, self).sizeHint()

        w, h = self.level.size

        w *= self.block_length
        h *= self.block_length

        return QSize(w, h)

    def mouseMoveEvent(self, event: QMouseEvent):
        mouse_point = event.position().toPoint()

        if self.mouse_mode == MODE_DRAG:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self._dragging(mouse_point)

        elif self.mouse_mode in RESIZE_MODES:
            previously_selected_objects = self.level_ref.selected_objects

            self._resizing(mouse_point)

            self.level_ref.selected_objects = previously_selected_objects

        elif self.mouse_mode == MODE_MOVE_MARIO:
            self._update_mario_move(mouse_point)

        elif self.selection_square.active:
            self._set_selection_end(event)

        elif self.settings.value("editor/resize_mode") == RESIZE_LEFT_CLICK:
            self._set_cursor_for_position(mouse_point)

        object_under_cursor = self.object_at(mouse_point)

        if self.settings.value("level view/object_tooltip_enabled") and object_under_cursor is not None:
            self.setToolTip(str(object_under_cursor))
        else:
            self.setToolTip("")
            QToolTip.hideText()

        return super(LevelView, self).mouseMoveEvent(event)

    def _set_cursor_for_position(self, mouse_point: QPoint):
        level_object = self.object_at(mouse_point)

        if isinstance(level_object, (EnemyItem, LevelObject)):
            is_resizable = not level_object.is_fixed

            edges = self._cursor_on_edge_of_object(level_object, mouse_point)

            if is_resizable and edges:
                if edges == Qt.Edge.RightEdge and level_object.expands() & EXPANDS_HORIZ:
                    cursor = Qt.CursorShape.SizeHorCursor
                elif edges == Qt.Edge.BottomEdge and level_object.expands() & EXPANDS_VERT:
                    cursor = Qt.CursorShape.SizeVerCursor
                elif (level_object.expands() & EXPANDS_BOTH) == EXPANDS_BOTH:
                    cursor = Qt.CursorShape.SizeFDiagCursor
                else:
                    return

                if self.mouse_mode not in RESIZE_MODES:
                    self.setCursor(cursor)

                return

        if self.mouse_mode not in RESIZE_MODES:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def _cursor_on_edge_of_object(self, level_object: InLevelObject, pos: QPoint, edge_width: int = 4) -> Qt.Edge:
        right = (level_object.get_rect().left() + level_object.get_rect().width()) * self.block_length
        bottom = (level_object.get_rect().top() + level_object.get_rect().height()) * self.block_length

        on_right_edge = pos.x() in range(right - edge_width, right)
        on_bottom_edge = pos.y() in range(bottom - edge_width, bottom)

        edges = Qt.Edge()

        if on_right_edge:
            edges |= Qt.Edge.RightEdge

        if on_bottom_edge:
            edges |= Qt.Edge.BottomEdge

        return edges

    def wheelEvent(self, event: QWheelEvent):
        if self.settings.value("editor/object_scroll_enabled"):
            pos = event.position().toPoint()
            obj_under_cursor = self.object_at(pos)

            if obj_under_cursor is None:
                return False

            if isinstance(self.level, WorldMap):
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

    def _change_object_on_mouse_wheel(self, cursor_position: QPoint, y_delta: int):
        obj_under_cursor = self.object_at(cursor_position)

        if not isinstance(obj_under_cursor, InLevelObject):
            return

        if y_delta > 0:
            macro_name = f"Increment Type of '{obj_under_cursor.name}'"
        else:
            macro_name = f"Decrement Type of '{obj_under_cursor.name}'"

        self.undo_stack.beginMacro(macro_name)

        if isinstance(obj_under_cursor, LevelObject):
            index = self.level.objects.index(obj_under_cursor)
        else:
            index = self.level.enemies.index(cast(EnemyItem, obj_under_cursor))

        copied_object = obj_under_cursor.copy()

        self.undo_stack.push(RemoveObject(self.level, obj_under_cursor))

        if y_delta > 0:
            copied_object.increment_type()
        else:
            copied_object.decrement_type()

        copied_object.selected = True

        self.undo_stack.push(AddObject(self.level, copied_object, index))

        self.undo_stack.endMacro()

    def _on_right_mouse_button_down(self, event: QMouseEvent):
        if self.mouse_mode == MODE_DRAG:
            return

        level_pos = self.to_level_point(event.position().toPoint())

        self.last_mouse_position = level_pos

        if self._select_objects_on_click(event) and self.settings.value("editor/resize_mode") == RESIZE_RIGHT_CLICK:
            self._try_start_resize(MODE_RESIZE_DIAG, event)

    def _try_start_resize(self, resize_mode: int, event: QMouseEvent):
        if resize_mode not in RESIZE_MODES:
            return False

        if all(isinstance(obj, EnemyItem) for obj in self.get_selected_objects()):
            return False

        self.mouse_mode = resize_mode

        if (obj := self.object_at(event.position().toPoint())) is None:
            return False

        self.resize_obj_start_point = Position.from_xy(*obj.get_position())

        self.objects_before_resizing = [obj.copy() for obj in self.get_selected_objects()]

        return True

    def _resizing(self, mouse_point: QPoint):
        self.resizing_happened = True

        if isinstance(self.level, WorldMap):
            return

        level_pos = self.to_level_point(mouse_point)

        dx, dy = (level_pos - self.resize_obj_start_point).xy

        if not self.mouse_mode & MODE_RESIZE_HORIZ:
            dx = 0

        if not self.mouse_mode & MODE_RESIZE_VERT:
            dy = 0

        self.last_mouse_position = level_pos

        selected_objects = self.get_selected_objects()

        for obj in selected_objects:
            obj.resize_by(dx, dy)

        self.update()

    def get_selected_objects(self) -> list[InLevelObject]:
        return cast(list[InLevelObject], super(LevelView, self).get_selected_objects())

    def _on_right_mouse_button_up(self, event):
        if self.resizing_happened:
            self._stop_resize()

        elif self.context_menu is not None:
            menu_pos = self.mapToGlobal(event.position().toPoint())
            object_under_cursor = self.object_at(event.position())

            if self.get_selected_objects():
                menu = self.context_menu.as_object_menu(object_under_cursor)
            else:
                menu = self.context_menu.as_background_menu(object_under_cursor)

            menu.popup(menu_pos)

        self.resizing_happened = False
        self.mouse_mode = MODE_FREE
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def _stop_resize(self):
        if not self.resizing_happened:
            return

        if self.mouse_mode not in RESIZE_MODES or not self.get_selected_objects():
            return

        self.undo_stack.push(
            ResizeObjects(
                self.level,
                self.objects_before_resizing,
                self.get_selected_objects(),
            )
        )

        self.objects_before_resizing = []

        self.resizing_happened = False
        self.mouse_mode = MODE_FREE
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def _on_left_mouse_button_down(self, event: QMouseEvent):
        # 1 If clicking on Mario: show potential Mario positions, when dragging
        # 2 if clicking on background: deselect everything, start selection square
        # 3 if clicking on background and ctrl: start selection_square
        # 4 if clicking on selected object: deselect everything and select only this object
        # 5 if clicking on selected object and ctrl: do nothing, deselect this object on release
        # 6 if clicking on unselected object: deselect everything and select only this object
        # 7 if clicking on unselected object and ctrl: select this object

        if self._is_over_mario_sprite(event.position().toPoint()):
            self._start_move_mario()

        elif self._select_objects_on_click(event):
            obj = self.object_at(event.position().toPoint())

            if not isinstance(obj, InLevelObject):
                return

            # enable all drag functionality
            if obj is not None:
                edge = self._cursor_on_edge_of_object(obj, event.position().toPoint())

                if (
                    self.settings.value("editor/resize_mode") == RESIZE_LEFT_CLICK
                    and edge
                    and self._try_start_resize(self._resize_mode_from_edge(edge), event)
                ):
                    pass
                else:
                    self.drag_start_point = Position.from_xy(*obj.get_position())
                    self.objects_before_moving = [obj.copy() for obj in self.get_selected_objects()]
        else:
            self._start_selection_square(event.position().toPoint())

    def _is_over_mario_sprite(self, mouse_point: QPoint) -> bool:
        # Mario Sprite is offset by half a block, so offset the cursor as well
        mouse_point.setX(mouse_point.x() - self.block_length // 2)

        if not self.settings.value("level view/draw_mario"):
            return False

        return self.level_header.mario_position() == self.to_level_point(mouse_point).xy

    def _start_move_mario(self):
        self.mouse_mode = MODE_MOVE_MARIO

        self._last_mario_indexes = self.level_header.mario_start_indexes

        self.setCursor(Qt.CursorShape.ClosedHandCursor)

        self.drawer.should_draw_potential_marios = True

    def _update_mario_move(self, mouse_point: QPoint):
        # Mario Sprite is offset by half a block, so offset the cursor as well
        mouse_point.setX(mouse_point.x() - self.block_length // 2)

        # get current mouse position
        # convert it to level position
        current_level_position = self.to_level_point(mouse_point)

        # check if among valid mario positions
        if current_level_position.xy not in self.level_header.gen_mario_start_positions():
            return

        # if so, get the corresponding starting indexes
        x_index, y_index = self.level_header.start_indexes_from_position(*current_level_position.xy)

        # write them to the level header temporarily
        self.level_header.start_x_index = x_index
        self.level_header.start_y_index = y_index

    def _stop_mario_move(self):
        cur_mario_indexes = self.level_header.mario_start_indexes

        if self._last_mario_indexes != cur_mario_indexes:
            last_x, last_y = self._last_mario_indexes
            cur_x, cur_y = cur_mario_indexes

            self.level_header.start_x_index = last_x
            self.level_header.start_y_index = last_y

            x_command = SetLevelAttribute(self.level, "start_x_index", cur_x)
            y_command = SetLevelAttribute(self.level, "start_y_index", cur_y)

            make_macro(
                self.undo_stack,
                f"Set Mario Start Position to {self.level_header.mario_position()}",
                x_command,
                y_command,
            )
        else:
            start_x_index, start_y_index = self._last_mario_indexes

            self.level_header.start_x_index = start_x_index
            self.level_header.start_y_index = start_y_index

        self.drawer.should_draw_potential_marios = False

    @staticmethod
    def _resize_mode_from_edge(edge: Qt.Edge):
        mode = 0

        if edge & Qt.Edge.RightEdge:
            mode |= MODE_RESIZE_HORIZ

        if edge & Qt.Edge.BottomEdge:
            mode |= MODE_RESIZE_VERT

        return mode

    def _dragging(self, mouse_point: QPoint):
        self.dragging_happened = True

        level_pos = self.to_level_point(mouse_point)

        dx, dy = (level_pos - self.last_mouse_position).xy

        self.last_mouse_position = level_pos

        selected_objects = self.get_selected_objects()

        for obj in selected_objects:
            obj.move_by(dx, dy)

        self.update()

    def object_at(self, q_point: QPoint) -> Optional[InLevelObject]:
        return cast(Optional[InLevelObject], super(LevelView, self).object_at(q_point))

    def _on_left_mouse_button_up(self, event: QMouseEvent):
        obj = self.object_at(event.position().toPoint())

        if self.mouse_mode == MODE_DRAG and self.dragging_happened:
            drag_end_point = self.to_level_point(event.position().toPoint())

            if self.drag_start_point != drag_end_point:
                self._stop_drag(drag_end_point)
            else:
                self.dragging_happened = False

        elif self.resizing_happened:
            self._stop_resize()

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

        elif self.mouse_mode == MODE_MOVE_MARIO:
            self._stop_mario_move()

        self.mouse_mode = MODE_FREE
        self._object_was_selected_on_last_click = False
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def _stop_drag(self, drag_end_point: Position):
        if not self.dragging_happened:
            return

        dx, dy = (drag_end_point - self.drag_start_point).xy

        if dx == dy == 0 or not self.get_selected_objects():
            return

        self.undo_stack.push(
            MoveObjects(
                self.level,
                self.objects_before_moving,
                self.get_selected_objects(),
            )
        )

        self.objects_before_moving.clear()
        self.dragging_happened = False

    def scroll_to_objects(self, objects: list[LevelObject]):
        if not objects:
            return

        min_x = min([obj.x_position for obj in objects]) * self.block_length
        min_y = min([obj.y_position for obj in objects]) * self.block_length

        # not great, not terrible
        cast(QScrollArea, self.parent().parent()).ensureVisible(min_x, min_y)

    def level_safe_to_save(self) -> tuple[bool, str, str]:
        is_safe = True
        reason = ""
        additional_info = ""

        if not self.level_ref:
            return is_safe, reason, additional_info

        if ROM.additional_data.managed_level_positions:
            free_space_in_bank = ROM.additional_data.free_space_for_object_set(self.level.object_set_number)
            free_space_for_enemies = ROM.additional_data.free_space_for_enemies()

            additional_level_data = self.level.current_object_size() - self.level.object_size_on_disk
            additional_enemy_data = self.level.current_enemies_size() - self.level.enemy_size_on_disk

            if free_space_in_bank < additional_level_data:
                is_safe = False
                reason = "Not enough space in ROM"
                additional_info = "There is not enough space in the ROM for this level."

            elif free_space_for_enemies < additional_enemy_data:
                is_safe = False
                reason = "Not enough space in ROM"
                additional_info = "There is not enough space in the ROM for the enemies/items in this Level."

        else:
            if self.level_ref.too_many_level_objects():
                level = self._cuts_into_other_objects()

                is_safe = False
                reason = "Too many level objects."

                if level:
                    additional_info = f"Would overwrite data of original level '{level}'."
                else:
                    additional_info = (
                        "It wouldn't overwrite another level, but it might still overwrite other important data."
                    )

                additional_info += (
                    " If you deleted a bunch of objects and saved the level afterwards, this is probably a false alarm."
                )
            elif self.level_ref.too_many_enemies_or_items():
                level = self._cuts_into_other_enemies()

                is_safe = False
                reason = "Too many enemies or items."

                if level:
                    additional_info = f"Would probably overwrite enemy/item data of original level '{level}'."
                else:
                    additional_info = (
                        "It wouldn't overwrite enemy/item data of another level, "
                        "but it might still overwrite other important data."
                    )

                additional_info += (
                    " If you deleted a bunch of enemies and saved the level afterwards, this is probably a false alarm."
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
                [level.rom_level_offset - HEADER_LENGTH for level in Level.sorted_offsets],
                end_of_level_objects,
            )
            - 1
        )

        found_level = Level.sorted_offsets[level_index]

        if found_level.rom_level_offset == self.level_ref.object_offset:
            return ""
        else:
            return f"World {found_level.game_world} - {found_level.name}"

    def from_m3l(self, data: bytearray):
        self.level_ref.from_m3l(data)

    def add_object(
        self,
        domain: int,
        obj_index: int,
        q_point: QPoint,
        length: int | None,
        index: int = -1,
    ):
        level_pos = self.to_level_point(q_point)

        self.level_ref.add_object(domain, obj_index, level_pos, length, index)

    def add_enemy(self, enemy_index: int, q_point: QPoint, index=-1):
        level_pos = self.to_level_point(q_point)

        if index == -1:
            index = len(self.level.enemies)

        self.level_ref.add_enemy(enemy_index, level_pos, index)

    def dropEvent(self, event):
        level_object = self._object_from_mime_data(event.mimeData())

        if isinstance(level_object, LevelObject):
            self.undo_stack.push(
                AddLevelObjectAt(
                    self,
                    event.position().toPoint(),
                    level_object.domain,
                    level_object.obj_index,
                )
            )
        else:
            self.undo_stack.push(AddEnemyAt(self, event.position().toPoint(), level_object.obj_index))

        event.accept()

        self.currently_dragged_object = None

        self.level_ref.data_changed.emit()
