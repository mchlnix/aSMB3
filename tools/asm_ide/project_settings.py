import json
from enum import StrEnum
from pathlib import Path
from typing import Any


class ProjectSettingKeys(StrEnum):
    HIGHLIGHTED_LINE_NUMBERS = "highlight_line_numbers"
    LAST_POSITION_IN_FILES = "last_position_in_files"
    OPEN_FILES = "open_files"
    OPEN_TAB_INDEX = " open_tab_index"


_DEFAULT_VALUES: dict[ProjectSettingKeys, dict | list | int] = {
    ProjectSettingKeys.HIGHLIGHTED_LINE_NUMBERS: {},  # dict[rel_path_str, list[line_no]]
    ProjectSettingKeys.LAST_POSITION_IN_FILES: {},  # dict[rel_path_str, tuple[text_pos, scroll_pos]]
    ProjectSettingKeys.OPEN_FILES: [],  # list[rel_path_str]
    ProjectSettingKeys.OPEN_TAB_INDEX: -1,  # tab_index
}


class ProjectSettings:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self._save_path = root_path / "aSMB3.json"

        self._settings: dict[ProjectSettingKeys, Any] = {}

        self._init_settings()

    def _init_settings(self):
        self._settings = _DEFAULT_VALUES.copy()

        if self._save_path.is_file():
            self._settings.update(json.loads(self._save_path.read_text()))

    def set_value(self, key: ProjectSettingKeys, value):
        self._settings[key] = value

        self.sync()

    def value(self, key: ProjectSettingKeys):
        return self._settings[key]

    def sync(self):
        self._save_path.write_text(json.dumps(self._settings, indent=2))

    def clear_open_files(self):
        self.set_value(ProjectSettingKeys.OPEN_FILES, [])

    def add_open_file(self, abs_path: Path):
        currently_open_files = self.value(ProjectSettingKeys.OPEN_FILES)

        currently_open_files.append(self._to_rel_path_str(abs_path))

        self.set_value(ProjectSettingKeys.OPEN_FILES, currently_open_files)

    def save_position_in_file(self, abs_path: Path, text_position: int, scroll_position: int):
        last_position_in_files: dict[str, tuple[int, int]] = self.value(ProjectSettingKeys.LAST_POSITION_IN_FILES)

        last_position_in_files[self._to_rel_path_str(abs_path)] = text_position, scroll_position

        self.set_value(ProjectSettingKeys.LAST_POSITION_IN_FILES, last_position_in_files)

    def load_position_in_file(self, abs_path: Path) -> tuple[int, int]:
        last_position_in_files: dict[str, tuple[int, int]] = self.value(ProjectSettingKeys.LAST_POSITION_IN_FILES)

        return last_position_in_files.get(self._to_rel_path_str(abs_path), (0, 0))

    def _to_rel_path_str(self, abs_path: Path):
        return str(abs_path.relative_to(self.root_path))
