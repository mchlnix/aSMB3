from enum import StrEnum

from PySide6.QtCore import QSettings


class TooltipType(StrEnum):
    DEFAULT = "default"
    REFERENCES = "references"


class SettingKeys(StrEnum):
    APP_REPARSE_DELAY_MS = "app_reparse_delay_ms"
    APP_REMEMBER_OPEN_FILES = "app_remember_open_files"  # currently unused
    APP_SAVE_AUTOMATICALLY = "app_save_automatically"  # currently unused
    APP_START_MAXIMIZED = "app_start_maximized"

    EDITOR_CODE_FONT_BOLD = "editor_code_font_bold"
    EDITOR_CODE_FONT_SIZE = "editor_code_font_size"
    EDITOR_REFERENCE_FONT_SIZE = "editor_reference_font_size"
    EDITOR_SEARCH_FONT_SIZE = "editor_search_font_size"
    EDITOR_TOOLTIP_TYPE = "editor_tooltip_type"  # currently unused
    EDITOR_TOOLTIP_MAX_RESULTS = "editor_tooltip_max_results"


_DEFAULT_VALUES: dict[SettingKeys, str | int | bool] = {
    SettingKeys.APP_REPARSE_DELAY_MS: 1000,
    SettingKeys.APP_REMEMBER_OPEN_FILES: False,
    SettingKeys.APP_SAVE_AUTOMATICALLY: False,
    SettingKeys.APP_START_MAXIMIZED: False,
    #
    SettingKeys.EDITOR_CODE_FONT_BOLD: True,
    SettingKeys.EDITOR_CODE_FONT_SIZE: 14,
    SettingKeys.EDITOR_REFERENCE_FONT_SIZE: 12,
    SettingKeys.EDITOR_SEARCH_FONT_SIZE: 12,
    SettingKeys.EDITOR_TOOLTIP_TYPE: TooltipType.REFERENCES,
    SettingKeys.EDITOR_TOOLTIP_MAX_RESULTS: 30,
}


class Settings(QSettings):
    def __init__(self):
        super(Settings, self).__init__("mchlnix", "aSMB3")

    def value(self, key: SettingKeys, default_value=None, type_=None):
        if key in _DEFAULT_VALUES and type_ is None:
            type_ = type(_DEFAULT_VALUES[key])

        returned_value = super(Settings, self).value(key, default_value)

        if returned_value is None:
            return returned_value
        elif type_ is bool and isinstance(returned_value, str):
            # boolean values loaded from disk are returned as strings for some reason
            return returned_value.lower() == "true"
        elif type_ is None:
            return returned_value
        else:
            return type_(returned_value)


def init_settings():
    settings = Settings()

    for key in SettingKeys:
        if settings.contains(key):
            continue

        settings.setValue(key, _DEFAULT_VALUES[key])
