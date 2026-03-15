import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from core.window import MainWindow
from core.update import (
    check_update,
    download_update,
    extract_update,
    launch_updater
)


def main():

    app = QApplication(sys.argv)

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

            launch_updater(extract_dir)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()