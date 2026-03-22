from __future__ import annotations

import json
import math
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFontMetrics, QKeyEvent, QMouseEvent, QPainter, QPalette, QPen, QPixmap, QShowEvent, QTextLayout, QWheelEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QMenu,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from core.flow_layout import FlowLayout
from .canvas import CanvasConfig, ClipPathCanvas
from .state import MODE_CIRCLE, MODE_INPUT, MODE_VIEW, SIZE_TYPE_PERCENT, CircleGuide, ClipPoint


class CodeLineEdit(QLineEdit):
    def __init__(self, click_handler, wheel_handler, parent: QWidget | None = None):
        super().__init__(parent)
        self._click_handler = click_handler
        self._wheel_handler = wheel_handler

    def mousePressEvent(self, event):
        self._click_handler(event)
        super().mousePressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        self._wheel_handler(event)

    def enterEvent(self, event):
        if self.toolTip():
            QToolTip.showText(self.mapToGlobal(self.rect().bottomLeft()), self.toolTip(), self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        QToolTip.hideText()
        super().leaveEvent(event)


class SelectAllLineEdit(QLineEdit):
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if not self.hasFocus():
                self.setFocus(Qt.MouseFocusReason)
            QTimer.singleShot(0, self.selectAll)
            event.accept()
            return
        super().mousePressEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)


class PointTableWidget(QTableWidget):
    rowReordered = Signal(int, int)
    indexMenuRequested = Signal(int, QPoint)
    dragPreviewChanged = Signal(int, int)
    dragStateChanged = Signal(bool)

    def __init__(self, rows: int, columns: int, parent: QWidget | None = None):
        super().__init__(rows, columns, parent)
        self._drag_row: int | None = None
        self._drag_active = False
        self._press_pos: QPoint | None = None
        self._preview_row = -1

    def mousePressEvent(self, event: QMouseEvent):
        item = self.itemAt(event.position().toPoint())
        if item and item.column() == 0:
            self._drag_row = item.row()
            self._press_pos = event.position().toPoint()
            self._drag_active = event.button() == Qt.LeftButton
            if event.button() == Qt.RightButton:
                self.indexMenuRequested.emit(item.row(), self.viewport().mapToGlobal(event.position().toPoint()))
                event.accept()
                return
        else:
            self._drag_row = None
            self._drag_active = False
            self._press_pos = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if (
            self._drag_active
            and self._drag_row is not None
            and self._press_pos is not None
            and (event.position().toPoint() - self._press_pos).manhattanLength() >= QApplication.startDragDistance()
        ):
            self.dragStateChanged.emit(True)
            self.viewport().setCursor(QCursor(Qt.ClosedHandCursor))
            target_item = self.itemAt(event.position().toPoint())
            target_row = target_item.row() if target_item else self.rowAt(event.position().toPoint().y())
            if target_row != self._preview_row:
                self._preview_row = target_row
                self.dragPreviewChanged.emit(self._drag_row, self._preview_row)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._drag_active and self._drag_row is not None and event.button() == Qt.LeftButton:
            target_item = self.itemAt(event.position().toPoint())
            target_row = target_item.row() if target_item else self.rowAt(event.position().toPoint().y())
            if target_row >= 0 and target_row != self._drag_row:
                self.rowReordered.emit(self._drag_row, target_row)
        self.viewport().unsetCursor()
        self._drag_row = None
        self._drag_active = False
        self._press_pos = None
        self._preview_row = -1
        self.dragPreviewChanged.emit(-1, -1)
        self.dragStateChanged.emit(False)
        super().mouseReleaseEvent(event)


class HistoryPreviewWidget(QWidget):
    def __init__(self, pixmap: QPixmap, size_text: str, code_text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._size_text = size_text
        self.base_code_text = code_text
        self._display_lines = [code_text]
        self._display_color = QColor(self.palette().color(QPalette.Text))
        self._text_width = 120

    def set_text_width(self, width: int):
        self._text_width = width
        self.update()

    def set_preview_lines(self, lines: list[str]):
        self._display_lines = lines or [""]
        self._display_color = QColor(self.palette().color(QPalette.Text))
        self.update()

    def set_feedback_text(self, text: str):
        self._display_lines = [text]
        self._display_color = QColor("#4ecdc4")
        self.update()

    def line_count(self) -> int:
        return max(1, len(self._display_lines) or 1)

    def size_label_height(self) -> int:
        return self.fontMetrics().height()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        metrics = painter.fontMetrics()

        margin = 8
        gap = 10
        text_x = margin + self._pixmap.width() + gap
        size_y = margin + metrics.ascent()

        painter.drawPixmap(margin, margin, self._pixmap)

        painter.setPen(QColor("#7f8797"))
        painter.drawText(text_x, size_y, self._size_text)

        painter.setPen(self._display_color)
        line_y = margin + metrics.height() + 2 + metrics.ascent()
        for line in self._display_lines:
            painter.drawText(text_x, line_y, line)
            line_y += metrics.lineSpacing()


class ClipPathWindow(QMainWindow):
    MAX_HISTORY = 100
    DEFAULT_HISTORY_DIALOG_WIDTH = 620
    DEFAULT_HISTORY_DIALOG_HEIGHT = 360

    def __init__(
        self,
        state_path: Path | None = None,
        history_path: Path | None = None,
        ui_state_path: Path | None = None,
    ):
        super().__init__()
        self.points: list[ClipPoint] = []
        self.circles: list[CircleGuide] = []

        self.ctrl_pressed = False
        self.last_mode_button: QPushButton | None = None
        self.undo_stack: list[tuple[list[ClipPoint], list[CircleGuide]]] = []
        self.redo_stack: list[tuple[list[ClipPoint], list[CircleGuide]]] = []

        self.copy_feedback_base_text = ""
        self.state_path = Path(state_path) if state_path else None
        self.history_path = Path(history_path) if history_path else None
        self.ui_state_path = Path(ui_state_path) if ui_state_path else None
        self._table_syncing = False
        self._toolbar_button_height = 24
        self._code_full_text = "clip-path: polygon();"
        self._code_scroll_offset = 0
        self._history_dialog_width = self.DEFAULT_HISTORY_DIALOG_WIDTH
        self._history_dialog_height = self.DEFAULT_HISTORY_DIALOG_HEIGHT
        self._code_tooltip_text = "Click to copy and save to history.\nScroll to view horizontally."
        self._drag_source_row = -1
        self._drag_target_row = -1

        self._build_ui()
        self._connect_ui()
        self._restore_ui_state()
        self._restore_state()
        self._refresh_views()

    def set_state_path(self, state_path: Path | None):
        self.state_path = Path(state_path) if state_path else None
        self._save_state()

    def _restore_ui_state(self):
        if not self.ui_state_path or not self.ui_state_path.exists():
            return
        try:
            state = json.loads(self.ui_state_path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return
        if not isinstance(state, dict):
            return
        self._history_dialog_width = max(320, int(state.get("history_dialog_width", self.DEFAULT_HISTORY_DIALOG_WIDTH)))
        self._history_dialog_height = max(240, int(state.get("history_dialog_height", self.DEFAULT_HISTORY_DIALOG_HEIGHT)))

    def _save_ui_state(self):
        if not self.ui_state_path:
            return
        self.ui_state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "history_dialog_width": self._history_dialog_width,
            "history_dialog_height": self._history_dialog_height,
        }
        self.ui_state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _build_ui(self):
        self.setWindowTitle("Clip-Path")

        body = QWidget()
        root_layout = QVBoxLayout(body)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        toolbar = QWidget()
        toolbar_layout = FlowLayout(toolbar, margin=0, spacing=2)

        border_color = self.palette().color(QPalette.Mid).name()
        toolbar.setStyleSheet(
            f"""
            #size_box, #grid_box, #guide_box {{
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
            """
        )

        mode_box = QWidget()
        mode_box.setObjectName("mode_box")
        mode_layout = QHBoxLayout(mode_box)
        mode_layout.setContentsMargins(4, 2, 4, 2)
        mode_layout.setSpacing(2)
        self.mode_input = QPushButton("入力")
        self.mode_screen = QPushButton("画面")
        self.mode_circle = QPushButton("円")
        for btn in (self.mode_input, self.mode_screen, self.mode_circle):
            btn.setCheckable(True)
            btn.setFixedHeight(self._toolbar_button_height)
            btn.setStyleSheet("padding: 0px 6px;")
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for btn in (self.mode_input, self.mode_screen, self.mode_circle):
            self.mode_group.addButton(btn)
            mode_layout.addWidget(btn)
        self.mode_input.setChecked(True)
        self.last_mode_button = self.mode_input
        mode_box.hide()

        size_box = QWidget()
        size_box.setObjectName("size_box")
        size_layout = QHBoxLayout(size_box)
        size_layout.setContentsMargins(4, 2, 4, 2)
        size_layout.setSpacing(2)
        self.size_h = QSpinBox()
        self.size_w = QSpinBox()
        for spin in (self.size_h, self.size_w):
            spin.setRange(1, 9999)
            spin.setValue(100)
            spin.setButtonSymbols(QSpinBox.NoButtons)
            spin.setFixedWidth(46)
            spin.setFixedHeight(self._toolbar_button_height)
        self.unit_px = QPushButton("px")
        self.unit_percent = QPushButton("%")
        self.unit_px.setCheckable(True)
        self.unit_percent.setCheckable(True)
        self.unit_px.setFixedHeight(self._toolbar_button_height)
        self.unit_percent.setFixedHeight(self._toolbar_button_height)
        self.unit_px.setStyleSheet("padding: 0px 6px;")
        self.unit_percent.setStyleSheet("padding: 0px 6px;")
        self.unit_group = QButtonGroup(self)
        self.unit_group.setExclusive(True)
        self.unit_group.addButton(self.unit_px)
        self.unit_group.addButton(self.unit_percent)
        self.unit_percent.setChecked(True)
        size_layout.addWidget(QLabel("h:"))
        size_layout.addWidget(self.size_h)
        size_layout.addWidget(QLabel("w:"))
        size_layout.addWidget(self.size_w)
        size_layout.addWidget(self.unit_px)
        size_layout.addWidget(self.unit_percent)

        grid_box = QWidget()
        grid_box.setObjectName("grid_box")
        grid_layout = QHBoxLayout(grid_box)
        grid_layout.setContentsMargins(4, 2, 4, 2)
        grid_layout.setSpacing(2)
        self.grid_input = QSpinBox()
        self.grid_input.setRange(1, 999)
        self.grid_input.setValue(10)
        self.grid_input.setButtonSymbols(QSpinBox.NoButtons)
        self.grid_input.setFixedWidth(46)
        self.grid_input.setFixedHeight(self._toolbar_button_height)
        self.grid_check = QCheckBox()
        self.grid_check.setFixedHeight(self._toolbar_button_height)
        self.grid_check.setChecked(True)
        grid_layout.addWidget(QLabel("Grid:"))
        grid_layout.addWidget(self.grid_input)
        grid_layout.addWidget(self.grid_check)

        guide_box = QWidget()
        guide_box.setObjectName("guide_box")
        guide_layout = QHBoxLayout(guide_box)
        guide_layout.setContentsMargins(4, 2, 4, 2)
        guide_layout.setSpacing(2)
        self.guide_check = QCheckBox()
        self.guide_check.setFixedHeight(self._toolbar_button_height)
        self.guide_check.setChecked(True)
        guide_layout.addWidget(QLabel("Guide:"))
        guide_layout.addWidget(self.guide_check)

        toolbar_layout.addWidget(mode_box)
        toolbar_layout.addWidget(size_box)
        toolbar_layout.addWidget(grid_box)
        toolbar_layout.addWidget(guide_box)
        root_layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        self.canvas = ClipPathCanvas(
            CanvasConfig(
                circle_tool_active_getter=lambda: self.circle_tool_button.isChecked(),
                ctrl_pressed_getter=lambda: self.ctrl_pressed,
                guide_visible_getter=lambda: self.guide_check.isChecked(),
                points_getter=lambda: self.points,
                size_getter=self._get_size,
                grid_getter=self._get_grid,
                circles_getter=lambda: self.circles,
                snap_points_getter=self._get_snap_points,
                on_points_changed=self._refresh_views,
                on_point_targeted=self._focus_point_x_editor,
                on_cursor_changed=self._on_cursor_changed,
                on_push_history=self._push_undo_state,
                on_circle_created=self._on_circle_created,
                on_circle_removed=self._on_circle_removed,
            )
        )
        left_layout.addWidget(self.canvas, 1)
        circle_button_bg = self.palette().color(QPalette.Button).name()
        circle_button_fg = self.palette().color(QPalette.ButtonText).name()
        circle_button_active_bg = self.palette().color(QPalette.Highlight).name()
        circle_button_active_fg = self.palette().color(QPalette.HighlightedText).name()
        self.toolbox_toggle_button = QPushButton("ToolBox")
        self.toolbox_toggle_button.setCheckable(True)
        self.toolbox_toggle_button.setChecked(True)
        self.toolbox_toggle_button.setFixedHeight(self._toolbar_button_height)
        self.toolbox_panel = QWidget()
        toolbox_layout = QHBoxLayout(self.toolbox_panel)
        toolbox_layout.setContentsMargins(6, 6, 6, 6)
        toolbox_layout.setSpacing(6)
        self.circle_tool_button = QPushButton("円")
        self.circle_tool_button.setCheckable(True)
        self.circle_tool_button.setFixedHeight(28)
        self.circle_tool_button.setStyleSheet(
            f"""
            QPushButton {{
                padding: 0px 10px;
                background: {circle_button_bg};
                color: {circle_button_fg};
            }}
            QPushButton:checked {{
                background: {circle_button_active_bg};
                color: {circle_button_active_fg};
            }}
            """
        )
        toolbox_layout.addWidget(self.circle_tool_button)
        toolbox_layout.addStretch(1)
        left_layout.addWidget(self.toolbox_toggle_button)
        left_layout.addWidget(self.toolbox_panel)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.point_table = PointTableWidget(0, 3)
        self.point_table.setHorizontalHeaderLabels(["#", "X", "Y"])
        self.point_table.verticalHeader().setVisible(False)
        self.point_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.point_table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.point_table.setColumnWidth(0, 28)
        self.point_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.point_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.point_table.setMinimumWidth(140)
        right_layout.addWidget(self.point_table)

        buttons = QVBoxLayout()
        buttons.setSpacing(4)
        self.reset_button = QPushButton("Reset")
        self.save_history_button = QPushButton("履歴に保存")
        self.show_history_button = QPushButton("履歴を表示")
        self.reset_button.setFixedHeight(self._toolbar_button_height)
        self.save_history_button.setFixedHeight(self._toolbar_button_height)
        self.show_history_button.setFixedHeight(self._toolbar_button_height)
        buttons.addWidget(self.reset_button)
        history_buttons = QHBoxLayout()
        history_buttons.setSpacing(4)
        history_buttons.addWidget(self.save_history_button)
        history_buttons.addWidget(self.show_history_button)
        buttons.addLayout(history_buttons)
        right_layout.addLayout(buttons)

        splitter.addWidget(right)
        right.setMinimumWidth(170)
        splitter.setSizes([620, 280])

        footer = QHBoxLayout()
        self.cursor_label = QLabel("Cursor: x=0.00%, y=0.00%")
        cursor_metrics = QFontMetrics(self.cursor_label.font())
        cursor_width = max(
            cursor_metrics.horizontalAdvance("Cursor: x=100.00%, y=100.00%"),
            cursor_metrics.horizontalAdvance("Cursor: x=9999.0px, y=9999.0px"),
        )
        self.cursor_label.setFixedWidth(cursor_width + 8)
        footer.addWidget(self.cursor_label)

        self.code_label = CodeLineEdit(self._on_code_clicked, self._on_code_wheel)
        self.code_label.setReadOnly(True)
        self.code_label.setFrame(False)
        self.code_label.setFixedHeight(30)
        self.code_label.setText(self._code_full_text)
        self.code_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.code_label.setStyleSheet("padding: 0px 4px; background: transparent; border: none;")
        self.code_label.setToolTip(self._code_tooltip_text)
        footer.addWidget(self.code_label, 1)
        root_layout.addLayout(footer)

        self.setCentralWidget(body)
        self._update_code_label_layout(reset_scroll=True)

    def _connect_ui(self):
        self.mode_group.buttonClicked.connect(self._on_mode_clicked)
        self.size_h.valueChanged.connect(self._on_size_changed)
        self.size_w.valueChanged.connect(self._on_size_changed)
        self.unit_px.clicked.connect(self._on_size_changed)
        self.unit_percent.clicked.connect(self._on_size_changed)
        self.grid_input.valueChanged.connect(self._on_grid_changed)
        self.grid_check.toggled.connect(self._on_grid_changed)
        self.guide_check.toggled.connect(self._on_guide_changed)
        self.reset_button.clicked.connect(self._reset_state)
        self.save_history_button.clicked.connect(self._save_current_to_history)
        self.show_history_button.clicked.connect(self._show_history_dialog)
        self.point_table.rowReordered.connect(self._reorder_points)
        self.point_table.indexMenuRequested.connect(self._show_point_index_menu)
        self.point_table.dragPreviewChanged.connect(self._on_table_drag_preview_changed)
        self.point_table.dragStateChanged.connect(self._on_table_drag_state_changed)
        self.circle_tool_button.toggled.connect(self._on_circle_tool_toggled)
        self.toolbox_toggle_button.toggled.connect(self._on_toolbox_toggled)

    def _serialize_points(self, points: list[ClipPoint]) -> list[dict]:
        return [{"x": point.x, "y": point.y} for point in points]

    def _serialize_circles(self) -> list[dict]:
        return [
            {
                "center": {"x": circle.center.x, "y": circle.center.y},
                "radius": circle.radius,
                "divisions": circle.divisions,
                "snap_points": self._serialize_points(circle.snap_points),
            }
            for circle in self.circles
        ]

    def _restore_state(self):
        if not self.state_path or not self.state_path.exists():
            return
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return
        if not isinstance(state, dict):
            return

        points = state.get("points", [])
        circles = state.get("circles", [])
        self.points = [
            ClipPoint(float(point.get("x", 0.0)), float(point.get("y", 0.0)))
            for point in points
            if isinstance(point, dict)
        ]
        restored_circles: list[CircleGuide] = []
        for circle in circles:
            if not isinstance(circle, dict):
                continue
            center = circle.get("center")
            if not isinstance(center, dict):
                continue
            snap_points = circle.get("snap_points", [])
            restored_circles.append(
                CircleGuide(
                    center=ClipPoint(float(center.get("x", 0.0)), float(center.get("y", 0.0))),
                    radius=float(circle.get("radius", 0.0)),
                    divisions=int(circle.get("divisions", 0)),
                    snap_points=[
                        ClipPoint(float(point.get("x", 0.0)), float(point.get("y", 0.0)))
                        for point in snap_points
                        if isinstance(point, dict)
                    ],
                )
            )
        self.circles = restored_circles

        self.size_w.setValue(max(1, int(state.get("size_w", 100))))
        self.size_h.setValue(max(1, int(state.get("size_h", 100))))
        if state.get("unit") == "px":
            self.unit_px.setChecked(True)
        else:
            self.unit_percent.setChecked(True)
        self.grid_input.setValue(max(1, int(state.get("grid_value", 10))))
        self.grid_check.setChecked(bool(state.get("grid_enabled", True)))
        self.guide_check.setChecked(bool(state.get("guide_enabled", True)))
        mode = state.get("mode", MODE_INPUT)
        if mode == MODE_VIEW:
            self.mode_screen.setChecked(True)
            self.last_mode_button = self.mode_screen
        elif mode == MODE_CIRCLE:
            self.mode_circle.setChecked(True)
            self.last_mode_button = self.mode_circle
            self.circle_tool_button.setChecked(True)
        else:
            self.mode_input.setChecked(True)
            self.last_mode_button = self.mode_input
            self.circle_tool_button.setChecked(False)

    def _save_state(self):
        if not self.state_path:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "points": self._serialize_points(self.points),
            "circles": self._serialize_circles(),
            "mode": MODE_CIRCLE if self.circle_tool_button.isChecked() else MODE_INPUT,
            "size_w": self.size_w.value(),
            "size_h": self.size_h.value(),
            "unit": "px" if self.unit_px.isChecked() else SIZE_TYPE_PERCENT,
            "grid_value": self.grid_input.value(),
            "grid_enabled": self.grid_check.isChecked(),
            "guide_enabled": self.guide_check.isChecked(),
        }
        self.state_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _on_mode_clicked(self, btn):
        self.mode_circle.setChecked(btn is self.mode_circle)
        self.canvas.update()
        self._save_state()

    def _on_size_changed(self, *_):
        self.canvas.update()
        self._refresh_views()
        self._save_state()

    def _on_grid_changed(self, *_):
        self.canvas.update()
        self._refresh_views()
        self._save_state()

    def _on_guide_changed(self, *_):
        self.canvas.update()
        self._save_state()

    def _on_circle_tool_toggled(self, checked: bool):
        self.mode_circle.setChecked(checked)
        if not checked:
            self.mode_input.setChecked(True)
        self.canvas.update()
        self._save_state()

    def _on_toolbox_toggled(self, checked: bool):
        self.toolbox_panel.setVisible(checked)
        self.toolbox_toggle_button.setText("ToolBox" if checked else "ToolBox ▸")

    def _effective_mode(self) -> str:
        if self.ctrl_pressed:
            return MODE_VIEW
        return MODE_CIRCLE if self.circle_tool_button.isChecked() else MODE_INPUT

    def _get_size(self) -> tuple[float, float, str]:
        unit = "px" if self.unit_px.isChecked() else SIZE_TYPE_PERCENT
        return float(self.size_w.value()), float(self.size_h.value()), unit

    def _get_grid(self) -> tuple[bool, int]:
        return self.grid_check.isChecked(), max(1, self.grid_input.value())

    def _get_snap_points(self) -> list[ClipPoint]:
        points: list[ClipPoint] = []
        for circle in self.circles:
            points.extend(circle.snap_points)
        return points

    def _on_cursor_changed(self, raw: ClipPoint, snapped: ClipPoint):
        point = snapped if self._get_grid()[0] else raw
        out_x, out_y = self._to_output(point)
        self.cursor_label.setText(f"Cursor: x={out_x}, y={out_y}")

    def _format_measure(self, value: float, suffix: str, digits: int) -> str:
        rounded = round(value, digits)
        if float(rounded).is_integer():
            return f"{int(rounded)}{suffix}"
        text = f"{rounded:.{digits}f}".rstrip("0").rstrip(".")
        return f"{text}{suffix}"

    def _to_output(self, point: ClipPoint) -> tuple[str, str]:
        width, height, unit = self._get_size()
        if unit == SIZE_TYPE_PERCENT:
            return self._format_measure(point.x * 100, "%", 2), self._format_measure(point.y * 100, "%", 2)
        return self._format_measure(point.x * width, "px", 1), self._format_measure(point.y * height, "px", 1)

    def _to_table_output(self, point: ClipPoint) -> tuple[str, str]:
        return self._to_output(point)

    def _table_to_point(self, x_text: str, y_text: str) -> ClipPoint | None:
        x_text = x_text.replace("px", "").replace("%", "").strip()
        y_text = y_text.replace("px", "").replace("%", "").strip()
        try:
            xv = float(x_text)
            yv = float(y_text)
        except ValueError:
            return None
        w, h, unit = self._get_size()
        if unit == SIZE_TYPE_PERCENT:
            return ClipPoint(xv / 100.0, yv / 100.0)
        return ClipPoint(xv / max(w, 1.0), yv / max(h, 1.0))

    def _build_code(self) -> str:
        if not self.points:
            return "clip-path: polygon();"
        text = ", ".join(f"{x} {y}" for x, y in (self._to_output(p) for p in self.points))
        return f"clip-path: polygon({text});"

    def _refresh_views(self):
        self._table_syncing = True
        self.point_table.setRowCount(len(self.points))
        for row, point in enumerate(self.points):
            idx_item = QTableWidgetItem(str(row + 1))
            idx_item.setFlags(Qt.ItemIsEnabled)
            self.point_table.setItem(row, 0, idx_item)

            x_text, y_text = self._to_table_output(point)
            x_edit = SelectAllLineEdit(x_text)
            y_edit = SelectAllLineEdit(y_text)
            x_edit.editingFinished.connect(lambda r=row: self._on_row_edit_finished(r))
            y_edit.editingFinished.connect(lambda r=row: self._on_row_edit_finished(r))
            self.point_table.setCellWidget(row, 1, x_edit)
            self.point_table.setCellWidget(row, 2, y_edit)

        self._table_syncing = False
        self._fit_point_table_columns()
        self._apply_point_table_drag_feedback()

        text = self._build_code()
        self.copy_feedback_base_text = text
        self._code_full_text = text
        self.code_label.setStyleSheet("padding: 0px 4px; background: transparent; border: none;")
        self._update_code_label_layout(reset_scroll=True)
        self._save_state()

    def _fit_point_table_columns(self):
        total = max(self.point_table.viewport().width(), 120)
        index_w = 28
        rem = max(total - index_w, 40)
        each = rem // 2
        self.point_table.setColumnWidth(0, index_w)
        self.point_table.setColumnWidth(1, each)
        self.point_table.setColumnWidth(2, rem - each)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_point_table_columns()
        self._update_code_label_layout()

    def _code_max_scroll_offset(self, text: str, available_width: int, font_metrics: QFontMetrics) -> int:
        ellipsis = "..."
        if font_metrics.horizontalAdvance(text) <= available_width:
            return 0
        for offset in range(len(text)):
            prefix = ellipsis if offset > 0 else ""
            candidate = f"{prefix}{text[offset:]}"
            if font_metrics.horizontalAdvance(candidate) <= available_width:
                return offset
        return max(0, len(text) - 1)

    def _code_display_text(self, text: str, offset: int, available_width: int, font_metrics: QFontMetrics) -> tuple[str, bool]:
        prefix = "..." if offset > 0 else ""
        visible = text[offset:]
        has_tail = False
        while visible and font_metrics.horizontalAdvance(f"{prefix}{visible}") > available_width:
            visible = visible[:-1]
            has_tail = True
        if not visible:
            visible = text[min(offset, len(text) - 1)]
            has_tail = offset < len(text) - 1
        suffix = "..." if has_tail else ""
        display_text = f"{prefix}{visible}{suffix}"
        while display_text and font_metrics.horizontalAdvance(display_text) > available_width:
            if has_tail and len(visible) > 1:
                visible = visible[:-1]
                display_text = f"{prefix}{visible}..."
                continue
            display_text = font_metrics.elidedText(display_text, Qt.ElideRight, available_width)
            break
        return display_text, has_tail

    def _update_code_label_layout(self, reset_scroll: bool = False):
        text = self._code_full_text
        metrics = self.code_label.fontMetrics()
        available_width = max(1, self.code_label.width() - 8)
        if reset_scroll:
            self._code_scroll_offset = 0
        if metrics.horizontalAdvance(text) <= available_width:
            self.code_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.code_label.setText(text)
            self.code_label.setCursorPosition(len(text))
            self._code_scroll_offset = 0
            return

        self.code_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        max_offset = self._code_max_scroll_offset(text, available_width, metrics)
        self._code_scroll_offset = max(0, min(self._code_scroll_offset, max_offset))
        display_text, _ = self._code_display_text(text, self._code_scroll_offset, available_width, metrics)
        self.code_label.setText(display_text)
        self.code_label.setCursorPosition(0)

    def _on_code_wheel(self, event: QWheelEvent):
        if not self._code_full_text:
            event.ignore()
            return
        metrics = self.code_label.fontMetrics()
        available_width = max(1, self.code_label.width() - 8)
        if metrics.horizontalAdvance(self._code_full_text) <= available_width:
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        step = max(1, (abs(delta) // 120) * 3)
        direction = -1 if delta > 0 else 1
        max_offset = self._code_max_scroll_offset(self._code_full_text, available_width, metrics)
        self._code_scroll_offset = max(0, min(max_offset, self._code_scroll_offset + (direction * step)))
        self._update_code_label_layout()
        event.accept()

    def _focus_point_x_editor(self, row: int):
        if not (0 <= row < len(self.points)):
            return
        x_edit = self.point_table.cellWidget(row, 1)
        if not isinstance(x_edit, QLineEdit):
            return
        self.point_table.setCurrentCell(row, 1)
        self.point_table.scrollToItem(self.point_table.item(row, 0), QAbstractItemView.PositionAtCenter)
        x_edit.setFocus(Qt.OtherFocusReason)
        x_edit.selectAll()

    def _on_table_drag_preview_changed(self, source_row: int, target_row: int):
        self._drag_source_row = source_row
        self._drag_target_row = target_row
        self._apply_point_table_drag_feedback()

    def _on_table_drag_state_changed(self, active: bool):
        if not active:
            self._drag_source_row = -1
            self._drag_target_row = -1
        self._apply_point_table_drag_feedback()

    def _apply_point_table_drag_feedback(self):
        for row in range(self.point_table.rowCount()):
            item = self.point_table.item(row, 0)
            is_source = row == self._drag_source_row
            is_target = row == self._drag_target_row
            if item is not None:
                if is_source:
                    item.setBackground(QColor("#364153"))
                    item.setForeground(QColor("#ffffff"))
                elif is_target:
                    item.setBackground(QColor("#26303f"))
                    item.setForeground(QColor("#ffffff"))
                else:
                    item.setBackground(QColor(Qt.transparent))
                    item.setForeground(QColor(self.palette().color(QPalette.Text)))
            for column in (1, 2):
                editor = self.point_table.cellWidget(row, column)
                if not isinstance(editor, QLineEdit):
                    continue
                if is_source:
                    editor.setStyleSheet("padding: 0px 4px; background-color: #2b3445; border: 1px solid #7aa2f7;")
                elif is_target:
                    editor.setStyleSheet("padding: 0px 4px; background-color: #1f2836; border-top: 2px solid #e0af68;")
                else:
                    editor.setStyleSheet("padding: 0px 4px;")

    def _reorder_points(self, source_row: int, target_row: int):
        if not (0 <= source_row < len(self.points) and 0 <= target_row < len(self.points)):
            return
        self._push_undo_state()
        point = self.points.pop(source_row)
        self.points.insert(target_row, point)
        self._refresh_views()
        self.canvas.update()
        self._focus_point_x_editor(target_row)

    def _insert_point(self, index: int):
        insert_at = max(0, min(index, len(self.points)))
        self._push_undo_state()
        self.points.insert(insert_at, ClipPoint(0.0, 0.0))
        self._refresh_views()
        self.canvas.update()
        self._focus_point_x_editor(insert_at)

    def _remove_point(self, row: int):
        if not (0 <= row < len(self.points)):
            return
        self._push_undo_state()
        self.points.pop(row)
        self._refresh_views()
        self.canvas.update()

    def _show_point_index_menu(self, row: int, global_pos: QPoint):
        if not (0 <= row < len(self.points)):
            return
        menu = QMenu(self.point_table)
        insert_before_action = menu.addAction("前に挿入")
        insert_after_action = menu.addAction("後ろに挿入")
        remove_action = menu.addAction("この点を削除")
        action = menu.exec(global_pos)
        if action == insert_before_action:
            self._insert_point(row)
        elif action == insert_after_action:
            self._insert_point(row + 1)
        elif action == remove_action:
            self._remove_point(row)

    def _clone_points(self) -> list[ClipPoint]:
        return [ClipPoint(p.x, p.y) for p in self.points]

    def _copy_circles(self, circles: list[CircleGuide]) -> list[CircleGuide]:
        return [
            CircleGuide(
                center=ClipPoint(c.center.x, c.center.y),
                radius=c.radius,
                divisions=c.divisions,
                snap_points=[ClipPoint(p.x, p.y) for p in c.snap_points],
            )
            for c in circles
        ]

    def _push_undo_state(self):
        self.undo_stack.append((self._clone_points(), self._copy_circles(self.circles)))
        self.redo_stack.clear()

    def _apply_state(self, points: list[ClipPoint], circles: list[CircleGuide]):
        self.points = [ClipPoint(p.x, p.y) for p in points]
        self.circles = self._copy_circles(circles)
        self._refresh_views()
        self.canvas.update()
        self._save_state()

    def _undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append((self._clone_points(), self._copy_circles(self.circles)))
        points, circles = self.undo_stack.pop()
        self._apply_state(points, circles)

    def _redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append((self._clone_points(), self._copy_circles(self.circles)))
        points, circles = self.redo_stack.pop()
        self._apply_state(points, circles)

    def _load_history_entries(self) -> list[dict]:
        if not self.history_path or not self.history_path.exists():
            return []
        try:
            loaded = json.loads(self.history_path.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError:
            return []
        if not isinstance(loaded, list):
            return []
        entries: list[dict] = []
        for item in loaded:
            if isinstance(item, str):
                entries.append({"code": item})
                continue
            if isinstance(item, dict) and isinstance(item.get("code"), str):
                normalized = {"code": item["code"]}
                size = item.get("size")
                if isinstance(size, dict):
                    normalized["size"] = {
                        "w": size.get("w"),
                        "h": size.get("h"),
                        "unit": size.get("unit"),
                    }
                entries.append(normalized)
        return entries

    def _save_history_entry(self, code: str):
        if not self.history_path:
            return
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        w, h, unit = self._get_size()
        entry = {"code": code, "size": {"w": w, "h": h, "unit": unit}}
        entries = self._load_history_entries()
        if entries and entries[0].get("code") == code and entries[0].get("size") == entry["size"]:
            return
        entries.insert(0, entry)
        self.history_path.write_text(json.dumps(entries[: self.MAX_HISTORY], ensure_ascii=False, indent=2), encoding="utf-8")

    def _flash_code_feedback(self, text: str, color: str, restore_delay_ms: int = 700):
        self._code_full_text = text
        self.code_label.setStyleSheet(f"padding: 0px 4px; color: {color}; background: transparent; border: none;")
        self.code_label.setText(text)
        self._update_code_label_layout(reset_scroll=True)

        def _restore():
            self._code_full_text = self.copy_feedback_base_text
            self.code_label.setStyleSheet("padding: 0px 4px; background: transparent; border: none;")
            self.code_label.setText(self.copy_feedback_base_text)
            self._update_code_label_layout(reset_scroll=True)

        QTimer.singleShot(restore_delay_ms, _restore)

    def _save_current_to_history(self):
        if len(self.points) <= 2:
            self._flash_code_feedback("3つ以上の点を設定してください", "#f7768e", 900)
            return
        self._save_history_entry(self._build_code())
        self._flash_code_feedback("saved to history", "#4ecdc4")

    def _on_code_clicked(self, _event):
        if len(self.points) <= 2:
            self._code_full_text = "3つ以上の点を配置してください"
            self.code_label.setStyleSheet("padding: 0px 4px; color: #f7768e; background: transparent; border: none;")
            self.code_label.setText("3つ以上の点を配置してください")
            self._update_code_label_layout(reset_scroll=True)

            def _restore_error():
                self._code_full_text = self.copy_feedback_base_text
                self.code_label.setStyleSheet("padding: 0px 4px; background: transparent; border: none;")
                self.code_label.setText(self.copy_feedback_base_text)
                self._update_code_label_layout(reset_scroll=True)

            QTimer.singleShot(900, _restore_error)
            return

        code = self._build_code()
        QApplication.clipboard().setText(code)
        self._save_history_entry(code)
        self._code_full_text = "copy and saved"
        self.code_label.setStyleSheet("padding: 0px 4px; color: #4ecdc4; background: transparent; border: none;")
        self.code_label.setText("copy and saved")
        self._update_code_label_layout(reset_scroll=True)

        def _restore():
            self._code_full_text = self.copy_feedback_base_text
            self.code_label.setStyleSheet("padding: 0px 4px; background: transparent; border: none;")
            self.code_label.setText(self.copy_feedback_base_text)
            self._update_code_label_layout(reset_scroll=True)

        QTimer.singleShot(700, _restore)

    def _on_row_edit_finished(self, row: int):
        if self._table_syncing or row >= len(self.points):
            return
        x_edit = self.point_table.cellWidget(row, 1)
        y_edit = self.point_table.cellWidget(row, 2)
        if not isinstance(x_edit, QLineEdit) or not isinstance(y_edit, QLineEdit):
            return
        point = self._table_to_point(x_edit.text(), y_edit.text())
        if point is None:
            return
        self._push_undo_state()
        self.points[row] = point
        self.canvas.update()
        self._refresh_views()

    def _on_circle_created(self, start: ClipPoint, end: ClipPoint):
        self._push_undo_state()
        cx = (start.x + end.x) / 2.0
        cy = (start.y + end.y) / 2.0
        radius = max((((end.x - start.x) ** 2 + (end.y - start.y) ** 2) ** 0.5) / 2.0, 1e-6)
        divisions, ok = QInputDialog.getInt(self, "円の分割", "分割数", 8, 3, 360, 1)
        if not ok:
            return
        start_angle = math.atan2(start.y - cy, start.x - cx)
        snaps: list[ClipPoint] = []
        for i in range(divisions):
            ang = start_angle + (2 * math.pi * i) / divisions
            snaps.append(ClipPoint(cx + math.cos(ang) * radius, cy + math.sin(ang) * radius))
        self.circles.append(CircleGuide(center=ClipPoint(cx, cy), radius=radius, divisions=divisions, snap_points=snaps))
        self._refresh_views()
        self.canvas.update()
        self._save_state()

    def _on_circle_removed(self, index: int):
        if 0 <= index < len(self.circles):
            self.circles.pop(index)
            self._save_state()

    def _reset_state(self):
        self.points = []
        self.circles = []
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.canvas.zoom = 1.0
        self.canvas.pan.setX(0.0)
        self.canvas.pan.setY(0.0)
        self._refresh_views()
        self.canvas.update()
        self._save_state()

    def _history_size_tuple(self, size_info: dict | None) -> tuple[float, float, str] | None:
        if not isinstance(size_info, dict):
            return None
        w = size_info.get("w")
        h = size_info.get("h")
        unit = size_info.get("unit")
        if not isinstance(w, (int, float)) or not isinstance(h, (int, float)) or not isinstance(unit, str):
            return None
        return float(w), float(h), unit

    def _parse_code_to_points(self, code: str, size_override: tuple[float, float, str] | None = None) -> list[ClipPoint] | None:
        if "polygon(" not in code:
            return None
        inside = code.split("polygon(", 1)[1].split(")", 1)[0]
        if not inside.strip():
            return []
        out: list[ClipPoint] = []
        w, h, unit = size_override or self._get_size()
        for pair in inside.split(","):
            vals = pair.strip().split()
            if len(vals) != 2:
                return None
            x_t, y_t = vals
            is_percent = x_t.endswith("%") or y_t.endswith("%")
            x = float(x_t.replace("%", "").replace("px", ""))
            y = float(y_t.replace("%", "").replace("px", ""))
            if is_percent:
                out.append(ClipPoint(x / 100.0, y / 100.0))
            else:
                out.append(ClipPoint(x / max(w, 1.0), y / max(h, 1.0)))
        return out

    def _make_shape_icon(self, code: str, size_info: dict | None = None, side: int = 96) -> QPixmap:
        pix = QPixmap(side, side)
        pix.fill(QColor("#1f2330"))
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#7aa2f7"), 2))
        points = self._parse_code_to_points(code, self._history_size_tuple(size_info)) or []
        if len(points) > 1:
            margin = 12
            draw_size = max(1, side - (margin * 2))
            mapped = [(margin + pt.x * draw_size, margin + pt.y * draw_size) for pt in points]
            for i in range(len(mapped) - 1):
                p.drawLine(int(mapped[i][0]), int(mapped[i][1]), int(mapped[i + 1][0]), int(mapped[i + 1][1]))
            if len(mapped) > 2:
                p.drawLine(int(mapped[-1][0]), int(mapped[-1][1]), int(mapped[0][0]), int(mapped[0][1]))
        p.end()
        return pix

    def _build_history_preview_lines(self, text: str, width: int, max_lines: int, font_metrics: QFontMetrics) -> list[str]:
        if width <= 0 or max_lines <= 0:
            return [text]
        layout = QTextLayout(text, self.font())
        layout.beginLayout()
        lines: list[str] = []
        while len(lines) < max_lines:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(width)
            start = int(line.textStart())
            length = int(line.textLength())
            part = text[start : start + length]
            has_more = start + length < len(text)
            if len(lines) == max_lines - 1 and has_more:
                part = part.rstrip()
                while part and font_metrics.horizontalAdvance(f"{part}...") > width:
                    part = part[:-1]
                lines.append(f"{part}..." if part else "...")
                break
            lines.append(part)
        layout.endLayout()
        return lines or [""]

    def _history_preview_height(self, font_metrics: QFontMetrics, line_count: int) -> int:
        return max(1, line_count) * font_metrics.lineSpacing()

    def _show_history_dialog(self):
        items = self._load_history_entries()
        if not items:
            QMessageBox.information(self, "履歴", "履歴がありません")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Clip-Path History")
        layout = QVBoxLayout(dlg)
        lst = QListWidget()
        lst.setContextMenuPolicy(Qt.CustomContextMenu)
        lst.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        lst.verticalScrollBar().setSingleStep(12)
        preview_size = QSize(96, 96)
        lst.setIconSize(preview_size)
        row_widgets: dict[int, HistoryPreviewWidget] = {}
        for entry in items:
            code = entry.get("code")
            if not isinstance(code, str):
                continue
            size_info = entry.get("size")
            size_text = "[size: current]"
            if isinstance(size_info, dict):
                w = size_info.get("w")
                h = size_info.get("h")
                unit = size_info.get("unit")
                if isinstance(w, (int, float)) and isinstance(h, (int, float)) and isinstance(unit, str):
                    size_text = f"[size: {int(w) if float(w).is_integer() else w}x{int(h) if float(h).is_integer() else h}{unit}]"
            item = QListWidgetItem()
            item.setData(Qt.UserRole, entry)
            lst.addItem(item)
            widget = HistoryPreviewWidget(self._make_shape_icon(code, size_info, preview_size.width()), size_text, code)
            row_widgets[id(item)] = widget
            lst.setItemWidget(item, widget)
        layout.addWidget(lst)

        def relayout_items():
            metrics = QFontMetrics(lst.font())
            code_width = max(120, lst.viewport().width() - preview_size.width() - 48)
            for i in range(lst.count()):
                item = lst.item(i)
                widget = row_widgets.get(id(item))
                if widget is None:
                    continue
                preview_lines = self._build_history_preview_lines(widget.base_code_text, code_width, 3, metrics)
                widget.set_text_width(code_width)
                widget.set_preview_lines(preview_lines)
                code_height = self._history_preview_height(metrics, widget.line_count())
                text_height = widget.size_label_height() + code_height + 8
                item.setSizeHint(QSize(lst.viewport().width(), max(preview_size.height(), text_height) + 16))

        def resize_event(event):
            QDialog.resizeEvent(dlg, event)
            relayout_items()

        dlg.resizeEvent = resize_event

        def restore_selected(it: QListWidgetItem):
            payload = it.data(Qt.UserRole)
            code = payload.get("code") if isinstance(payload, dict) else None
            if not isinstance(code, str):
                return
            QApplication.clipboard().setText(code)
            relayout_items()
            clicked_widget = row_widgets.get(id(it))
            if clicked_widget is not None:
                clicked_widget.set_feedback_text("copy and send")

                def _restore_feedback(widget: HistoryPreviewWidget = clicked_widget):
                    if widget in row_widgets.values():
                        relayout_items()

                QTimer.singleShot(900, _restore_feedback)
            parsed = self._parse_code_to_points(
                code,
                self._history_size_tuple(payload.get("size") if isinstance(payload, dict) else None),
            )
            if parsed is None:
                return
            self._push_undo_state()
            self.points = parsed
            self.circles = []
            if isinstance(payload, dict):
                size_info = payload.get("size")
                if isinstance(size_info, dict):
                    w = size_info.get("w")
                    h = size_info.get("h")
                    unit = size_info.get("unit")
                    if isinstance(w, (int, float)) and isinstance(h, (int, float)):
                        self.size_w.setValue(max(1, int(round(w))))
                        self.size_h.setValue(max(1, int(round(h))))
                    if unit == SIZE_TYPE_PERCENT:
                        self.unit_percent.setChecked(True)
                    elif unit == "px":
                        self.unit_px.setChecked(True)
            self._refresh_views()
            self.canvas.update()
            self._save_state()

        def on_context_menu(pos: QPoint):
            item = lst.itemAt(pos)
            if item is None:
                return
            menu = QMenu(lst)
            delete_action = menu.addAction("履歴から削除")
            action = menu.exec(lst.viewport().mapToGlobal(pos))
            if action != delete_action:
                return
            scroll_value = lst.verticalScrollBar().value()
            row = lst.row(item)
            item_key = id(item)
            removed = lst.takeItem(row)
            row_widgets.pop(item_key, None)
            del removed
            lst.verticalScrollBar().setValue(scroll_value)
            remaining: list[dict] = []
            for i in range(lst.count()):
                payload = lst.item(i).data(Qt.UserRole)
                if isinstance(payload, dict) and isinstance(payload.get("code"), str):
                    remaining.append(payload)
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            self.history_path.write_text(json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8")

        lst.itemClicked.connect(restore_selected)
        lst.customContextMenuRequested.connect(on_context_menu)
        dlg.resize(self._history_dialog_width, self._history_dialog_height)

        def persist_history_dialog_size(_result: int):
            self._history_dialog_width = max(320, dlg.width())
            self._history_dialog_height = max(240, dlg.height())
            self._save_ui_state()

        dlg.finished.connect(persist_history_dialog_size)
        QTimer.singleShot(0, relayout_items)
        dlg.exec()

    def keyPressEvent(self, event: QKeyEvent):
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_Z:
            self._undo()
            return
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_Y:
            self._redo()
            return
        if event.key() == Qt.Key_Control and not self.ctrl_pressed:
            self.ctrl_pressed = True
            self.canvas.update()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = False
            self.canvas.update()
        super().keyReleaseEvent(event)

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        QTimer.singleShot(0, lambda: self._update_code_label_layout(reset_scroll=True))
