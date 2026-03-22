from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from .widgets import CodeLineEdit


class GradientFooter(QWidget):
    def __init__(self, on_code_clicked, on_code_wheel, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.cursor_label = QLabel("Cursor: x=0.00%, y=0.00%")
        cursor_metrics = QFontMetrics(self.cursor_label.font())
        cursor_width = max(
            cursor_metrics.horizontalAdvance("Cursor: x=100.00%, y=100.00%"),
            cursor_metrics.horizontalAdvance("Cursor: x=9999.0px, y=9999.0px"),
        )
        self.cursor_label.setFixedWidth(cursor_width + 8)
        layout.addWidget(self.cursor_label)
        self.code_label = CodeLineEdit(on_code_clicked, on_code_wheel)
        self.code_label.setReadOnly(True)
        self.code_label.setFrame(False)
        self.code_label.setFixedHeight(30)
        self.code_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.code_label.setTextMargins(4, 0, 4, 0)
        self.code_label.setStyleSheet("background: transparent; border: none;")
        self.code_label.setToolTip("Click to copy and save to history.\nScroll to view horizontally.")
        layout.addWidget(self.code_label, 1)

    def set_cursor_text(self, text: str):
        self.cursor_label.setText(text)
