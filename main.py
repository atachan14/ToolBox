import sys
from PySide6.QtWidgets import QApplication
from core.window import MainWindow
from core.update import check_update


def main():

    update = check_update()
    if update:
        print("New version:", update["version"])
    else:
        print("Latest version")

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()