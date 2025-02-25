from enum import StrEnum

from PySide6.QtCore import QSettings


class TooltipType(StrEnum):
    DEFAULT = "default"
    REFERENCES = "references"


class AppSettingKeys(StrEnum):
    APP_REPARSE_DELAY_MS = "app_reparse_delay_ms"
    APP_REMEMBER_OPEN_FILES = "app_remember_open_files"  # currently unused
    APP_SAVE_AUTOMATICALLY = "app_save_automatically"  # currently unused
    APP_START_MAXIMIZED = "app_start_maximized"

    ASSEMBLY_COMMAND = "assembly_command"
    ASSEMBLY_NOTIFY_SUCCESS = "assembly_notify_success"

    EDITOR_CODE_FONT_BOLD = "editor_code_font_bold"
    EDITOR_CODE_FONT_SIZE = "editor_code_font_size"
    EDITOR_REFERENCE_FONT_SIZE = "editor_reference_font_size"
    EDITOR_SEARCH_FONT_SIZE = "editor_search_font_size"
    EDITOR_TOOLTIP_TYPE = "editor_tooltip_type"  # currently unused
    EDITOR_TOOLTIP_MAX_RESULTS = "editor_tooltip_max_results"


_DEFAULT_VALUES: dict[AppSettingKeys, str | int | bool] = {
    AppSettingKeys.APP_REPARSE_DELAY_MS: 1000,
    AppSettingKeys.APP_REMEMBER_OPEN_FILES: False,
    AppSettingKeys.APP_SAVE_AUTOMATICALLY: False,
    AppSettingKeys.APP_START_MAXIMIZED: False,
    #
    AppSettingKeys.ASSEMBLY_COMMAND: "nesasm.exe smb3.asm",
    AppSettingKeys.ASSEMBLY_NOTIFY_SUCCESS: True,
    #
    AppSettingKeys.EDITOR_CODE_FONT_BOLD: True,
    AppSettingKeys.EDITOR_CODE_FONT_SIZE: 14,
    AppSettingKeys.EDITOR_REFERENCE_FONT_SIZE: 12,
    AppSettingKeys.EDITOR_SEARCH_FONT_SIZE: 12,
    AppSettingKeys.EDITOR_TOOLTIP_TYPE: TooltipType.REFERENCES,
    AppSettingKeys.EDITOR_TOOLTIP_MAX_RESULTS: 30,
}


class AppSettings(QSettings):
    def __init__(self):
        super(AppSettings, self).__init__("mchlnix", "aSMB3")

    def value(self, key: AppSettingKeys, default_value=None, type_=None):
        if key in _DEFAULT_VALUES and type_ is None:
            type_ = type(_DEFAULT_VALUES[key])

        returned_value = super(AppSettings, self).value(key, default_value)

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
    settings = AppSettings()

    for key in AppSettingKeys:

        # fixes wrong default command in version <0.4
        if key == AppSettingKeys.ASSEMBLY_COMMAND:
            command = settings.value(AppSettingKeys.ASSEMBLY_COMMAND)
            command = command.replace("%f", "smb3.asm")

            settings.setValue(key, command)

        if settings.contains(key):
            continue

        settings.setValue(key, _DEFAULT_VALUES[key])
