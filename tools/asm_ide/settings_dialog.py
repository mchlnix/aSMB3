from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from tools.asm_ide.application_settings import AppSettingKeys, AppSettings
from tools.asm_ide.util import label_and_widget


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)

        settings = AppSettings()

        QVBoxLayout(self)

        # Application Group

        self._app_group = QGroupBox("Application", self)

        app_group_layout = QVBoxLayout()
        self._app_group.setLayout(app_group_layout)

        self._app_remember_open_files_cb = QCheckBox("Remember open files on startup")
        self._app_remember_open_files_cb.setChecked(settings.value(AppSettingKeys.APP_REMEMBER_OPEN_FILES))
        self._app_remember_open_files_cb.setDisabled(True)
        self._app_remember_open_files_cb.setToolTip("Not implemented yet.")

        self._app_auto_save_cb = QCheckBox("Auto-save documents after every change")
        self._app_auto_save_cb.setChecked(settings.value(AppSettingKeys.APP_SAVE_AUTOMATICALLY))
        self._app_auto_save_cb.setDisabled(True)
        self._app_auto_save_cb.setToolTip("Not implemented yet.")

        self._app_start_maximized_cb = QCheckBox("Start application maximized")
        self._app_start_maximized_cb.setChecked(settings.value(AppSettingKeys.APP_START_MAXIMIZED))

        self._app_reparse_delay_sb = QSpinBox()
        self._app_reparse_delay_sb.setMinimum(100)
        self._app_reparse_delay_sb.setMaximum(60 * 1000)
        self._app_reparse_delay_sb.setValue(settings.value(AppSettingKeys.APP_REPARSE_DELAY_MS))

        app_group_layout.addWidget(self._app_remember_open_files_cb)
        app_group_layout.addWidget(self._app_auto_save_cb)
        app_group_layout.addWidget(self._app_start_maximized_cb)
        app_group_layout.addLayout(
            label_and_widget("Delay until document is reparsed, after change (ms)", self._app_reparse_delay_sb)
        )

        self.layout().addWidget(self._app_group)

        # Assembly Group

        self._assembly_group = QGroupBox("Assembly", self)

        assembly_group_layout = QVBoxLayout()
        self._assembly_group.setLayout(assembly_group_layout)

        self._assembly_notify_success_cb = QCheckBox("Notify about successful assembly")
        self._assembly_notify_success_cb.setChecked(settings.value(AppSettingKeys.ASSEMBLY_NOTIFY_SUCCESS))

        self._assembly_command_input = QLineEdit()
        self._assembly_command_input.setPlaceholderText(settings.value(AppSettingKeys.ASSEMBLY_COMMAND))
        self._assembly_command_input.setText(settings.value(AppSettingKeys.ASSEMBLY_COMMAND))

        assembly_group_layout.addWidget(self._assembly_notify_success_cb)
        assembly_group_layout.addLayout(
            label_and_widget("Assembler command", self._assembly_command_input, add_stretch=False)
        )

        self.layout().addWidget(self._assembly_group)

        # Editor Group

        self._editor_group = QGroupBox("Editor", self)

        editor_group_layout = QVBoxLayout()
        self._editor_group.setLayout(editor_group_layout)

        self._editor_code_font_bold_cb = QCheckBox("Code Font is bold")
        self._editor_code_font_bold_cb.setChecked(settings.value(AppSettingKeys.EDITOR_CODE_FONT_BOLD))

        self._editor_code_font_size_sb = QSpinBox()
        self._editor_code_font_size_sb.setMinimum(1)
        self._editor_code_font_size_sb.setValue(settings.value(AppSettingKeys.EDITOR_CODE_FONT_SIZE))

        self._editor_reference_font_size_sb = QSpinBox()
        self._editor_reference_font_size_sb.setMinimum(1)
        self._editor_reference_font_size_sb.setValue(settings.value(AppSettingKeys.EDITOR_REFERENCE_FONT_SIZE))

        self._editor_search_font_size_sb = QSpinBox()
        self._editor_search_font_size_sb.setMinimum(1)
        self._editor_search_font_size_sb.setValue(settings.value(AppSettingKeys.EDITOR_SEARCH_FONT_SIZE))

        self._editor_tooltip_max_results_sb = QSpinBox()
        self._editor_tooltip_max_results_sb.setMinimum(-1)
        (self._editor_tooltip_max_results_sb.setValue(settings.value(AppSettingKeys.EDITOR_TOOLTIP_MAX_RESULTS)))

        editor_group_layout.addWidget(self._editor_code_font_bold_cb)
        editor_group_layout.addLayout(label_and_widget("Code Font Size", self._editor_code_font_size_sb))
        editor_group_layout.addLayout(
            label_and_widget("Reference Popup Font Size", self._editor_reference_font_size_sb)
        )
        editor_group_layout.addLayout(label_and_widget("Search Result Font Size", self._editor_search_font_size_sb))
        editor_group_layout.addLayout(
            label_and_widget("Maximum number of results in ToolTip", self._editor_tooltip_max_results_sb)
        )

        self.layout().addWidget(self._editor_group)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_settings()

        return super().closeEvent(event)

    def _save_settings(self):
        settings = AppSettings()

        settings.setValue(AppSettingKeys.APP_REPARSE_DELAY_MS, self._app_reparse_delay_sb.value())
        settings.setValue(AppSettingKeys.APP_REMEMBER_OPEN_FILES, self._app_remember_open_files_cb.isChecked())
        settings.setValue(AppSettingKeys.APP_SAVE_AUTOMATICALLY, self._app_auto_save_cb.isChecked())
        settings.setValue(AppSettingKeys.APP_START_MAXIMIZED, self._app_start_maximized_cb.isChecked())

        settings.setValue(AppSettingKeys.ASSEMBLY_NOTIFY_SUCCESS, self._assembly_notify_success_cb.isChecked())
        settings.setValue(AppSettingKeys.ASSEMBLY_COMMAND, self._assembly_command_input.text())

        settings.setValue(AppSettingKeys.EDITOR_CODE_FONT_BOLD, self._editor_code_font_bold_cb.isChecked())
        settings.setValue(AppSettingKeys.EDITOR_CODE_FONT_SIZE, self._editor_code_font_size_sb.value())
        settings.setValue(AppSettingKeys.EDITOR_REFERENCE_FONT_SIZE, self._editor_reference_font_size_sb.value())
        settings.setValue(AppSettingKeys.EDITOR_SEARCH_FONT_SIZE, self._editor_search_font_size_sb.value())
        settings.setValue(AppSettingKeys.EDITOR_TOOLTIP_MAX_RESULTS, self._editor_tooltip_max_results_sb.value())

        settings.sync()


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    settings_dialog = SettingsDialog()

    settings_dialog.show()

    sys.exit(app.exec())
