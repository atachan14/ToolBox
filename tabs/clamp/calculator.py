from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QFormLayout,
    QPushButton,
    QLabel,
    QApplication,
)
from PySide6.QtGui import QShortcut, QKeySequence
from .style import flash_text

class ClampCalculator(QWidget):

    def __init__(self, tool):
        super().__init__()
        self.tool = tool
        
        self.setup_ui()
        self.setup_signals()
        self.setup_shortcuts()

    def setup_ui(self):
        layout = QVBoxLayout()

        # 自由入力
        self.quick_input = QLineEdit()
        self.quick_input.setPlaceholderText("16 350 767 32")
        
        self.quick_input.setClearButtonEnabled(True)

        layout.addWidget(self.quick_input)

        # 個別入力
        form = QFormLayout()

        self.min_px = QLineEdit()
        self.max_px = QLineEdit()
        self.min_view = QLineEdit()
        self.max_view = QLineEdit()

        form.addRow("min px", self.min_px)
        form.addRow("min view", self.min_view)
        form.addRow("max view", self.max_view)
        form.addRow("max px", self.max_px)

        layout.addLayout(form)

        # calculateボタン
        self.calc_button = QPushButton("calculate")
        layout.addWidget(self.calc_button)

        # 結果
        self.result = QLabel("clamp(...)")
        layout.addWidget(self.result)

        self.setLayout(layout)
        
    def setup_signals(self):
        self.quick_input.returnPressed.connect(self.calculate)

        self.calc_button.clicked.connect(self.calculate)
        self.result.mousePressEvent = self.copy_result
        
    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self.clear_quick_input)
        
    def parse_quick_input(self):

        text = self.quick_input.text()

        if not text:
            return

        text = text.replace(",", " ",)
        text = text.replace("px", "")
        parts = text.split()
        
        if len(parts) != 4:
            self.result.setStyleSheet("")
            return

        min_px, min_view, max_view, max_px = parts

        self.min_px.setText(min_px)
        self.max_px.setText(max_px)
        self.min_view.setText(min_view)
        self.max_view.setText(max_view)
        
    def calculate(self):

        # 自由入力処理
        focus = QApplication.focusWidget()

        if focus == self.quick_input:
            self.parse_quick_input()

        try:
            min_px = float(self.min_px.text())
            max_px = float(self.max_px.text())
            min_view = float(self.min_view.text())
            max_view = float(self.max_view.text())
        except ValueError:
            self.show_error()
            return

        if min_view == max_view:
            self.show_error()
            return

        if min_view > max_view:
            min_view, max_view = max_view, min_view
            min_px, max_px = max_px, min_px

        slope = (max_px - min_px) / (max_view - min_view) * 100
        intercept = min_px - (slope * min_view / 100)

        low = min(min_px, max_px)
        high = max(min_px, max_px)

        sign = "+" if slope >= 0 else "-"
        slope_abs = abs(slope)
    
        clamp = f"clamp({low:g}px, calc({intercept:.4f}px {sign} {slope_abs:.4f}vw), {high:g}px)"


        self.result.setText(clamp)
        self.result.setStyleSheet("")
        flash_text(self.result)
        
        view_range = f"{int(min_view)}~{int(max_view)}"

        self.tool.history.add_history(view_range, clamp)

    def show_error(self):
        self.result.setText("error")    
        self.result.setStyleSheet("color:#ff6b6b;")

    def copy_result(self, event):
        text = self.result.text()
        if text == "clamp(...)":
            return

        QApplication.clipboard().setText(text)
    
    def clear_quick_input(self):
        self.quick_input.clear()
        self.quick_input.setFocus()
        
        