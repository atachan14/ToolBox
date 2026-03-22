from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, QWidget

from core.flow_layout import FlowLayout


class GradientToolbar(QWidget):
    changed = Signal()

    def __init__(self, button_height: int, parent: QWidget | None = None):
        super().__init__(parent)
        self._button_height = button_height
        self._build_ui()
        self._connect_ui()

    def _build_ui(self):
        layout = FlowLayout(self, margin=0, spacing=2)
        border_color = self.palette().color(QPalette.Mid).name()
        self.setStyleSheet(
            f"""
            #size_box, #grid_box, #guide_box {{
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
            """
        )

        size_box = QWidget()
        size_box.setObjectName("size_box")
        size_layout = QHBoxLayout(size_box)
        size_layout.setContentsMargins(4, 2, 4, 2)
        size_layout.setSpacing(2)
        size_layout.addWidget(QLabel("H:"))
        self.size_h = QSpinBox()
        self.size_h.setRange(1, 9999)
        self.size_h.setValue(100)
        self.size_h.setButtonSymbols(QSpinBox.NoButtons)
        self.size_h.setFixedWidth(46)
        self.size_h.setFixedHeight(self._button_height)
        size_layout.addWidget(self.size_h)
        size_layout.addWidget(QLabel("W:"))
        self.size_w = QSpinBox()
        self.size_w.setRange(1, 9999)
        self.size_w.setValue(100)
        self.size_w.setButtonSymbols(QSpinBox.NoButtons)
        self.size_w.setFixedWidth(46)
        self.size_w.setFixedHeight(self._button_height)
        size_layout.addWidget(self.size_w)
        self.unit_px = QPushButton("px")
        self.unit_percent = QPushButton("%")
        for button in (self.unit_px, self.unit_percent):
            button.setCheckable(True)
            button.setFixedHeight(self._button_height)
            button.setStyleSheet("padding: 0px 6px;")
            size_layout.addWidget(button)
        self.unit_percent.setChecked(True)

        guide_box = QWidget()
        guide_box.setObjectName("guide_box")
        guide_layout = QHBoxLayout(guide_box)
        guide_layout.setContentsMargins(4, 2, 4, 2)
        guide_layout.setSpacing(2)
        guide_layout.addWidget(QLabel("Guide:"))
        self.guide_check = QCheckBox()
        self.guide_check.setChecked(True)
        self.guide_check.setFixedHeight(self._button_height)
        guide_layout.addWidget(self.guide_check)

        grid_box = QWidget()
        grid_box.setObjectName("grid_box")
        grid_layout = QHBoxLayout(grid_box)
        grid_layout.setContentsMargins(4, 2, 4, 2)
        grid_layout.setSpacing(2)
        grid_layout.addWidget(QLabel("Grid:"))
        self.grid_input = QSpinBox()
        self.grid_input.setRange(1, 999)
        self.grid_input.setValue(10)
        self.grid_input.setButtonSymbols(QSpinBox.NoButtons)
        self.grid_input.setFixedWidth(46)
        self.grid_input.setFixedHeight(self._button_height)
        self.grid_check = QCheckBox()
        self.grid_check.setChecked(True)
        self.grid_check.setFixedHeight(self._button_height)
        grid_layout.addWidget(self.grid_input)
        grid_layout.addWidget(self.grid_check)

        layout.addWidget(size_box)
        layout.addWidget(grid_box)
        layout.addWidget(guide_box)

    def _connect_ui(self):
        self.size_h.valueChanged.connect(lambda *_: self.changed.emit())
        self.size_w.valueChanged.connect(lambda *_: self.changed.emit())
        self.grid_input.valueChanged.connect(lambda *_: self.changed.emit())
        self.grid_check.toggled.connect(lambda *_: self.changed.emit())
        self.guide_check.toggled.connect(lambda *_: self.changed.emit())
        self.unit_px.clicked.connect(self._on_unit_changed)
        self.unit_percent.clicked.connect(self._on_unit_changed)

    def _on_unit_changed(self):
        sender = self.sender()
        self.unit_px.setChecked(sender is self.unit_px)
        self.unit_percent.setChecked(sender is self.unit_percent)
        self.changed.emit()

    def get_size(self) -> tuple[float, float, str]:
        return float(self.size_w.value()), float(self.size_h.value()), self.unit_name()

    def get_grid(self) -> tuple[bool, int]:
        return self.grid_check.isChecked(), self.grid_input.value()

    def guide_enabled(self) -> bool:
        return self.guide_check.isChecked()

    def unit_name(self) -> str:
        return "px" if self.unit_px.isChecked() else "%"
