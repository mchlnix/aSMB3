import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from tools.asm_ide.main_window import MainWindow
from tools.asm_ide.settings import init_settings

if __name__ == "__main__":
    app = None

    try:
        app = QApplication(sys.argv)

        init_settings()

        main_window = MainWindow()
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
