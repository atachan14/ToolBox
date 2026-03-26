import sys
import os
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon

from core.paths import resource_path
from core.window import MainWindow
from core.update import (
    check_update,
    download_update,
    extract_update,
    launch_updater
)

import ctypes
import time

def main():

    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("toolbox.app")

    app = QApplication(sys.argv)

    qss_path = resource_path("toolbox.qss")

    with open(qss_path, encoding="utf-8") as f:
        app.setStyleSheet(f.read())


    icon_path = resource_path("toolbox.ico")
    icon = QIcon(str(icon_path))

    app.setWindowIcon(icon)

    update = check_update()

    if update:

        reply = QMessageBox.question(
            None,
            "ToolBox Update",
            f"新しいバージョン {update['version']} があります。\n更新しますか？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:

            zip_path = download_update(update["url"])
            extract_dir = extract_update(zip_path)

            launch_updater(extract_dir, os.getpid())
            app.quit()
            return

    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
    
    
