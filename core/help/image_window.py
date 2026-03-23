from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from .models import HelpDocument


class _ImageItem(QWidget):
    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.path = path
        self._pixmap = QPixmap(str(path))
        self._viewport_size = QSize(400, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel(path.name)
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(title)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.image_label)

        if self._pixmap.isNull():
            self.image_label.setText("Image could not be loaded.")
            self.image_label.setMinimumHeight(80)
        else:
            self._update_pixmap()

    def set_viewport_size(self, size: QSize):
        self._viewport_size = QSize(max(1, size.width()), max(1, size.height()))
        self._update_pixmap()

    def _update_pixmap(self):
        if self._pixmap.isNull():
            return
        available = QSize(
            max(1, self._viewport_size.width() - 16),
            max(1, self._viewport_size.height() - 44),
        )
        scaled = self._pixmap.scaled(available, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)
        self.image_label.setFixedSize(scaled.size())
        self.setMinimumHeight(scaled.height() + 46)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_pixmap()


class HelpImageWindow(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent, Qt.Window)
        self._items: dict[Path, QWidget] = {}
        self.setWindowTitle(title)
        self.resize(420, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        layout.addWidget(self.scroll)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(8, 8, 8, 8)
        self.container_layout.setSpacing(8)
        self.container_layout.addStretch(1)
        self.scroll.setWidget(self.container)

    def set_document(self, document: HelpDocument):
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._items = {}
        if not document.images:
            empty = QLabel("No images referenced in this help.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setMinimumSize(QSize(200, 120))
            self.container_layout.addWidget(empty)
            self.container_layout.addStretch(1)
            return

        for image in document.images:
            item = _ImageItem(image.path, self.container)
            self.container_layout.addWidget(item)
            self._items[image.path.resolve()] = item
        self._apply_viewport_size_to_items()
        self.container_layout.addStretch(1)
        self.scroll.verticalScrollBar().setValue(0)

    def scroll_to_image(self, path: Path):
        item = self._items.get(path.resolve())
        if item is None:
            return
        self.show()
        self.raise_()
        self.activateWindow()
        self.scroll.ensureWidgetVisible(item, 0, 12)

    def _apply_viewport_size_to_items(self):
        viewport_size = self.scroll.viewport().size()
        for item in self._items.values():
            if isinstance(item, _ImageItem):
                item.set_viewport_size(viewport_size)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_viewport_size_to_items()

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_viewport_size_to_items()
