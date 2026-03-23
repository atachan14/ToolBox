from __future__ import annotations

from pathlib import Path

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
        self._image_window_initialized = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Horizontal, self)
        layout.addWidget(self.splitter)

        self.toc_view = HelpTocView(self.splitter)
        self.content_view = HelpContentView(self.splitter)
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

    def showEvent(self, event):
        super().showEvent(event)
        if self._image_window_initialized:
            return
        self._image_window_initialized = True
        if self.parentWidget() is not None:
            parent_frame = self.parentWidget().frameGeometry()
            self.move(parent_frame.topLeft() + QPoint(40, 40))
        self.image_window.move(self.frameGeometry().topRight() + QPoint(12, 0))
        self.image_window.show()

    def closeEvent(self, event):
        self.image_window.close()
        super().closeEvent(event)
