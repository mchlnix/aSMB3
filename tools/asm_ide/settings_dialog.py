from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QGroupBox,
    QSpinBox,
    QVBoxLayout,
)

from tools.asm_ide.settings import SettingKeys, Settings
from tools.asm_ide.util import label_and_widget


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)

        settings = Settings()

        QVBoxLayout(self)

        self._app_group = QGroupBox("Application", self)
        self._app_group.setLayout(QVBoxLayout())

        self._app_remember_open_files_cb = QCheckBox("Remember open files on startup")
        self._app_remember_open_files_cb.setChecked(settings.value(SettingKeys.APP_REMEMBER_OPEN_FILES))
        self._app_remember_open_files_cb.setDisabled(True)
        self._app_remember_open_files_cb.setToolTip("Not implemented yet.")

        self._app_auto_save_cb = QCheckBox("Auto-save documents after every change")
        self._app_auto_save_cb.setChecked(settings.value(SettingKeys.APP_SAVE_AUTOMATICALLY))
        self._app_auto_save_cb.setDisabled(True)
        self._app_auto_save_cb.setToolTip("Not implemented yet.")

        self._app_start_maximized_cb = QCheckBox("Start application maximized")
        self._app_start_maximized_cb.setChecked(settings.value(SettingKeys.APP_START_MAXIMIZED))

        self._app_reparse_delay_sb = QSpinBox()
        self._app_reparse_delay_sb.setMinimum(100)
        self._app_reparse_delay_sb.setMaximum(60 * 1000)
        self._app_reparse_delay_sb.setValue(settings.value(SettingKeys.APP_REPARSE_DELAY_MS))

        self._app_group.layout().addWidget(self._app_remember_open_files_cb)
        self._app_group.layout().addWidget(self._app_auto_save_cb)
        self._app_group.layout().addWidget(self._app_start_maximized_cb)
        self._app_group.layout().addLayout(
            label_and_widget("Delay until document is reparsed, after change (ms)", self._app_reparse_delay_sb)
        )

        self.layout().addWidget(self._app_group)

        self._editor_group = QGroupBox("Editor", self)
        self._editor_group.setLayout(QVBoxLayout())

        self._editor_code_font_bold_cb = QCheckBox("Code Font is bold")
        self._editor_code_font_bold_cb.setChecked(settings.value(SettingKeys.EDITOR_CODE_FONT_BOLD))

        self._editor_code_font_size_sb = QSpinBox()
        self._editor_code_font_size_sb.setMinimum(1)
        self._editor_code_font_size_sb.setValue(settings.value(SettingKeys.EDITOR_CODE_FONT_SIZE))

        self._editor_reference_font_size_sb = QSpinBox()
        self._editor_reference_font_size_sb.setMinimum(1)
        self._editor_reference_font_size_sb.setValue(settings.value(SettingKeys.EDITOR_REFERENCE_FONT_SIZE))

        self._editor_search_font_size_sb = QSpinBox()
        self._editor_search_font_size_sb.setMinimum(1)
        self._editor_search_font_size_sb.setValue(settings.value(SettingKeys.EDITOR_SEARCH_FONT_SIZE))

        self._editor_tooltip_max_results_sb = QSpinBox()
        self._editor_tooltip_max_results_sb.setMinimum(-1)
        (self._editor_tooltip_max_results_sb.setValue(settings.value(SettingKeys.EDITOR_TOOLTIP_MAX_RESULTS)))

        self._editor_group.layout().addWidget(self._editor_code_font_bold_cb)
        self._editor_group.layout().addLayout(label_and_widget("Code Font Size", self._editor_code_font_size_sb))
        self._editor_group.layout().addLayout(
            label_and_widget("Reference Popup Font Size", self._editor_reference_font_size_sb)
        )
        self._editor_group.layout().addLayout(
            label_and_widget("Search Result Font Size", self._editor_search_font_size_sb)
        )
        self._editor_group.layout().addLayout(
            label_and_widget("Maximum number of results in ToolTip", self._editor_tooltip_max_results_sb)
        )

        self.layout().addWidget(self._editor_group)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_settings()

        return super().closeEvent(event)

    def _save_settings(self):
        settings = Settings()

        settings.setValue(SettingKeys.APP_REPARSE_DELAY_MS, self._app_reparse_delay_sb.value())
        settings.setValue(SettingKeys.APP_REMEMBER_OPEN_FILES, self._app_remember_open_files_cb.isChecked())
        settings.setValue(SettingKeys.APP_SAVE_AUTOMATICALLY, self._app_auto_save_cb.isChecked())
        settings.setValue(SettingKeys.APP_START_MAXIMIZED, self._app_start_maximized_cb.isChecked())

        settings.setValue(SettingKeys.EDITOR_CODE_FONT_BOLD, self._editor_code_font_bold_cb.isChecked())
        settings.setValue(SettingKeys.EDITOR_CODE_FONT_SIZE, self._editor_code_font_size_sb.value())
        settings.setValue(SettingKeys.EDITOR_REFERENCE_FONT_SIZE, self._editor_reference_font_size_sb.value())
        settings.setValue(SettingKeys.EDITOR_SEARCH_FONT_SIZE, self._editor_search_font_size_sb.value())
        settings.setValue(SettingKeys.EDITOR_TOOLTIP_MAX_RESULTS, self._editor_tooltip_max_results_sb.value())

        settings.sync()


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    settings_dialog = SettingsDialog()

    settings_dialog.show()

    sys.exit(app.exec())
