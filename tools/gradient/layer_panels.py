from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QBrush
from PySide6.QtWidgets import QAbstractItemView, QCheckBox, QComboBox, QFrame, QHeaderView, QHBoxLayout, QLabel, QLineEdit, QSpinBox, QStyledItemDelegate, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

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
        if item is not None and item.column() in (1, 2):
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
        if item and event.button() == Qt.LeftButton and item.row() < self.rowCount() - 1:
            self.setCurrentItem(item)
            self.setFocus()
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
                if index.isValid() and index.column() == 0:
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


class StepLineEdit(QLineEdit):
    stepRequested = Signal(int)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            self.stepRequested.emit(1)
            event.accept()
            return
        if event.key() == Qt.Key_Down:
            self.stepRequested.emit(-1)
            event.accept()
            return
        super().keyPressEvent(event)


class StopTableItemDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit) and index.column() in (1, 2):
            table = self.parent()
            if isinstance(table, StopTableWidget):
                step_editor = StepLineEdit(parent)
                step_editor.setFrame(editor.hasFrame())
                step_editor.setAlignment(editor.alignment())
                step_editor.stepRequested.connect(lambda delta, row=index.row(), column=index.column(), widget=table: widget.stepRequested.emit(row, column, delta))
                return step_editor
        return editor


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


DEGREE_PRESETS = [
    ("input", None),
    ("to top", 0),
    ("to top right", 45),
    ("to right", 90),
    ("to bottom right", 135),
    ("to bottom", 180),
    ("to bottom left", 225),
    ("to left", 270),
    ("to top left", 315),
]


def _preset_index_for_mode(mode: str) -> int:
    for index, (label, _preset_deg) in enumerate(DEGREE_PRESETS):
        if label == mode:
            return index
    return 0


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


def build_linear_inspector(layer: dict, format_stop_value, on_deg_changed, on_deg_mode_changed, on_repeat_changed, on_cell_clicked, on_item_changed, on_context_requested, on_step_requested, on_reorder_requested, on_add_requested, on_color_dropped, column_widths, on_column_resized) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    controls = QFrame()
    controls.setFrameShape(QFrame.StyledPanel)
    controls_layout = QVBoxLayout(controls)
    controls_layout.setContentsMargins(6, 6, 6, 6)
    controls_layout.setSpacing(4)

    repeat_row = QHBoxLayout()
    repeat_row.setContentsMargins(0, 0, 0, 0)
    repeat_row.setSpacing(4)
    repeat_check = QCheckBox("repeat")
    repeat_check.setChecked(bool(layer.get("repeat", False)))
    repeat_check.toggled.connect(lambda checked, item=layer: on_repeat_changed(item, checked))
    repeat_row.addWidget(repeat_check)
    repeat_row.addStretch(1)
    controls_layout.addLayout(repeat_row)

    deg_row = QHBoxLayout()
    deg_row.setContentsMargins(0, 0, 0, 0)
    deg_row.setSpacing(4)
    deg_row.addWidget(QLabel("deg"))
    deg_select = QComboBox()
    for label, preset_deg in DEGREE_PRESETS:
        deg_select.addItem(label, preset_deg)
    deg_select.setCurrentIndex(_preset_index_for_mode(str(layer.get("deg_mode", "input"))))
    deg_row.addWidget(deg_select, 1)
    deg_input = QSpinBox()
    deg_input.setRange(0, 360)
    deg_input.setValue(int(layer.get("deg", 90)))
    deg_input.setButtonSymbols(QSpinBox.NoButtons)
    deg_input.valueChanged.connect(lambda value, item=layer: on_deg_changed(item, value))
    deg_input.setEnabled(deg_select.currentData() is None)
    deg_row.addWidget(deg_input)
    controls_layout.addLayout(deg_row)

    def _on_deg_select_changed(_index: int, item=layer, combo=deg_select, spin=deg_input):
        preset_deg = combo.currentData()
        is_input = preset_deg is None
        spin.setEnabled(is_input)
        if not is_input:
            on_deg_mode_changed(item, str(combo.currentText()))
        else:
            on_deg_mode_changed(item, "input")

    deg_select.currentIndexChanged.connect(_on_deg_select_changed)
    layout.addWidget(controls)

    table = _build_stop_table(layer, format_stop_value, on_cell_clicked, on_item_changed, on_context_requested, on_step_requested, on_reorder_requested, on_add_requested, on_color_dropped, column_widths, on_column_resized)
    populate_linear_stop_table(table, layer, format_stop_value)
    layout.addWidget(table, 1)
    layer["_stop_table"] = table
    return panel


def build_radial_inspector(layer: dict, format_position_value, on_center_changed, on_center_step_requested, on_repeat_changed, on_cell_clicked, on_item_changed, on_context_requested, on_step_requested, on_reorder_requested, on_add_requested, on_color_dropped, column_widths, on_column_resized) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    controls = QFrame()
    controls.setFrameShape(QFrame.StyledPanel)
    controls_layout = QVBoxLayout(controls)
    controls_layout.setContentsMargins(6, 6, 6, 6)
    controls_layout.setSpacing(4)

    repeat_row = QHBoxLayout()
    repeat_row.setContentsMargins(0, 0, 0, 0)
    repeat_row.setSpacing(4)
    repeat_check = QCheckBox("repeat")
    repeat_check.setChecked(bool(layer.get("repeat", False)))
    repeat_check.toggled.connect(lambda checked, item=layer: on_repeat_changed(item, checked))
    repeat_row.addWidget(repeat_check)
    repeat_row.addStretch(1)
    controls_layout.addLayout(repeat_row)

    center_row = QHBoxLayout()
    center_row.setContentsMargins(0, 0, 0, 0)
    center_row.setSpacing(4)
    center_row.addWidget(QLabel("cx"))
    cx_input = StepLineEdit(format_position_value(layer, float(layer.get("center_x", 0.5)), axis="x"))
    center_row.addWidget(cx_input, 1)
    center_row.addWidget(QLabel("cy"))
    cy_input = StepLineEdit(format_position_value(layer, float(layer.get("center_y", 0.5)), axis="y"))
    center_row.addWidget(cy_input, 1)
    cx_input.editingFinished.connect(lambda item=layer, x_widget=cx_input, y_widget=cy_input: on_center_changed(item, x_widget, y_widget))
    cy_input.editingFinished.connect(lambda item=layer, x_widget=cx_input, y_widget=cy_input: on_center_changed(item, x_widget, y_widget))
    cx_input.stepRequested.connect(lambda delta, item=layer, x_widget=cx_input, y_widget=cy_input: on_center_step_requested(item, x_widget, y_widget, "x", delta))
    cy_input.stepRequested.connect(lambda delta, item=layer, x_widget=cx_input, y_widget=cy_input: on_center_step_requested(item, x_widget, y_widget, "y", delta))
    controls_layout.addLayout(center_row)

    layout.addWidget(controls)

    table = _build_stop_table(layer, lambda owner, position: format_position_value(owner, position, axis="radius"), on_cell_clicked, on_item_changed, on_context_requested, on_step_requested, on_reorder_requested, on_add_requested, on_color_dropped, column_widths, on_column_resized)
    populate_linear_stop_table(table, layer, lambda owner, position: format_position_value(owner, position, axis="radius"))
    layout.addWidget(table, 1)
    layer["_stop_table"] = table
    layer["_radial_cx_input"] = cx_input
    layer["_radial_cy_input"] = cy_input
    return panel


def _build_stop_table(layer: dict, format_stop_value, on_cell_clicked, on_item_changed, on_context_requested, on_step_requested, on_reorder_requested, on_add_requested, on_color_dropped, column_widths, on_column_resized) -> StopTableWidget:
    table = StopTableWidget(0, 3)
    table.setItemDelegate(StopTableItemDelegate(table))
    table.setHorizontalHeaderLabels(["color", "alpha", "stop"])
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
    table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
    table.horizontalHeader().setMinimumSectionSize(36)
    for index, width in enumerate(column_widths):
        table.setColumnWidth(index, width)
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
    table.horizontalHeader().sectionResized.connect(lambda section, _old, new, widget=table: on_column_resized(widget, section, new))

    def _on_cell_clicked(row: int, column: int, owner=layer, widget=table):
        if row == widget.rowCount() - 1:
            on_add_requested(owner)
            return
        item = widget.item(row, column)
        if item is not None:
            widget.setCurrentItem(item)
            widget.setFocus()
        on_cell_clicked(owner, widget, row, column)

    table.cellClicked.connect(_on_cell_clicked)
    return table


def populate_linear_stop_table(table: QTableWidget, layer: dict, format_stop_value):
    stops = list(layer.get("stops") or [])
    table.blockSignals(True)
    table.clearSpans()
    table.setRowCount(len(stops) + 1)
    for row, stop in enumerate(stops):
        color_text, alpha_text = split_color_and_alpha(str(stop.get("color", "")))
        color_item = QTableWidgetItem(color_text)
        alpha_item = QTableWidgetItem(alpha_text)
        value_item = QTableWidgetItem(format_stop_value(layer, float(stop.get("position", 0.0))))
        color_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        alpha_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        value_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        muted = bool(stop.get("muted", False))
        if muted:
            muted_bg = QBrush(QColor("#343841"))
            muted_fg = QBrush(QColor("#8a93a5"))
            for item in (color_item, alpha_item, value_item):
                item.setBackground(muted_bg)
                item.setForeground(muted_fg)
        else:
            color_value = str(stop.get("color", "#ffffff"))
            color_item.setBackground(QColor(color_value))
            color_item.setForeground(QBrush(QColor(alpha_pattern_text_color(color_value))))
        table.setItem(row, 0, color_item)
        table.setItem(row, 1, alpha_item)
        table.setItem(row, 2, value_item)
    add_row = len(stops)
    add_item = QTableWidgetItem("追加")
    add_item.setFlags((add_item.flags() & ~Qt.ItemIsEditable) & ~Qt.ItemIsSelectable)
    add_item.setTextAlignment(Qt.AlignCenter)
    table.setSpan(add_row, 0, 1, 3)
    table.setItem(add_row, 0, add_item)
    table.setRowHeight(add_row, 24)
    table.blockSignals(False)
