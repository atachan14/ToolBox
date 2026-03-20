from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QKeyEvent, QPalette, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .canvas import CanvasConfig, ClipPathCanvas
from .state import MODE_INPUT, MODE_VIEW, SIZE_TYPE_PERCENT, ClipPoint


class ClipPathWindow(QMainWindow):
    MAX_HISTORY = 100

    def __init__(self):
        super().__init__()

        self.points: list[ClipPoint] = []
        self.ctrl_pressed = False
        self.last_mode_button: QPushButton | None = None

        self.undo_stack: list[list[ClipPoint]] = []
        self.redo_stack: list[list[ClipPoint]] = []

        self.copy_feedback_base_text = ""
        self.history_path = Path(__file__).resolve().parents[2] / "tabs" / "Clip-Path" / "history.json"
        self._table_syncing = False

        self._build_ui()
        self._connect_ui()
        self._refresh_views()

    def _build_ui(self):
        self.setWindowTitle("Clip-Path")

        body = QWidget()
        root_layout = QVBoxLayout(body)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)

        palette = self.palette()
        border_color = palette.color(QPalette.Mid).name()

        container_style = f"""
        #mode_box, #size_box, #grid_box {{
            border: 1px solid {border_color};
            border-radius: 6px;
        }}
        """

        button_style = """
        QPushButton {
            padding: 2px 8px;
        }
        """

        mode_box = QWidget()
        mode_box.setObjectName("mode_box")
        mode_layout = QHBoxLayout(mode_box)
        mode_layout.setContentsMargins(6, 2, 6, 2)
        mode_layout.setSpacing(4)

        self.mode_input = QPushButton("入力")
        self.mode_screen = QPushButton("画面")
        self.mode_circle = QPushButton("円")

        for btn in [self.mode_input, self.mode_screen, self.mode_circle]:
            btn.setCheckable(True)
            btn.setStyleSheet(button_style)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.mode_input)
        self.mode_group.addButton(self.mode_screen)
        self.mode_group.addButton(self.mode_circle)
        self.mode_input.setChecked(True)
        self.last_mode_button = self.mode_input

        mode_layout.addWidget(self.mode_input)
        mode_layout.addWidget(self.mode_screen)
        mode_layout.addWidget(self.mode_circle)

        size_box = QWidget()
        size_box.setObjectName("size_box")
        size_layout = QHBoxLayout(size_box)
        size_layout.setContentsMargins(6, 2, 6, 2)
        size_layout.setSpacing(4)

        self.size_h = QSpinBox()
        self.size_h.setRange(1, 9999)
        self.size_h.setValue(100)
        self.size_h.setButtonSymbols(QSpinBox.NoButtons)
        self.size_h.setFixedWidth(50)

        self.size_w = QSpinBox()
        self.size_w.setRange(1, 9999)
        self.size_w.setValue(100)
        self.size_w.setButtonSymbols(QSpinBox.NoButtons)
        self.size_w.setFixedWidth(50)

        self.unit_px = QPushButton("px")
        self.unit_percent = QPushButton("%")
        self.unit_px.setCheckable(True)
        self.unit_percent.setCheckable(True)

        self.unit_group = QButtonGroup(self)
        self.unit_group.setExclusive(True)
        self.unit_group.addButton(self.unit_px)
        self.unit_group.addButton(self.unit_percent)
        self.unit_px.setChecked(True)

        self.unit_px.setStyleSheet(button_style)
        self.unit_percent.setStyleSheet(button_style)

        size_layout.addWidget(QLabel("h:"))
        size_layout.addWidget(self.size_h)
        size_layout.addWidget(QLabel("w:"))
        size_layout.addWidget(self.size_w)
        size_layout.addWidget(self.unit_px)
        size_layout.addWidget(QLabel("/"))
        size_layout.addWidget(self.unit_percent)

        grid_box = QWidget()
        grid_box.setObjectName("grid_box")
        grid_layout = QHBoxLayout(grid_box)
        grid_layout.setContentsMargins(6, 2, 6, 2)
        grid_layout.setSpacing(4)

        self.grid_input = QSpinBox()
        self.grid_input.setRange(1, 999)
        self.grid_input.setValue(10)
        self.grid_input.setButtonSymbols(QSpinBox.NoButtons)
        self.grid_input.setFixedWidth(50)

        self.grid_on = QPushButton("ON")
        self.grid_off = QPushButton("OFF")
        self.grid_on.setCheckable(True)
        self.grid_off.setCheckable(True)

        self.grid_group = QButtonGroup(self)
        self.grid_group.setExclusive(True)
        self.grid_group.addButton(self.grid_on)
        self.grid_group.addButton(self.grid_off)
        self.grid_off.setChecked(True)

        self.grid_on.setStyleSheet(button_style)
        self.grid_off.setStyleSheet(button_style)

        grid_layout.addWidget(QLabel("Grid:"))
        grid_layout.addWidget(self.grid_input)
        grid_layout.addWidget(self.grid_on)
        grid_layout.addWidget(QLabel("/"))
        grid_layout.addWidget(self.grid_off)

        toolbar.setStyleSheet(container_style)
        toolbar_layout.addWidget(mode_box)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(size_box)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(grid_box)

        root_layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter, stretch=1)

        self.canvas = ClipPathCanvas(
            CanvasConfig(
                mode_getter=self._effective_mode,
                points_getter=lambda: self.points,
                size_getter=self._get_size,
                grid_getter=self._get_grid,
                on_points_changed=self._refresh_views,
                on_cursor_changed=self._on_cursor_changed,
                on_push_history=self._push_undo_state,
            )
        )
        splitter.addWidget(self.canvas)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.point_table = QTableWidget(0, 2)
        self.point_table.setHorizontalHeaderLabels(["X", "Y"])
        self.point_table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.point_table.setColumnWidth(0, 72)
        self.point_table.setColumnWidth(1, 72)
        right_layout.addWidget(self.point_table)

        splitter.addWidget(right_panel)
        splitter.setSizes([600, 260])

        footer = QHBoxLayout()
        self.cursor_label = QLabel("Cursor: x=0.00%, y=0.00%")
        footer.addWidget(self.cursor_label)

        footer.addStretch()

        self.code_area = QScrollArea()
        self.code_area.setWidgetResizable(False)
        self.code_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.code_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.code_area.setFixedHeight(30)
        self.code_label = QLabel("clip-path: polygon();")
        self.code_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.code_label.setWordWrap(False)
        self.code_label.setStyleSheet("padding: 4px;")
        self.code_label.adjustSize()
        self.code_area.setWidget(self.code_label)
        self.code_area.mousePressEvent = self._on_code_clicked
        self.code_label.mousePressEvent = self._on_code_clicked
        self.code_area.wheelEvent = self._on_code_wheel
        footer.addWidget(self.code_area)

        root_layout.addLayout(footer)

        self.setCentralWidget(body)

    def _connect_ui(self):
        self.mode_group.buttonClicked.connect(self._on_mode_clicked)

        self.size_h.valueChanged.connect(self._on_size_changed)
        self.size_w.valueChanged.connect(self._on_size_changed)
        self.unit_px.clicked.connect(self._on_size_changed)
        self.unit_percent.clicked.connect(self._on_size_changed)

        self.grid_input.valueChanged.connect(self._on_grid_changed)
        self.grid_on.clicked.connect(self._on_grid_changed)
        self.grid_off.clicked.connect(self._on_grid_changed)
        self.point_table.itemChanged.connect(self._on_point_item_changed)

    def _on_mode_clicked(self, btn):
        self.last_mode_button = btn
        self.canvas.update()

    def _on_mode_clicked(self, btn):
        self.last_mode_button = btn
        self.canvas.update()

    def _on_size_changed(self, *_):
        is_px = self.unit_px.isChecked()
        self.size_h.setEnabled(is_px)
        self.size_w.setEnabled(is_px)

        self.canvas.update()
        self._refresh_views()

    def _on_grid_changed(self, *_):
        self.canvas.update()
        self._refresh_views()

    def _effective_mode(self) -> str:
        if self.ctrl_pressed:
            return MODE_VIEW

        if self.mode_input.isChecked():
            return MODE_INPUT

        return MODE_VIEW if self.mode_screen.isChecked() else "円"

    def _get_size(self) -> tuple[float, float, str]:
        unit = "px" if self.unit_px.isChecked() else SIZE_TYPE_PERCENT
        return float(self.size_w.value()), float(self.size_h.value()), unit

    def _get_grid(self) -> tuple[bool, int]:
        return self.grid_on.isChecked(), max(1, self.grid_input.value())

    def _on_cursor_changed(self, raw: ClipPoint, snapped: ClipPoint):
        active, _ = self._get_grid()
        point = snapped if active else raw
        out_x, out_y = self._to_output(point)
        self.cursor_label.setText(f"Cursor: x={out_x}, y={out_y}")

    def _to_output(self, point: ClipPoint) -> tuple[str, str]:
        width, height, unit = self._get_size()

        if unit == SIZE_TYPE_PERCENT:
            return f"{point.x * 100:.2f}%", f"{point.y * 100:.2f}%"

        return f"{point.x * width:.1f}px", f"{point.y * height:.1f}px"

    def _to_table_output(self, point: ClipPoint) -> tuple[str, str]:
        width, height, unit = self._get_size()

        if unit == SIZE_TYPE_PERCENT:
            return f"{point.x * 100:.2f}", f"{point.y * 100:.2f}"

        return f"{point.x * width:.1f}", f"{point.y * height:.1f}"

    def _table_to_point(self, row: int) -> ClipPoint | None:
        x_item = self.point_table.item(row, 0)
        y_item = self.point_table.item(row, 1)

        if not x_item or not y_item:
            return None

        x_text = x_item.text().replace("px", "").replace("%", "").strip()
        y_text = y_item.text().replace("px", "").replace("%", "").strip()

        try:
            x_value = float(x_text)
            y_value = float(y_text)
        except ValueError:
            return None

        width, height, unit = self._get_size()

        if unit == SIZE_TYPE_PERCENT:
            return ClipPoint(x_value / 100.0, y_value / 100.0)

        return ClipPoint(
            x_value / max(width, 1.0),
            y_value / max(height, 1.0),
        )

    def _build_code(self) -> str:
        if not self.points:
            return "clip-path: polygon();"

        text = ", ".join(
            f"{x} {y}" for x, y in (self._to_output(point) for point in self.points)
        )

        return f"clip-path: polygon({text});"

    def _refresh_views(self):
        self._table_syncing = True
        self.point_table.setRowCount(len(self.points))

        for row, point in enumerate(self.points):
            out_x, out_y = self._to_table_output(point)
            self.point_table.setItem(row, 0, QTableWidgetItem(out_x))
            self.point_table.setItem(row, 1, QTableWidgetItem(out_y))
        self._table_syncing = False

        text = self._build_code()
        self.copy_feedback_base_text = text
        self.code_label.setStyleSheet("padding: 4px;")
        self.code_label.setText(text)
        self.code_label.adjustSize()

    def _clone_points(self) -> list[ClipPoint]:
        return [ClipPoint(point.x, point.y) for point in self.points]

    def _push_undo_state(self):
        self.undo_stack.append(self._clone_points())
        self.redo_stack.clear()

    def _apply_points(self, points: list[ClipPoint]):
        self.points = [ClipPoint(point.x, point.y) for point in points]
        self._refresh_views()
        self.canvas.update()

    def _undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append(self._clone_points())
        self._apply_points(self.undo_stack.pop())

    def _redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append(self._clone_points())
        self._apply_points(self.redo_stack.pop())

    def _save_history_entry(self, code: str):
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

        entries: list[str] = []
        if self.history_path.exists():
            try:
                loaded = json.loads(self.history_path.read_text(encoding="utf-8") or "[]")
                if isinstance(loaded, list):
                    entries = [str(item) for item in loaded if isinstance(item, str)]
            except json.JSONDecodeError:
                entries = []

        if entries and entries[0] == code:
            return

        entries.insert(0, code)
        self.history_path.write_text(
            json.dumps(entries[: self.MAX_HISTORY], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _on_code_clicked(self, _event):
        code = self._build_code()
        QApplication.clipboard().setText(code)
        self._save_history_entry(code)

        self.code_label.setStyleSheet("padding: 4px; color: #4ecdc4;")
        self.code_label.setText("copy and saved")

        def _restore():
            self.code_label.setStyleSheet("padding: 4px;")
            self.code_label.setText(self.copy_feedback_base_text)

        QTimer.singleShot(700, _restore)

    def _on_code_wheel(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        bar = self.code_area.horizontalScrollBar()
        bar.setValue(bar.value() - int(delta / 4))
        event.accept()

    def _on_point_item_changed(self, item: QTableWidgetItem):
        if self._table_syncing:
            return

        row = item.row()
        if row < 0 or row >= len(self.points):
            return

        point = self._table_to_point(row)
        if point is None:
            return

        self._push_undo_state()
        self.points[row] = point
        self.canvas.update()
        self._refresh_views()

    def keyPressEvent(self, event: QKeyEvent):
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_Z:
            self._undo()
            return

        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_Y:
            self._redo()
            return

        if event.key() == Qt.Key_Control and not self.ctrl_pressed:
            self.ctrl_pressed = True
            self.last_mode_button = self.mode_group.checkedButton() or self.last_mode_button
            self.mode_screen.setChecked(True)
            self.canvas.set_temp_mode(MODE_VIEW)
            self.canvas.update()

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = False
            if self.last_mode_button:
                self.last_mode_button.setChecked(True)
            self.canvas.set_temp_mode(None)
            self.canvas.update()

        super().keyReleaseEvent(event)
