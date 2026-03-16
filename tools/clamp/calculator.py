from __future__ import annotations

from PySide6.QtCore import QTimer, Qt,QEvent
from PySide6.QtGui import QKeySequence, QShortcut,QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QLabel
)

from .logic import build_clamp


class ClampCalculator(QWidget):
    def __init__(self, tool):
        super().__init__()
        self.tool = tool
        self.last_edited = None
        self._current_result_text = "clamp(...)"

        self.setup_ui()
        self.setup_signals()
        self.setup_shortcuts()

    def setup_ui(self):
        layout = QVBoxLayout()

        # free input block
        self.free_box = QFrame()
        self.free_box.setProperty("state", "normal")
        free_layout = QVBoxLayout(self.free_box)
        free_layout.setContentsMargins(0, 0, 0, 0)

        self.free_input = QLineEdit()
        self.free_input.setPlaceholderText("16 350 767 32")
        self.free_input.setClearButtonEnabled(True)
        free_layout.addWidget(self.free_input)
        layout.addWidget(self.free_box)

        # form block
        self.form_box = QFrame()
        self.form_box.setProperty("state", "normal")
        form_layout = QFormLayout(self.form_box)
        form_layout.setContentsMargins(0, 0, 0, 0)

        self.min_px = QLineEdit()
        self.max_px = QLineEdit()
        self.min_view = QLineEdit()
        self.max_view = QLineEdit()

        form_layout.addRow("min px", self.min_px)
        form_layout.addRow("min view", self.min_view)
        form_layout.addRow("max view", self.max_view)
        form_layout.addRow("max px", self.max_px)
        layout.addWidget(self.form_box)

        # action buttons
        button_row = QHBoxLayout()
        self.calc_button = QPushButton("calculate")
        self.reset_button = QPushButton("reset")
        self.reset_button.setFlat(True)
        button_row.addWidget(self.calc_button)
        button_row.addWidget(self.reset_button)
        layout.addLayout(button_row)

        # 余白はここ
        layout.addStretch()
        
        # result button
        self.result_label = QLabel(self._current_result_text)
        self.result_label.setWordWrap(True)
        self.result_label.setProperty("state", "start")
        self.result_label.setCursor(Qt.PointingHandCursor)
 
        layout.addWidget(self.result_label)

        ## 余白はここ
        layout.addStretch()

        # reverse block
        self.reverse_box = QFrame()
        self.reverse_box.setProperty("state", "normal")
        reverse_layout = QVBoxLayout(self.reverse_box)
        reverse_layout.setContentsMargins(0, 0, 0, 0)

        self.reverse_input = QLineEdit()
        self.reverse_input.setPlaceholderText("reverse...")
        self.reverse_input.setClearButtonEnabled(True)
        reverse_layout.addWidget(self.reverse_input)
        layout.addWidget(self.reverse_box)

        self.setLayout(layout)

        self.setStyleSheet(
            """
            QFrame {
                border: 1px solid transparent;
                border-radius: 6px;
                background: transparent;
            }
            QFrame[state="active"] {
                border: 1px solid #4ecdc4;
                background: rgba(78, 205, 196, 0.12);
            }
            QLabel[state="error"] { color: #ff6b6b; }
            QLabel[state="copied"] { color: #4ecdc4; }
            """
        )

    def setup_signals(self):
        self.calc_button.clicked.connect(self.calc_exe)
        self.reset_button.clicked.connect(self.reset_all)
        self.result_label.mousePressEvent = lambda e: self.copy_result()

        self.free_input.installEventFilter(self)
        for w in (self.min_px, self.max_px, self.min_view, self.max_view):
            w.installEventFilter(self)
        self.reverse_input.installEventFilter(self)
        
    def eventFilter(self, obj, event):
        if event.type() == QEvent.FocusIn:
            if obj == self.free_input:
                self.set_last("free")
            elif obj in (self.min_px, self.max_px, self.min_view, self.max_view):
                self.set_last("form")
            elif obj == self.reverse_input:
                self.set_last("reverse")
        return super().eventFilter(obj, event)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Delete"), self).activated.connect(self.reset_all)
        QShortcut(QKeySequence(Qt.Key_Return), self).activated.connect(self.handle_enter)
        QShortcut(QKeySequence(Qt.Key_Enter), self).activated.connect(self.handle_enter)

    def set_last(self, name: str):
        self.last_edited = name

    def handle_enter(self):
        focus = self.focusWidget()
        if focus == self.free_input:
            self.free_exe()
        elif focus in (self.min_px, self.max_px, self.min_view, self.max_view):
            self.form_exe()
        elif focus == self.reverse_input:
            self.reverse_exe()
        elif focus == self.reset_button:
            self.reset_all()
        elif focus == self.result_label:
            self.copy_result()
        else:
            self.calc_exe()

    def calc_exe(self):
        if self.last_edited == "reverse":
            self.reverse_exe()
        elif self.last_edited == "form":
            self.form_exe()
        else:
            self.free_exe()

    def flash_box(self, box: QFrame):
        box.setProperty("state", "active")
        box.style().unpolish(box)
        box.style().polish(box)
        QTimer.singleShot(350, lambda: self._reset_box_state(box))

    def _reset_box_state(self, box: QFrame):
        box.setProperty("state", "normal")
        box.style().unpolish(box)
        box.style().polish(box)

    def free_exe(self):
        self.flash_box(self.free_box)
        text = self.free_input.text().strip()
        if not text:
            self.error_result("textが入力されてません")
            return

        normalized = (
            text.replace(",", " ")
            .replace("px", "")
            .replace("~", " ")
            .replace("〜", " ")
            .replace("　", " ")
        )
        parts = normalized.split()
        if len(parts) != 4:
            self.error_result("textの形式が正しくありません（例: 16 350 767 32）")
            return

        min_px, min_view, max_view, max_px = parts
        self.min_px.setText(min_px)
        self.max_px.setText(max_px)
        self.min_view.setText(min_view)
        self.max_view.setText(max_view)

        self.form_exe()

    def form_exe(self):
        self.flash_box(self.form_box)
        try:
            min_px = float(self.min_px.text())
            max_px = float(self.max_px.text())
            min_view = float(self.min_view.text())
            max_view = float(self.max_view.text())
        except ValueError:
            self.error_result("数値を入力してください")
            return

        ok, payload = build_clamp(min_px, max_px, min_view, max_view)
        if not ok:
            self.error_result(payload)
            return

        self.success_result(
            payload,
            min_px,
            min_view,
            max_view,
            max_px,
        )

    def reverse_exe(self):
        self.flash_box(self.reverse_box)
        original_text = self.reverse_input.text().strip()
        text = "".join(original_text.lower().split())
        
        if not text.startswith("clamp(") or not text.endswith(")"):
            self.error_result("error")
            return

        try:
            inner = text[6:-1]
            min_px_raw, calc_part, max_px_raw = inner.split(",")
            min_px = float(min_px_raw.replace("px", ""))
            max_px = float(max_px_raw.replace("px", ""))

            calc_inner = calc_part.replace("calc(", "").replace(")", "")
            if "+" in calc_inner:
                left, right = calc_inner.split("+", 1)
                sign = 1
            elif "-" in calc_inner:
                left, right = calc_inner.split("-", 1)
                sign = -1
            else:
                raise ValueError("missing +/- in calc")

            if "px" in left:
                px_part, vw_part = left, right
            else:
                px_part, vw_part = right, left

            base_px = float(px_part.replace("px", ""))
            vw = float(vw_part.replace("vw", "")) * sign
            if vw == 0:
                raise ValueError("vw cannot be zero")

            min_view = (min_px - base_px) / vw * 100
            max_view = (max_px - base_px) / vw * 100

            min_view = int(round(min_view))
            max_view = int(round(max_view))

            pairs = sorted([(min_view, min_px), (max_view, max_px)])
            (min_view, min_px), (max_view, max_px) = pairs
        except (ValueError, ZeroDivisionError):
            self.error_result("error")
            return

        self.min_px.setText(f"{min_px:g}")
        self.max_px.setText(f"{max_px:g}")
        self.min_view.setText(str(min_view))
        self.max_view.setText(str(max_view))

      
        self.success_result(
            original_text,
            min_px,
            min_view,
            max_view,
            max_px,
        )


    def run_from_history(self, entry):
        self.min_px.setText(str(entry.get("min_px", "")))
        self.min_view.setText(str(entry.get("min_view", "")))
        self.max_view.setText(str(entry.get("max_view", "")))
        self.max_px.setText(str(entry.get("max_px", "")))
        self.set_last("form")
        self.min_px.setFocus()

    def success_result(
        self,
        clamp: str,
        min_px=None,
        min_view=None,
        max_view=None,
        max_px=None,
    ):
        self._current_result_text = clamp
        self.result_label.setText(clamp)

        self.result_label.setProperty("state", "success")
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)

        self.copy_result()

        # history送信
        if None not in (min_px, min_view, max_view, max_px):
            self.tool.history.add_history(
                clamp,
                min_px,
                min_view,
                max_view,
                max_px,
            )

    def error_result(self, message: str):
        self._current_result_text = message
        self.result_label.setText(message)
        self.result_label.setProperty("state", "error")
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)

    def copy_result(self):
        if self.result_label.property("state") != "success":
            return

        QApplication.clipboard().setText(self._current_result_text)

        self.result_label.setProperty("state", "copied")
        self.result_label.setText("Copied!")
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)

        QTimer.singleShot(600, self.restore_result)

    def restore_result(self):
        self.result_label.setText(self._current_result_text)
        self.result_label.setProperty("state", "success")
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)

    def reset_all(self):
        self.free_input.clear()
        self.min_px.clear()
        self.max_px.clear()
        self.min_view.clear()
        self.max_view.clear()
        self.reverse_input.clear()

        self._current_result_text = "clamp(...)"
        self.result_label.setText(self._current_result_text)
        self.result_label.setProperty("state", "start")
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)

        for box in (self.free_box, self.form_box, self.reverse_box):
            self._reset_box_state(box)

        self.last_edited = None
        self.free_input.setFocus()