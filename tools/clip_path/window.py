from __future__ import annotations

import json
import math
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QIcon, QKeyEvent, QPainter, QPalette, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
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
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.flow_layout import FlowLayout
from .canvas import CanvasConfig, ClipPathCanvas
from .state import MODE_CIRCLE, MODE_INPUT, MODE_VIEW, SIZE_TYPE_PERCENT, CircleGuide, ClipPoint


class ClipPathWindow(QMainWindow):
    MAX_HISTORY = 100

    def __init__(self):
        super().__init__()
        self.points: list[ClipPoint] = []
        self.circles: list[CircleGuide] = []

        self.ctrl_pressed = False
        self.last_mode_button: QPushButton | None = None
        self.undo_stack: list[tuple[list[ClipPoint], list[CircleGuide]]] = []
        self.redo_stack: list[tuple[list[ClipPoint], list[CircleGuide]]] = []

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
        toolbar_layout = FlowLayout(toolbar, margin=0, spacing=3)

        border_color = self.palette().color(QPalette.Mid).name()
        toolbar.setStyleSheet(
            f"""
            #mode_box, #size_box, #grid_box {{
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
            """
        )

        mode_box = QWidget()
        mode_box.setObjectName("mode_box")
        mode_layout = QHBoxLayout(mode_box)
        mode_layout.setContentsMargins(4, 1, 4, 1)
        self.mode_input = QPushButton("入力")
        self.mode_screen = QPushButton("画面")
        self.mode_circle = QPushButton("円")
        for btn in (self.mode_input, self.mode_screen, self.mode_circle):
            btn.setCheckable(True)
            btn.setStyleSheet("padding: 0px 3px;")
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for btn in (self.mode_input, self.mode_screen, self.mode_circle):
            self.mode_group.addButton(btn)
            mode_layout.addWidget(btn)
        self.mode_input.setChecked(True)
        self.last_mode_button = self.mode_input

        size_box = QWidget()
        size_box.setObjectName("size_box")
        size_layout = QHBoxLayout(size_box)
        size_layout.setContentsMargins(4, 1, 4, 1)
        self.size_h = QSpinBox()
        self.size_w = QSpinBox()
        for spin in (self.size_h, self.size_w):
            spin.setRange(1, 9999)
            spin.setValue(100)
            spin.setButtonSymbols(QSpinBox.NoButtons)
            spin.setFixedWidth(46)
        self.unit_px = QPushButton("px")
        self.unit_percent = QPushButton("%")
        self.unit_px.setCheckable(True)
        self.unit_percent.setCheckable(True)
        self.unit_px.setStyleSheet("padding: 0px 3px;")
        self.unit_percent.setStyleSheet("padding: 0px 3px;")
        self.unit_group = QButtonGroup(self)
        self.unit_group.setExclusive(True)
        self.unit_group.addButton(self.unit_px)
        self.unit_group.addButton(self.unit_percent)
        self.unit_px.setChecked(True)
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
        grid_layout.setContentsMargins(4, 1, 4, 1)
        self.grid_input = QSpinBox()
        self.grid_input.setRange(1, 999)
        self.grid_input.setValue(10)
        self.grid_input.setButtonSymbols(QSpinBox.NoButtons)
        self.grid_input.setFixedWidth(46)
        self.grid_on = QPushButton("ON")
        self.grid_off = QPushButton("OFF")
        self.grid_on.setCheckable(True)
        self.grid_off.setCheckable(True)
        self.grid_on.setStyleSheet("padding: 0px 3px;")
        self.grid_off.setStyleSheet("padding: 0px 3px;")
        self.grid_group = QButtonGroup(self)
        self.grid_group.setExclusive(True)
        self.grid_group.addButton(self.grid_on)
        self.grid_group.addButton(self.grid_off)
        self.grid_off.setChecked(True)
        grid_layout.addWidget(QLabel("Grid:"))
        grid_layout.addWidget(self.grid_input)
        grid_layout.addWidget(self.grid_on)
        grid_layout.addWidget(QLabel("/"))
        grid_layout.addWidget(self.grid_off)

        toolbar_layout.addWidget(mode_box)
        toolbar_layout.addWidget(size_box)
        toolbar_layout.addWidget(grid_box)
        root_layout.addWidget(toolbar)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter, 1)

        self.canvas = ClipPathCanvas(
            CanvasConfig(
                mode_getter=self._effective_mode,
                points_getter=lambda: self.points,
                size_getter=self._get_size,
                grid_getter=self._get_grid,
                circles_getter=lambda: self.circles,
                snap_points_getter=self._get_snap_points,
                on_points_changed=self._refresh_views,
                on_cursor_changed=self._on_cursor_changed,
                on_push_history=self._push_undo_state,
                on_circle_created=self._on_circle_created,
                on_circle_removed=self._on_circle_removed,
            )
        )
        splitter.addWidget(self.canvas)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.point_table = QTableWidget(0, 3)
        self.point_table.setHorizontalHeaderLabels(["#", "X", "Y"])
        self.point_table.verticalHeader().setVisible(False)
        self.point_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.point_table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.point_table.setColumnWidth(0, 28)
        self.point_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.point_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.point_table.setMinimumWidth(140)
        right_layout.addWidget(self.point_table)

        buttons = QHBoxLayout()
        self.reset_button = QPushButton("Reset")
        self.show_history_button = QPushButton("履歴を表示")
        buttons.addWidget(self.reset_button)
        buttons.addWidget(self.show_history_button)
        right_layout.addLayout(buttons)

        splitter.addWidget(right)
        right.setMinimumWidth(170)
        splitter.setSizes([620, 280])

        footer = QHBoxLayout()
        self.cursor_label = QLabel("Cursor: x=0.00%, y=0.00%")
        footer.addWidget(self.cursor_label)

        self.code_area = QScrollArea()
        self.code_area.setFrameShape(QScrollArea.NoFrame)
        self.code_area.setWidgetResizable(False)
        self.code_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.code_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.code_area.setFixedHeight(30)
        self.code_label = QLabel("clip-path: polygon();")
        self.code_label.setWordWrap(False)
        self.code_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.code_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.code_label.setStyleSheet("padding: 4px;")
        self.code_area.setWidget(self.code_label)
        self.code_area.mousePressEvent = self._on_code_clicked
        self.code_label.mousePressEvent = self._on_code_clicked
        self.code_area.wheelEvent = self._on_code_wheel
        footer.addWidget(self.code_area, 1)
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
        self.grid_on.clicked.connect(self._on_grid_changed)
        self.grid_off.clicked.connect(self._on_grid_changed)
        self.reset_button.clicked.connect(self._reset_state)
        self.show_history_button.clicked.connect(self._show_history_dialog)

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
        return MODE_VIEW if self.mode_screen.isChecked() else MODE_CIRCLE

    def _get_size(self) -> tuple[float, float, str]:
        unit = "px" if self.unit_px.isChecked() else SIZE_TYPE_PERCENT
        return float(self.size_w.value()), float(self.size_h.value()), unit

    def _get_grid(self) -> tuple[bool, int]:
        return self.grid_on.isChecked(), max(1, self.grid_input.value())

    def _get_snap_points(self) -> list[ClipPoint]:
        points: list[ClipPoint] = []
        for circle in self.circles:
            points.extend(circle.snap_points)
        return points

    def _on_cursor_changed(self, raw: ClipPoint, snapped: ClipPoint):
        point = snapped if self._get_grid()[0] else raw
        out_x, out_y = self._to_output(point)
        self.cursor_label.setText(f"Cursor: x={out_x}, y={out_y}")

    def _to_output(self, point: ClipPoint) -> tuple[str, str]:
        width, height, unit = self._get_size()
        if unit == SIZE_TYPE_PERCENT:
            return f"{point.x * 100:.2f}%", f"{point.y * 100:.2f}%"
        return f"{point.x * width:.1f}px", f"{point.y * height:.1f}px"

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
            x_edit = QLineEdit(x_text)
            y_edit = QLineEdit(y_text)
            x_edit.editingFinished.connect(lambda r=row: self._on_row_edit_finished(r))
            y_edit.editingFinished.connect(lambda r=row: self._on_row_edit_finished(r))
            self.point_table.setCellWidget(row, 1, x_edit)
            self.point_table.setCellWidget(row, 2, y_edit)

        self._table_syncing = False
        self._fit_point_table_columns()

        text = self._build_code()
        self.copy_feedback_base_text = text
        self.code_label.setStyleSheet("padding: 4px;")
        self.code_label.setText(text)
        self._update_code_label_layout()

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

    def _update_code_label_layout(self, reset_scroll: bool = False):
        text_width = self.code_label.sizeHint().width()
        viewport_width = self.code_area.viewport().width()
        target_width = max(text_width, viewport_width)
        self.code_label.setFixedWidth(target_width)
        bar = self.code_area.horizontalScrollBar()
        if reset_scroll:
            bar.setValue(bar.maximum())

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

    def _save_history_entry(self, code: str):
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        entries: list[str] = []
        if self.history_path.exists():
            try:
                loaded = json.loads(self.history_path.read_text(encoding="utf-8") or "[]")
                if isinstance(loaded, list):
                    entries = [str(v) for v in loaded if isinstance(v, str)]
            except json.JSONDecodeError:
                entries = []
        if entries and entries[0] == code:
            return
        entries.insert(0, code)
        self.history_path.write_text(json.dumps(entries[: self.MAX_HISTORY], ensure_ascii=False, indent=2), encoding="utf-8")

    def _on_code_clicked(self, _event):
        if len(self.points) <= 2:
            self.code_label.setStyleSheet("padding: 4px; color: #f7768e;")
            self.code_label.setText("3つ以上の点を配置してください")
            self._update_code_label_layout(reset_scroll=True)

            def _restore_error():
                self.code_label.setStyleSheet("padding: 4px;")
                self.code_label.setText(self.copy_feedback_base_text)
                self._update_code_label_layout()

            QTimer.singleShot(900, _restore_error)
            return

        code = self._build_code()
        QApplication.clipboard().setText(code)
        self._save_history_entry(code)
        self.code_label.setStyleSheet("padding: 4px; color: #4ecdc4;")
        self.code_label.setText("copy and saved")
        self._update_code_label_layout(reset_scroll=True)

        def _restore():
            self.code_label.setStyleSheet("padding: 4px;")
            self.code_label.setText(self.copy_feedback_base_text)
            self._update_code_label_layout()

        QTimer.singleShot(700, _restore)

    def _on_code_wheel(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        bar = self.code_area.horizontalScrollBar()
        bar.setValue(bar.value() - int(delta / 4))
        event.accept()

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

    def _on_circle_removed(self, index: int):
        if 0 <= index < len(self.circles):
            self.circles.pop(index)

    def _reset_state(self):
        self.points = []
        self.circles = []
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.mode_input.setChecked(True)
        self.grid_off.setChecked(True)
        self.grid_input.setValue(10)
        self.unit_px.setChecked(True)
        self.size_w.setValue(100)
        self.size_h.setValue(100)
        self.canvas.zoom = 1.0
        self.canvas.pan.setX(0.0)
        self.canvas.pan.setY(0.0)
        self._refresh_views()
        self.canvas.update()

    def _parse_code_to_points(self, code: str) -> list[ClipPoint] | None:
        if "polygon(" not in code:
            return None
        inside = code.split("polygon(", 1)[1].split(")", 1)[0]
        if not inside.strip():
            return []
        out: list[ClipPoint] = []
        w, h, unit = self._get_size()
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

    def _make_shape_icon(self, code: str) -> QPixmap:
        pix = QPixmap(144, 96)
        pix.fill(QColor("#1f2330"))
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#7aa2f7"), 2))
        points = self._parse_code_to_points(code) or []
        if len(points) > 1:
            mapped = [(18 + pt.x * 108, 12 + pt.y * 72) for pt in points]
            for i in range(len(mapped) - 1):
                p.drawLine(int(mapped[i][0]), int(mapped[i][1]), int(mapped[i + 1][0]), int(mapped[i + 1][1]))
            if len(mapped) > 2:
                p.drawLine(int(mapped[-1][0]), int(mapped[-1][1]), int(mapped[0][0]), int(mapped[0][1]))
        p.end()
        return pix

    def _history_preview_text(self, code: str, max_chars: int = 220) -> str:
        text = code.replace(", ", ",\n")
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 1] + "…"

    def _show_history_dialog(self):
        if not self.history_path.exists():
            QMessageBox.information(self, "履歴", "履歴がありません")
            return
        try:
            items = json.loads(self.history_path.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError:
            items = []
        dlg = QDialog(self)
        dlg.setWindowTitle("Clip-Path History")
        layout = QVBoxLayout(dlg)
        lst = QListWidget()
        preview_size = QSize(144, 96)
        lst.setIconSize(preview_size)
        lst.setWordWrap(True)
        lst.setTextElideMode(Qt.ElideRight)
        lst.setContextMenuPolicy(Qt.CustomContextMenu)
        for code in items:
            if not isinstance(code, str):
                continue
            item = QListWidgetItem(self._history_preview_text(code))
            item.setIcon(QIcon(self._make_shape_icon(code)))
            item.setData(Qt.UserRole, code)
            item.setSizeHint(QSize(item.sizeHint().width(), preview_size.height() + 16))
            lst.addItem(item)
        layout.addWidget(lst)

        def restore_selected(it: QListWidgetItem):
            raw_code = it.data(Qt.UserRole)
            if not isinstance(raw_code, str):
                return
            parsed = self._parse_code_to_points(raw_code)
            if parsed is None:
                return
            self._push_undo_state()
            self.points = parsed
            self.circles = []
            self._refresh_views()
            self.canvas.update()

        def on_context_menu(pos: QPoint):
            item = lst.itemAt(pos)
            if item is None:
                return
            menu = QMenu(lst)
            delete_action = menu.addAction("履歴から削除")
            action = menu.exec(lst.viewport().mapToGlobal(pos))
            if action != delete_action:
                return
            row = lst.row(item)
            removed = lst.takeItem(row)
            del removed
            remaining: list[str] = []
            for i in range(lst.count()):
                code = lst.item(i).data(Qt.UserRole)
                if isinstance(code, str):
                    remaining.append(code)
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            self.history_path.write_text(json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8")

        lst.itemClicked.connect(restore_selected)
        lst.customContextMenuRequested.connect(on_context_menu)
        dlg.resize(620, 360)
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
