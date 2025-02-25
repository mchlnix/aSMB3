from pathlib import Path

from tools.asm_ide.project_settings import ProjectSettingKeys, ProjectSettings
from tools.asm_ide.tab_widget import TabWidget


class Project:
    def __init__(self, tab_widget: TabWidget):
        self._tab_widget = tab_widget
        self._tab_widget.highlighted_lines_changed.connect(self._update_highlighted_line_numbers)
        self._root_path = Path()

        self.is_open = False

    def open(self, root_path: Path):
        if self.is_open:
            raise ValueError(f"Project was already open for '{self._root_path}'")

        self.is_open = True

        self._root_path = root_path

        self._tab_widget.clear()
        self._tab_widget.root_path = root_path

        if not self._restore_previous_tabs():
            self._tab_widget.open_or_switch_file(self._root_path / "smb3.asm")

        if code_area := self._tab_widget.currentWidget():
            code_area.setFocus()

    def _restore_previous_tabs(self):
        """
        Tries reading the previously open tabs from the project settings and open them at the exact position.
        """
        project_settings = ProjectSettings(self._root_path)

        previously_open_files = project_settings.value(ProjectSettingKeys.OPEN_FILES)

        if not previously_open_files:
            return False

        for rel_path_str, text_position, scroll_position in previously_open_files:
            self._tab_widget.move_to_position(self._root_path / rel_path_str, text_position)
            code_area = self._tab_widget.currentWidget()

            if code_area is None:
                continue

            code_area.horizontalScrollBar().setValue(0)
            code_area.verticalScrollBar().setValue(scroll_position)

        self._tab_widget.setCurrentIndex(project_settings.value(ProjectSettingKeys.OPEN_TAB_INDEX))

        return True

    def _update_highlighted_line_numbers(self, abs_path: Path, line_numbers: list[int]):
        """Writes the currently highlighted line numbers of the given file to the project settings."""

        project_settings = ProjectSettings(self._root_path)
        rel_path_str = str(abs_path.relative_to(self._root_path))

        highlighted_numbers_by_file = project_settings.value(ProjectSettingKeys.HIGHLIGHTED_LINE_NUMBERS)
        highlighted_numbers_by_file[rel_path_str] = line_numbers

        project_settings.set_value(ProjectSettingKeys.HIGHLIGHTED_LINE_NUMBERS, highlighted_numbers_by_file)

    def close(self):
        if not self.is_open:
            return

        open_files: list[tuple[str, int, int]] = []
        for index, code_area in enumerate(self._tab_widget.widgets()):

            rel_path = self._tab_widget.tab_index_to_path[index].relative_to(self._root_path)
            text_position = code_area.textCursor().position()
            scroll_position = code_area.verticalScrollBar().value()

            open_files.append((str(rel_path), text_position, scroll_position))

        open_tab_index = self._tab_widget.currentIndex()

        ProjectSettings(self._root_path).set_value(ProjectSettingKeys.OPEN_FILES, open_files)
        ProjectSettings(self._root_path).set_value(ProjectSettingKeys.OPEN_TAB_INDEX, open_tab_index)

        self.is_open = False
