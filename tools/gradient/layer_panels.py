from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QBrush
from PySide6.QtWidgets import QAbstractItemView, QCheckBox, QFrame, QHeaderView, QHBoxLayout, QLabel, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from .color_utils import display_color_text, split_color_and_alpha
from .widgets import AlphaPatternLineEdit, alpha_pattern_text_color


class StopTableWidget(QTableWidget):
    stepRequested = Signal(int, int, int)
    rowReordered = Signal(int, int)
    colorDropped = Signal(int, str)

    def __init__(self, rows: int, columns: int, parent: QWidget | None = None):
        super().__init__(rows, columns, parent)
        self._drag_row: int | None = None
        self._drag_active = False
        self._press_pos = None
        self._drag_visual_row: int | None = None

    def keyPressEvent(self, event):
        item = self.currentItem()
        if item is not None and item.column() in (2, 3):
            if event.key() == Qt.Key_Up:
                self.stepRequested.emit(item.row(), item.column(), 1)
                event.accept()
                return
            if event.key() == Qt.Key_Down:
                self.stepRequested.emit(item.row(), item.column(), -1)
                event.accept()
                return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        if item and item.column() == 0 and event.button() == Qt.LeftButton:
            self._drag_row = item.row()
            self._press_pos = event.position().toPoint()
            self._drag_active = True
            self._drag_visual_row = item.row()
            self.viewport().update()
        else:
            self._drag_row = None
            self._press_pos = None
            self._drag_active = False
            self._drag_visual_row = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._drag_active
            and self._drag_row is not None
            and self._press_pos is not None
            and (event.position().toPoint() - self._press_pos).manhattanLength() >= 4
        ):
            self.viewport().setCursor(QCursor(Qt.ClosedHandCursor))
            self._drag_visual_row = self._drag_row
            self.viewport().update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_active and self._drag_row is not None and event.button() == Qt.LeftButton:
            target_item = self.itemAt(event.position().toPoint())
            target_row = target_item.row() if target_item else self.rowAt(event.position().toPoint().y())
            if target_row >= 0 and target_row != self._drag_row:
                self.rowReordered.emit(self._drag_row, target_row)
        self._drag_row = None
        self._press_pos = None
        self._drag_active = False
        self._drag_visual_row = None
        self.viewport().unsetCursor()
        self.viewport().update()
        super().mouseReleaseEvent(event)

    def viewportEvent(self, event):
        if event.type() in (QEvent.DragEnter, QEvent.DragMove, QEvent.Drop):
            mime = event.mimeData()
            if mime.hasFormat("application/x-gradient-color"):
                if event.type() == QEvent.DragEnter:
                    event.acceptProposedAction()
                    return True
                index = self.indexAt(event.position().toPoint())
                if index.isValid() and index.column() == 1:
                    if event.type() == QEvent.Drop:
                        color = bytes(mime.data("application/x-gradient-color")).decode("utf-8").strip()
                        if color:
                            self.colorDropped.emit(index.row(), color)
                    event.acceptProposedAction()
                    return True
        return super().viewportEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._drag_visual_row is None:
            return
        row_y = self.rowViewportPosition(self._drag_visual_row)
        row_h = self.rowHeight(self._drag_visual_row)
        if row_h <= 0:
            return
        from PySide6.QtGui import QPainter, QPen

        painter = QPainter(self.viewport())
        fill = QColor(78, 205, 196, 28)
        edge = QColor("#4ecdc4")
        painter.fillRect(0, row_y, self.viewport().width(), row_h, fill)
        painter.setPen(QPen(edge, 1))
        painter.drawRect(0, row_y, self.viewport().width() - 1, row_h - 1)


class BackgroundColorLineEdit(AlphaPatternLineEdit):
    colorDropped = Signal(str)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-gradient-color"):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-gradient-color"):
            color = bytes(event.mimeData().data("application/x-gradient-color")).decode("utf-8").strip()
            if color:
                self.colorDropped.emit(color)
                event.acceptProposedAction()
                return
        super().dropEvent(event)


def build_pending_inspector(kind: str) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(8, 8, 8, 8)
    note = QLabel("未実装")
    note.setWordWrap(True)
    frame = QFrame()
    frame.setFrameShape(QFrame.StyledPanel)
    frame_layout = QVBoxLayout(frame)
    frame_layout.setContentsMargins(10, 10, 10, 10)
    frame_layout.addWidget(note)
    frame_layout.addStretch(1)
    layout.addWidget(frame)
    return panel


def style_color_value_widget(widget: QWidget, color: str):
    if isinstance(widget, AlphaPatternLineEdit):
        widget.set_pattern_color(color)


def build_background_inspector(layer: dict, on_item_changed, on_context_requested, on_color_dropped) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(8, 8, 8, 8)
    frame = QFrame()
    frame.setFrameShape(QFrame.StyledPanel)
    frame_layout = QVBoxLayout(frame)
    frame_layout.setContentsMargins(10, 10, 10, 10)
    frame_layout.addWidget(QLabel("Color"))
    color_value = BackgroundColorLineEdit(str(layer.get("color", "#00000000")))
    color_value.setReadOnly(False)
    color_value.setAcceptDrops(True)
    color_value.editingFinished.connect(lambda item=layer, widget=color_value: on_item_changed(item, widget))
    color_value.setContextMenuPolicy(Qt.CustomContextMenu)
    color_value.customContextMenuRequested.connect(lambda pos, item=layer, widget=color_value: on_context_requested(item, widget, pos))
    color_value.colorDropped.connect(lambda color, item=layer: on_color_dropped(item, color))
    color_value.setText(display_color_text(str(layer.get("color", "#00000000"))))
    style_color_value_widget(color_value, str(layer.get("color", "#00000000")))
    frame_layout.addWidget(color_value)
    frame_layout.addStretch(1)
    layout.addWidget(frame)
    layer["_background_color_value"] = color_value
    return panel


def build_linear_inspector(layer: dict, format_stop_value, on_deg_changed, on_repeat_changed, on_item_changed, on_context_requested, on_step_requested, on_reorder_requested, on_add_requested, on_color_dropped) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    controls = QFrame()
    controls.setFrameShape(QFrame.StyledPanel)
    controls_layout = QHBoxLayout(controls)
    controls_layout.setContentsMargins(10, 10, 10, 10)
    controls_layout.setSpacing(8)
    controls_layout.addWidget(QLabel("deg"))
    deg_input = QSpinBox()
    deg_input.setRange(0, 360)
    deg_input.setValue(int(layer.get("deg", 90)))
    deg_input.setButtonSymbols(QSpinBox.NoButtons)
    deg_input.valueChanged.connect(lambda value, item=layer: on_deg_changed(item, value))
    controls_layout.addWidget(deg_input)
    controls_layout.addStretch(1)
    repeat_check = QCheckBox("repeat")
    repeat_check.setChecked(bool(layer.get("repeat", False)))
    repeat_check.toggled.connect(lambda checked, item=layer: on_repeat_changed(item, checked))
    controls_layout.addWidget(repeat_check)
    layout.addWidget(controls)

    table = StopTableWidget(0, 4)
    table.setHorizontalHeaderLabels(["", "color", "a", "stop"])
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
    table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
    table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
    table.setColumnWidth(0, 4)
    table.setColumnWidth(1, 56)
    table.setColumnWidth(2, 44)
    table.setColumnWidth(3, 48)
    table.setSelectionMode(QAbstractItemView.NoSelection)
    table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
    table.setAcceptDrops(True)
    table.viewport().setAcceptDrops(True)
    table.itemChanged.connect(lambda item, owner=layer, widget=table: on_item_changed(owner, widget, item))
    table.setContextMenuPolicy(Qt.CustomContextMenu)
    table.customContextMenuRequested.connect(lambda pos, owner=layer, widget=table: on_context_requested(owner, widget, pos))
    table.stepRequested.connect(lambda row, column, delta, owner=layer, widget=table: on_step_requested(owner, widget, row, column, delta))
    table.rowReordered.connect(lambda source, target, owner=layer: on_reorder_requested(owner, source, target))
    table.colorDropped.connect(lambda row, color, owner=layer: on_color_dropped(owner, row, color))
    populate_linear_stop_table(table, layer, format_stop_value)
    table.cellClicked.connect(lambda row, _column, owner=layer, widget=table: on_add_requested(owner) if row == widget.rowCount() - 1 else None)
    layout.addWidget(table, 1)
    layer["_stop_table"] = table
    return panel


def populate_linear_stop_table(table: QTableWidget, layer: dict, format_stop_value):
    stops = list(layer.get("stops") or [])
    table.blockSignals(True)
    table.clearSpans()
    table.setRowCount(len(stops) + 1)
    for row, stop in enumerate(stops):
        index_item = QTableWidgetItem("::")
        color_text, alpha_text = split_color_and_alpha(str(stop.get("color", "")))
        color_item = QTableWidgetItem(color_text)
        alpha_item = QTableWidgetItem(alpha_text)
        value_item = QTableWidgetItem(format_stop_value(layer, float(stop.get("position", 0.0))))
        muted = bool(stop.get("muted", False))
        index_item.setFlags(index_item.flags() & ~Qt.ItemIsEditable)
        if muted:
            muted_bg = QBrush(QColor("#343841"))
            muted_fg = QBrush(QColor("#8a93a5"))
            for item in (index_item, color_item, alpha_item, value_item):
                item.setBackground(muted_bg)
                item.setForeground(muted_fg)
        else:
            color_value = str(stop.get("color", "#ffffff"))
            color_item.setBackground(QColor(color_value))
            color_item.setForeground(QBrush(QColor(alpha_pattern_text_color(color_value))))
        table.setItem(row, 0, index_item)
        table.setItem(row, 1, color_item)
        table.setItem(row, 2, alpha_item)
        table.setItem(row, 3, value_item)
    add_row = len(stops)
    add_item = QTableWidgetItem("追加")
    add_item.setFlags((add_item.flags() & ~Qt.ItemIsEditable) & ~Qt.ItemIsSelectable)
    add_item.setTextAlignment(Qt.AlignCenter)
    table.setSpan(add_row, 0, 1, 4)
    table.setItem(add_row, 0, add_item)
    table.setRowHeight(add_row, 24)
    table.blockSignals(False)
