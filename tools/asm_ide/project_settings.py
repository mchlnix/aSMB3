import json
from enum import StrEnum
from pathlib import Path
from typing import Any


class ProjectSettingKeys(StrEnum):
    OPEN_FILES = "open_files"
    OPEN_TAB_INDEX = " open_tab_index"


_DEFAULT_VALUES: dict[ProjectSettingKeys, str | bool | int | list] = {
    ProjectSettingKeys.OPEN_FILES: [],
    ProjectSettingKeys.OPEN_TAB_INDEX: -1,
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
        self._save_path.write_text(json.dumps(self._settings))
