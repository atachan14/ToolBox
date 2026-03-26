from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QSplitter, QWidget

from .content_view import HelpContentView
from .image_window import HelpImageWindow
from .parser import parse_help_document
from .toc_view import HelpTocView


class HelpWindow(QWidget):
    def __init__(self, title: str, markdown_path: Path, parent=None):
        super().__init__(parent, Qt.Window)
        self.base_title = title
        self.markdown_path = Path(markdown_path)
        self.setWindowTitle(title)
        self.resize(480, 480)
        self.setMinimumWidth(420)
        self.setMinimumHeight(320)
        self._image_window_initialized = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Horizontal, self)
        layout.addWidget(self.splitter)

        self.toc_view = HelpTocView(self.splitter)
        self.content_view = HelpContentView(self.splitter)
        self.toc_view.setMinimumWidth(90)
        self.content_view.setMinimumWidth(220)
        self.splitter.addWidget(self.toc_view)
        self.splitter.addWidget(self.content_view)
        self.splitter.setSizes([150, 330])

        self.image_window = HelpImageWindow(f"{title} Images", self)

        self.toc_view.sectionSelected.connect(self.content_view.scroll_to_section)
        self.content_view.imageLinkClicked.connect(self._show_image_target)

        self.reload()

    def reload(self):
        try:
            document = parse_help_document(self.markdown_path)
        except OSError as exc:
            QMessageBox.warning(self, "Help", f"Could not load help.\n{exc}")
            return
        self.setWindowTitle(self.base_title)
        self.toc_view.set_document(document)
        self.content_view.set_document(document)
        self.image_window.setWindowTitle(f"{self.base_title} Images")
        self.image_window.set_document(document)

    def _show_image_target(self, path: Path):
        self.image_window.scroll_to_image(path)

    def _position_windows(self):
        gap = 12
        if self.parentWidget() is not None:
            parent_frame = self.parentWidget().frameGeometry()
            help_pos = parent_frame.topLeft() + QPoint(40, 40)
            screen = QGuiApplication.screenAt(parent_frame.center())
        else:
            help_pos = self.pos()
            screen = QGuiApplication.screenAt(self.frameGeometry().center())

        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.move(help_pos)
            self.image_window.move(help_pos + QPoint(self.width() + gap, 0))
            return

        available = screen.availableGeometry()
        help_width = self.frameGeometry().width()
        help_height = self.frameGeometry().height()
        image_width = self.image_window.frameGeometry().width()
        image_height = self.image_window.frameGeometry().height()

        combined_left = help_pos.x()
        combined_top = help_pos.y()
        combined_right = help_pos.x() + help_width + gap + image_width
        combined_bottom = help_pos.y() + max(help_height, image_height)

        shift_x = 0
        shift_y = 0

        if combined_right > available.right():
            shift_x = available.right() - combined_right
        if combined_left + shift_x < available.left():
            shift_x = available.left() - combined_left

        if combined_bottom > available.bottom():
            shift_y = available.bottom() - combined_bottom
        if combined_top + shift_y < available.top():
            shift_y = available.top() - combined_top

        final_help = help_pos + QPoint(shift_x, shift_y)
        final_image = final_help + QPoint(help_width + gap, 0)

        if final_image.x() + image_width > available.right():
            final_image.setX(max(available.left(), available.right() - image_width))
        if final_image.y() + image_height > available.bottom():
            final_image.setY(max(available.top(), available.bottom() - image_height))

        self.move(final_help)
        self.image_window.move(final_image)

    def showEvent(self, event):
        super().showEvent(event)
        if self._image_window_initialized:
            return
        self._image_window_initialized = True
        self._position_windows()
        self.image_window.show()

    def closeEvent(self, event):
        self.image_window.close()
        super().closeEvent(event)
