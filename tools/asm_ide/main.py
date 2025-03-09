import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from tools.asm_ide.application_settings import init_settings
from tools.asm_ide.main_window import MainWindow

if __name__ == "__main__":
    app = None

    try:
        app = QApplication()

        init_settings()

        path_arg: Path | None = None

        if len(sys.argv) > 1:
            path_arg = Path(sys.argv[1])

            if not path_arg.is_file():
                raise ValueError(f"Argument given over command line was not a file. Was '{path_arg}'")

        main_window = MainWindow(path_arg)
        main_window.show()

        app.exec()

    except Exception as e:
        if app is None:
            app = QApplication()

        box = QMessageBox()
        box.setWindowTitle("Crash report")
        box.setText(
            f"An unexpected error occurred! Please contact Michael in the discord "
            f"with the error below:\n\n{e}\n\n{traceback.format_exc()}"
        )
        box.exec()

        raise
