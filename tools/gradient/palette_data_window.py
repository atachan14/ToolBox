from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QDialog, QHBoxLayout, QInputDialog, QLineEdit, QListWidget, QListWidgetItem, QMenu, QVBoxLayout, QWidget

from .widgets import paint_alpha_pattern


class ScrollableNameEdit(QLineEdit):
    def __init__(self, text: str, on_commit: Callable[[str], None], parent: QWidget | None = None):
        super().__init__(text, parent)
        self._on_commit = on_commit
        self.setMinimumWidth(0)
        self.setFixedWidth(self.fontMetrics().horizontalAdvance("0" * 10) + 18)
        self.editingFinished.connect(self._commit)

    def _commit(self):
        self._on_commit(self.text().strip())


class ScrollableSwatchStrip(QWidget):
    def __init__(self, colors: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self._colors = list(colors)
        self._offset = 0
        self._swatch_size = 16
        self._spacing = 4
        self.setMinimumWidth(0)
        self.setMinimumHeight(20)

    def _content_width(self) -> int:
        if not self._colors:
            return 0
        return len(self._colors) * (self._swatch_size + self._spacing) - self._spacing

    def wheelEvent(self, event: QWheelEvent):
        content_width = self._content_width()
        max_offset = max(0, content_width - max(1, self.width() - 12))
        delta = event.angleDelta().y()
        if delta == 0 or max_offset == 0:
            event.ignore()
            return
        step = max(8, (abs(delta) // 120) * (self._swatch_size + self._spacing))
        direction = -1 if delta > 0 else 1
        self._offset = max(0, min(max_offset, self._offset + (direction * step)))
        self.update()
        event.accept()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        clip_rect = self.rect().adjusted(6, 2, -6, -2)
        painter.setClipRect(clip_rect)
        x = clip_rect.x() - self._offset
        y = clip_rect.y() + max(0, (clip_rect.height() - self._swatch_size) // 2)
        for color in self._colors:
            rect = QRectF(x, y, self._swatch_size, self._swatch_size)
            if rect.right() >= clip_rect.left() and rect.left() <= clip_rect.right():
                paint_alpha_pattern(painter, rect, str(color), "#6b7280", border_width=1, radius=3.0)
            x += self._swatch_size + self._spacing
        painter.setClipping(False)
        painter.setPen(QPen(QColor("#9ca3af")))
        if self._offset > 0:
            painter.drawText(QRectF(0, 0, 12, self.height()), Qt.AlignVCenter | Qt.AlignLeft, "...")
        if self._offset < max(0, self._content_width() - max(1, self.width() - 12)):
            painter.drawText(QRectF(self.width() - 12, 0, 12, self.height()), Qt.AlignVCenter | Qt.AlignRight, "...")


class PaletteDataWindow(QDialog):
    def __init__(
        self,
        load_entries: Callable[[], list[dict]],
        apply_palette: Callable[[dict], None],
        rename_palette: Callable[[Path, str], None],
        delete_palette: Callable[[Path], None],
        parent=None,
    ):
        super().__init__(parent)
        self._load_entries = load_entries
        self._apply_palette = apply_palette
        self._rename_palette = rename_palette
        self._delete_palette = delete_palette
        self.setWindowTitle("Palette Data")
        self.resize(360, 320)
        self._build_ui()
        self._reload_entries()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.customContextMenuRequested.connect(self._show_item_menu)
        layout.addWidget(self.list_widget)

    def _reload_entries(self):
        self.list_widget.clear()
        for entry in self._load_entries():
            item = QListWidgetItem()
            item.setData(Qt.UserRole, entry)
            widget = self._build_item_widget(entry)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def _build_item_widget(self, entry: dict) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        path = entry.get("path")
        name_label = ScrollableNameEdit(str(entry.get("name", "")), lambda value, palette_path=path: self._rename_entry(palette_path, value))
        swatch_strip = ScrollableSwatchStrip([str(color) for color in entry.get("colors") or []])
        layout.addWidget(name_label, 0)
        layout.addWidget(swatch_strip, 1)
        return widget

    def _rename_entry(self, path: Path | None, new_name: str):
        if not isinstance(path, Path):
            return
        self._rename_palette(path, new_name)
        self._reload_entries()

    def _on_item_clicked(self, item: QListWidgetItem):
        entry = item.data(Qt.UserRole)
        if not isinstance(entry, dict):
            return
        self._apply_palette(entry)
        self.accept()

    def _show_item_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if item is None:
            return
        entry = item.data(Qt.UserRole)
        if not isinstance(entry, dict):
            return
        path = entry.get("path")
        if not isinstance(path, Path):
            return
        menu = QMenu(self.list_widget)
        rename_action = menu.addAction("名前の変更")
        delete_action = menu.addAction("削除")
        action = menu.exec(self.list_widget.viewport().mapToGlobal(pos))
        if action == rename_action:
            current_name = str(entry.get("name", "palette"))
            new_name, accepted = QInputDialog.getText(self, "Rename Palette", "Name", text=current_name)
            if accepted:
                self._rename_palette(path, new_name)
                self._reload_entries()
            return
        if action == delete_action:
            self._delete_palette(path)
            self._reload_entries()
