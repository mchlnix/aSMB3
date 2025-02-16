from pathlib import Path

from PySide6.QtGui import QAction, QCursor, QGuiApplication, Qt
from PySide6.QtWidgets import QMenu, QMessageBox

from foundry import NO_PARENT, icon
from foundry.data_source.rom import ROM
from foundry.game.level.LevelRef import LevelRef
from foundry.gui.asm import (
    load_asm_filename,
    load_asm_level,
    make_fns_file_absolute,
    save_asm,
    save_asm_filename,
)
from foundry.gui.dialogs.fns_asm_load_dialog import FnsAsmLoadDialog
from foundry.gui.m3l import save_m3l, save_m3l_filename
from foundry.gui.settings import Settings
from smb3parse.constants import update_global_offsets


class FileMenu(QMenu):
    def __init__(self, level_ref: LevelRef, settings: Settings, title="&File"):
        super(FileMenu, self).__init__(title)

        self.level_ref = level_ref
        self.settings = settings

        self.triggered.connect(self._on_trigger)

        self.open_rom_action = self.addAction("Open ROM")
        self.open_rom_action.setIcon(icon("folder.svg"))

        self.addSeparator()

        self.save_rom_action = self.addAction("Save ROM")
        self.save_rom_action.setIcon(icon("save.svg"))
        self.save_rom_action.setShortcut(Qt.Modifier.CTRL | Qt.Key.Key_S)

        self.save_rom_as_action = self.addAction("Save ROM as ...")
        self.save_rom_as_action.setIcon(icon("save.svg"))

        self.addSeparator()

        m3l_menu = QMenu("M3L")
        m3l_menu.setIcon(icon("file.svg"))

        self.open_m3l_action = m3l_menu.addAction("Open M3L")
        self.open_m3l_action.setIcon(icon("folder.svg"))

        self.save_m3l_action = m3l_menu.addAction("Save M3L")
        self.save_m3l_action.setIcon(icon("save.svg"))

        asm_menu = QMenu("ASM")
        asm_menu.setIcon(icon("cpu.svg"))

        self.open_level_asm_action = asm_menu.addAction("Open Level")
        self.open_level_asm_action.setIcon(icon("folder.svg"))
        # open_level_asm.triggered.connect(self.on_open_asm)

        self.save_level_asm_action = asm_menu.addAction("Save Level")
        self.save_level_asm_action.setIcon(icon("save.svg"))

        asm_menu.addSeparator()

        self.import_enemy_asm_action = asm_menu.addAction("Import Enemies")
        self.import_enemy_asm_action.setIcon(icon("upload.svg"))

        self.export_enemy_asm_action = asm_menu.addAction("Export Enemies")
        self.export_enemy_asm_action.setIcon(icon("download.svg"))

        asm_menu.addSeparator()

        self.import_fns_action = asm_menu.addAction("Import FNS Addresses")
        self.import_fns_action.setIcon(icon("upload.svg"))

        self.addMenu(m3l_menu)
        self.addMenu(asm_menu)

        self.addSeparator()

        self.settings_action = self.addAction("Editor Settings")
        self.settings_action.setIcon(icon("sliders.svg"))

        self.addSeparator()

        self.exit_action = self.addAction("Exit")
        self.exit_action.setIcon(icon("power.svg"))

    def _on_trigger(self, action: QAction):
        if action is self.save_level_asm_action:
            self.on_save_level_asm()
        elif action is self.export_enemy_asm_action:
            self.on_save_enemy_asm()
        elif action is self.open_level_asm_action:
            self.on_open_level_asm()
        elif action is self.save_m3l_action:
            self.on_save_m3l()
        elif action is self.import_fns_action:
            self.on_fns_import()

    def on_open_level_asm(self):
        if not (pathname := load_asm_filename("Level ASM", self.settings.value("editor/default dir path"))):
            return

        load_asm_level(pathname, self.level_ref.level)

    def on_save_level_asm(self):
        suggested_file = f"{self.settings.value('editor/default dir path')}/{self.level_ref.name}.asm"

        level_asm, _ = self.level_ref.level.to_asm()

        self.save_asm(suggested_file, level_asm, "Level ASM")

    def on_save_enemy_asm(self):
        suggested_file = f"{self.settings.value('editor/default dir path')}/{self.level_ref.name}_enemy.asm"

        _, enemy_asm = self.level_ref.level.to_asm()

        self.save_asm(suggested_file, enemy_asm, "Enemy ASM")

    def save_asm(self, suggested_file: str, asm: str, what: str):
        if not (pathname := save_asm_filename(what, suggested_file)):
            return

        save_asm(what, pathname, asm)

    def on_save_m3l(self):
        suggested_file = self.settings.value("editor/default dir path") + "/" + self.level_ref.name + ".m3l"

        if not (pathname := save_m3l_filename(suggested_file)):
            return

        m3l_bytes = self.level_ref.level.to_m3l()

        save_m3l(pathname, m3l_bytes)

    def on_fns_import(self):
        open_dialog = FnsAsmLoadDialog(NO_PARENT, ROM.fns_path, ROM.smb3_asm_path)
        if open_dialog.exec() == FnsAsmLoadDialog.DialogCode.Rejected:
            return

        try:
            QGuiApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

            absolute_fns_path = make_fns_file_absolute(Path(open_dialog.fns_path), Path(open_dialog.asm_path))

            update_global_offsets(absolute_fns_path)

            ROM.fns_path = open_dialog.fns_path
            ROM.smb3_asm_path = open_dialog.asm_path

        except Exception as e:
            QMessageBox.critical(NO_PARENT, "Failed updating globals", str(e))
            return

        finally:
            QGuiApplication.restoreOverrideCursor()

        ROM.reset_graphics()

        if self.level_ref:
            self.level_ref.data_changed.emit()

        QMessageBox.information(NO_PARENT, "Update complete", "Successfully updated the ASM globals.")
