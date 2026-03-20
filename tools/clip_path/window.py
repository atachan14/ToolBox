from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QButtonGroup,
    QPushButton,
)
from PySide6.QtGui import QPalette

from .canvas import ClipPathCanvas
from .state import ClipPoint


class ClipPathWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.points: list[ClipPoint] = []

        self._build_ui()
        self._refresh_views()

    def _build_ui(self):
        self.setWindowTitle("Clip-Path")

        # =========================
        # root
        # =========================
        body = QWidget()
        root_layout = QVBoxLayout(body)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        # =========================
        # toolbar
        # =========================
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)

        # --- スタイル分離 ---
        
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

        # =========================
        # Mode
        # =========================
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

        mode_layout.addWidget(self.mode_input)
        mode_layout.addWidget(self.mode_screen)
        mode_layout.addWidget(self.mode_circle)

        # =========================
        # Size
        # =========================
        size_box = QWidget()
        size_box.setObjectName("size_box")

        size_layout = QHBoxLayout(size_box)
        size_layout.setContentsMargins(6, 2, 6, 2)
        size_layout.setSpacing(4)

        # --- H ---
        h_label = QLabel("h:")
        self.size_h = QSpinBox()
        self.size_h.setRange(1, 9999)
        self.size_h.setValue(100)
        self.size_h.setButtonSymbols(QSpinBox.NoButtons)
        self.size_h.setFixedWidth(50)

        # --- W ---
        w_label = QLabel("w:")
        self.size_w = QSpinBox()
        self.size_w.setRange(1, 9999)
        self.size_w.setValue(100)
        self.size_w.setButtonSymbols(QSpinBox.NoButtons)
        self.size_w.setFixedWidth(50)

        # --- Unit ---
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

        # =========================
        # %時にdisableする処理
        # =========================
        def update_size_enabled():
            is_px = self.unit_px.isChecked()
            self.size_h.setEnabled(is_px)
            self.size_w.setEnabled(is_px)

        self.unit_px.clicked.connect(update_size_enabled)
        self.unit_percent.clicked.connect(update_size_enabled)

        # 初期反映
        update_size_enabled()

        # layout

        size_layout.addWidget(h_label)
        size_layout.addWidget(self.size_h)

        size_layout.addWidget(w_label)
        size_layout.addWidget(self.size_w)

        size_layout.addWidget(self.unit_px)
        size_layout.addWidget(QLabel("/"))
        size_layout.addWidget(self.unit_percent)

        # =========================
        # Grid
        # =========================
        grid_box = QWidget()
        grid_box.setObjectName("grid_box")
        grid_layout = QHBoxLayout(grid_box)
        grid_layout.setContentsMargins(6, 2, 6, 2)
        grid_layout.setSpacing(4)

        grid_label = QLabel("Grid:")

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

        self.grid_on.setChecked(True)

        self.grid_on.setStyleSheet(button_style)
        self.grid_off.setStyleSheet(button_style)

        grid_layout.addWidget(grid_label)
        grid_layout.addWidget(self.grid_input)
        grid_layout.addWidget(self.grid_on)
        grid_layout.addWidget(QLabel("/"))
        grid_layout.addWidget(self.grid_off)

        # =========================
        # 配置
        # =========================
        
        toolbar.setStyleSheet(container_style)
        toolbar_layout.addWidget(mode_box)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(size_box)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(grid_box)

        root_layout.addWidget(toolbar)

        # =========================
        # middle
        # =========================
        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter, stretch=1)

        self.canvas = ClipPathCanvas(
            points=self.points,
            on_points_changed=self._refresh_views,
            on_cursor_changed=self._on_cursor_changed,
            snap_enabled=lambda: self.grid_on.isChecked(),
            snap_step=self.grid_input.value,
        )
        splitter.addWidget(self.canvas)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.point_table = QTableWidget(0, 3)
        self.point_table.setHorizontalHeaderLabels(["#", "X", "Y"])
        right_layout.addWidget(self.point_table)


        splitter.addWidget(right_panel)
        splitter.setSizes([600, 260])

        # =========================
        # footer
        # =========================
        footer = QHBoxLayout()

        self.cursor_label = QLabel("Cursor: x=0.0, y=0.0")
        footer.addWidget(self.cursor_label)

        footer.addStretch()

        self.code_label = QLabel("Code: clip-path: polygon();")
        footer.addWidget(self.code_label)

        root_layout.addLayout(footer)

        # =========================
        # set
        # =========================
        self.setCentralWidget(body)
    
    def _on_cursor_changed(self, x: float, y: float):
        self.cursor_label.setText(f"Cursor: x={x:.1f}, y={y:.1f}")

    def _format_value(self, value: float) -> str:
        unit = self.unit_combo.currentText()

        if unit == "px":
            return f"{value:.1f}px"

        base = self.base_value.value()
        percent = (value / base) * 100

        return f"{percent:.2f}%"

    def _build_code(self) -> str:
        if not self.points:
            return "clip-path: polygon();"

        point_text = ", ".join(
            f"{self._format_value(point.x)} {self._format_value(point.y)}"
            for point in self.points
        )

        return f"clip-path: polygon({point_text});"

    def _refresh_views(self):
        pass