from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .logic import build_clamp, parse_value_text, resolve_view_unit


class ClampCalculator(QWidget):
    def __init__(self, tool):
        super().__init__()
        self.tool = tool
        self.last_edited = None
        self._current_result_text = "clamp(...)"
        self._result_unit = "px"
        self._view_unit = "vw"
        self._result_values = None

        self.setup_ui()
        self.setup_signals()
        self.setup_shortcuts()

    def setup_ui(self):
        layout = QVBoxLayout()

        self.form_box = QFrame()
        self.form_box.setProperty("state", "normal")
        form_layout = QFormLayout(self.form_box)
        form_layout.setContentsMargins(0, 0, 0, 0)

        self.min_px = QLineEdit()
        self.max_px = QLineEdit()
        self.min_view = QLineEdit()
        self.max_view = QLineEdit()

        form_layout.addRow("min value", self.min_px)
        form_layout.addRow("min view", self.min_view)
        form_layout.addRow("max view", self.max_view)
        form_layout.addRow("max value", self.max_px)
        layout.addWidget(self.form_box)

        button_row = QHBoxLayout()
        self.calc_button = QPushButton("calculate")
        self.reset_button = QPushButton("reset")
        self.reset_button.setFlat(True)
        button_row.addWidget(self.calc_button)
        button_row.addWidget(self.reset_button)
        layout.addLayout(button_row)

        layout.addStretch()

        result_row = QHBoxLayout()
        result_row.setContentsMargins(0, 0, 0, 0)
        result_row.setSpacing(8)

        self.result_label = QLabel(self._current_result_text)
        self.result_label.setWordWrap(True)
        self.result_label.setProperty("state", "start")
        self.result_label.setCursor(Qt.PointingHandCursor)

        self.unit_selector_frame = QFrame()
        self.unit_selector_frame.setObjectName("unitSelectorFrame")
        self.unit_selector_frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        selector_layout = QHBoxLayout(self.unit_selector_frame)
        selector_layout.setContentsMargins(0, 0, 0, 0)
        selector_layout.setSpacing(0)

        self.unit_toggle = QComboBox()
        self.unit_toggle.setObjectName("unitSelector")
        self.unit_toggle.setCursor(Qt.PointingHandCursor)
        self.unit_toggle.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.unit_toggle.setMinimumWidth(44)
        self.unit_toggle.addItem("", "")
        self.unit_toggle.addItem("px", "px")
        self.unit_toggle.addItem("%", "%")
        self.unit_toggle.addItem("rem", "rem")
        self.unit_toggle.setCurrentIndex(self.unit_toggle.findData(self._result_unit))

        self.unit_arrow = QLabel("")
        self.unit_arrow.setObjectName("unitSelectorArrow")
        self.unit_arrow.setAlignment(Qt.AlignCenter)
        self.unit_arrow.setFixedWidth(6)

        selector_layout.addWidget(self.unit_toggle)
        selector_layout.addWidget(self.unit_arrow)

        self.view_unit_selector_frame = QFrame()
        self.view_unit_selector_frame.setObjectName("unitSelectorFrame")
        self.view_unit_selector_frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        view_selector_layout = QHBoxLayout(self.view_unit_selector_frame)
        view_selector_layout.setContentsMargins(0, 0, 0, 0)
        view_selector_layout.setSpacing(0)

        self.view_unit_toggle = QComboBox()
        self.view_unit_toggle.setObjectName("unitSelector")
        self.view_unit_toggle.setCursor(Qt.PointingHandCursor)
        self.view_unit_toggle.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.view_unit_toggle.setMinimumWidth(44)
        self.view_unit_toggle.addItem("", "")
        self.view_unit_toggle.addItem("vw", "vw")
        self.view_unit_toggle.addItem("vh", "vh")
        self.view_unit_toggle.setCurrentIndex(self.view_unit_toggle.findData(self._view_unit))

        self.view_unit_arrow = QLabel("")
        self.view_unit_arrow.setObjectName("unitSelectorArrow")
        self.view_unit_arrow.setAlignment(Qt.AlignCenter)
        self.view_unit_arrow.setFixedWidth(6)

        view_selector_layout.addWidget(self.view_unit_toggle)
        view_selector_layout.addWidget(self.view_unit_arrow)

        result_row.addWidget(self.result_label, 1)
        result_row.addWidget(self.unit_selector_frame, 0, Qt.AlignTop)
        result_row.addWidget(self.view_unit_selector_frame, 0, Qt.AlignTop)
        layout.addLayout(result_row)

        layout.addStretch()

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
            QFrame#unitSelectorFrame {
                background-color: #333333;
                color: #dddddd;
                border: 1px solid #555555;
                border-radius: 4px;
                min-height: 22px;
            }
            QFrame#unitSelectorFrame:hover {
                background-color: #444444;
            }
            QComboBox#unitSelector {
                background: transparent;
                color: #dddddd;
                border: none;
                padding: 2px 4px 2px 8px;
                min-height: 22px;
            }
            QComboBox#unitSelector::drop-down {
                width: 0px;
                border: none;
                background: transparent;
            }
            QComboBox#unitSelector::down-arrow {
                image: none;
            }
            QComboBox#unitSelector QAbstractItemView {
                background-color: #333333;
                color: #dddddd;
                border: 1px solid #555555;
                selection-background-color: #444444;
                selection-color: #ffffff;
            }
            QLabel#unitSelectorArrow {
                color: #dddddd;
                background: transparent;
                border: none;
                padding-right: 0px;
            }
            QLabel[state="error"] { color: #ff6b6b; }
            QLabel[state="copied"] { color: #4ecdc4; }
            """
        )

    def setup_signals(self):
        self.calc_button.clicked.connect(self.calc_exe)
        self.reset_button.clicked.connect(self.reset_all)
        self.result_label.mousePressEvent = lambda e: self.copy_result()
        self.unit_toggle.currentIndexChanged.connect(self.toggle_result_unit)
        self.view_unit_toggle.currentIndexChanged.connect(self.toggle_view_unit)

        for widget in (self.min_px, self.max_px, self.min_view, self.max_view):
            widget.installEventFilter(self)
        self.reverse_input.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.FocusIn:
            if obj in (self.min_px, self.max_px, self.min_view, self.max_view):
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
        if hasattr(self.tool, "_save_state"):
            self.tool._save_state()

    def handle_enter(self):
        focus = self.focusWidget()
        if focus in (self.min_px, self.max_px, self.min_view, self.max_view):
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
        else:
            self.form_exe()

    def flash_box(self, box: QFrame):
        box.setProperty("state", "active")
        box.style().unpolish(box)
        box.style().polish(box)
        QTimer.singleShot(350, lambda: self._reset_box_state(box))

    def _reset_box_state(self, box: QFrame):
        box.setProperty("state", "normal")
        box.style().unpolish(box)
        box.style().polish(box)

    def form_exe(self):
        self.flash_box(self.form_box)
        ok, min_value = parse_value_text(self.min_px.text())
        if not ok:
            self.error_result(min_value)
            return
        ok, max_value = parse_value_text(self.max_px.text())
        if not ok:
            self.error_result(max_value)
            return

        ok, min_view_value = parse_value_text(self.min_view.text())
        if not ok:
            self.error_result(min_view_value)
            return
        ok, max_view_value = parse_value_text(self.max_view.text())
        if not ok:
            self.error_result(max_view_value)
            return

        min_view, min_view_unit = min_view_value
        max_view, max_view_unit = max_view_value
        ok, view_unit = resolve_view_unit(min_view_unit, max_view_unit, self._view_unit)
        if not ok:
            self.error_result(view_unit)
            return

        ok, payload = build_clamp(
            min_value,
            max_value,
            min_view,
            max_view,
            selected_unit=self._result_unit,
            view_unit=view_unit,
        )
        if not ok:
            self.error_result(payload)
            return

        if view_unit in {"", "vw", "vh"}:
            self.set_view_unit(view_unit, save_state=False)
        self.success_result(
            self.min_px.text().strip(),
            min_view,
            max_view,
            self.max_px.text().strip(),
            payload,
            view_unit=view_unit,
        )

    def reverse_exe(self):
        self.flash_box(self.reverse_box)
        text = self.reverse_input.text().strip()
        if not text.startswith("clamp(") or not text.endswith(")"):
            self.error_result("error")
            return

        try:
            inner = text[6:-1]
            min_raw, calc_raw, max_raw = [part.strip() for part in inner.split(",", 2)]
            min_value, clamp_unit = self._parse_value_with_unit(min_raw)
            max_value, max_unit = self._parse_value_with_unit(max_raw)
            if clamp_unit != max_unit:
                raise ValueError("mixed units")

            calc_match = re.fullmatch(
                r"calc\(\s*(-?(?:\d+|\d*\.\d+))\s*([a-zA-Z%]*)\s*([+-])\s*(-?(?:\d+|\d*\.\d+))\s*([a-zA-Z%]*)\s*\)",
                calc_raw,
            )
            if not calc_match:
                raise ValueError("invalid calc")

            intercept = float(calc_match.group(1))
            intercept_unit = calc_match.group(2)
            sign = -1 if calc_match.group(3) == "-" else 1
            slope = float(calc_match.group(4)) * sign
            view_unit = calc_match.group(5)
            if intercept_unit != clamp_unit:
                raise ValueError("mixed units")
            if slope == 0:
                raise ValueError("view coefficient cannot be zero")

            min_view = (min_value - intercept) / slope * 100
            max_view = (max_value - intercept) / slope * 100
            pairs = sorted([(min_view, min_value), (max_view, max_value)], key=lambda pair: pair[0])
            (min_view, min_value), (max_view, max_value) = pairs

        except (ValueError, ZeroDivisionError):
            self.error_result("error")
            return

        self.min_px.setText(self._format_value_with_unit(min_value, clamp_unit))
        self.max_px.setText(self._format_value_with_unit(max_value, clamp_unit))
        formatted_min_view = self._format_number(min_view)
        formatted_max_view = self._format_number(max_view)
        if view_unit in {"", "vw", "vh"}:
            self.set_view_unit(view_unit, save_state=False)
        else:
            formatted_min_view += view_unit
            formatted_max_view += view_unit
        self.min_view.setText(formatted_min_view)
        self.max_view.setText(formatted_max_view)
        self.set_result_unit(clamp_unit, save_state=False)
        self.success_result(
            self.min_px.text().strip(),
            min_view,
            max_view,
            self.max_px.text().strip(),
            text,
            view_unit=view_unit,
        )

    def success_result(
        self,
        min_px=None,
        min_view=None,
        max_view=None,
        max_px=None,
        clamp_text=None,
        view_unit=None,
    ):
        clamp = clamp_text or self._build_result_text(min_px, min_view, max_view, max_px)
        if clamp is None:
            self.error_result("error")
            return

        self._result_values = (
            str(min_px),
            str(max_px),
            float(min_view),
            float(max_view),
            view_unit or self._view_unit,
        )
        self._current_result_text = clamp
        self.result_label.setText(clamp)
        self.result_label.setProperty("state", "success")
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)

        self.copy_result()
        if hasattr(self.tool, "_save_state"):
            self.tool._save_state()

    def error_result(self, message: str):
        self._result_values = None
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
        self.min_px.clear()
        self.max_px.clear()
        self.min_view.clear()
        self.max_view.clear()
        self.reverse_input.clear()
        self._result_values = None
        self._current_result_text = "clamp(...)"
        self.result_label.setText(self._current_result_text)
        self.result_label.setProperty("state", "start")
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)

        for box in (self.form_box, self.reverse_box):
            self._reset_box_state(box)

        self.last_edited = None
        self.min_px.setFocus()
        if hasattr(self.tool, "_save_state"):
            self.tool._save_state()

    def toggle_result_unit(self):
        self.set_result_unit(self.unit_toggle.currentData())

    def toggle_view_unit(self):
        self.set_view_unit(self.view_unit_toggle.currentData())

    def set_result_unit(self, unit: str, save_state: bool = True):
        self._result_unit = unit if unit in {"", "px", "%", "rem"} else ""
        self.unit_toggle.blockSignals(True)
        index = self.unit_toggle.findData(self._result_unit)
        self.unit_toggle.setCurrentIndex(max(0, index))
        self.unit_toggle.blockSignals(False)

        if self._result_values and self.result_label.property("state") in {"success", "copied"}:
            min_px, max_px, min_view, max_view, _ = self._result_values
            clamp = self._build_result_text(min_px, min_view, max_view, max_px)
            if clamp:
                self._current_result_text = clamp
                if self.result_label.property("state") != "copied":
                    self.result_label.setText(clamp)

        if save_state and hasattr(self.tool, "_save_state"):
            self.tool._save_state()

    def set_view_unit(self, unit: str, save_state: bool = True):
        self._view_unit = unit if unit in {"", "vw", "vh"} else "vw"
        self.view_unit_toggle.blockSignals(True)
        index = self.view_unit_toggle.findData(self._view_unit)
        self.view_unit_toggle.setCurrentIndex(max(0, index))
        self.view_unit_toggle.blockSignals(False)

        if self._result_values and self.result_label.property("state") in {"success", "copied"}:
            min_px, max_px, min_view, max_view, _ = self._result_values
            self._result_values = (min_px, max_px, min_view, max_view, self._view_unit)
            clamp = self._build_result_text(min_px, min_view, max_view, max_px)
            if clamp:
                self._current_result_text = clamp
                if self.result_label.property("state") != "copied":
                    self.result_label.setText(clamp)

        if save_state and hasattr(self.tool, "_save_state"):
            self.tool._save_state()

    def _build_result_text(self, min_px, min_view, max_view, max_px):
        ok, min_value = parse_value_text(str(min_px))
        if not ok:
            return None
        ok, max_value = parse_value_text(str(max_px))
        if not ok:
            return None
        ok, payload = build_clamp(
            min_value,
            max_value,
            float(min_view),
            float(max_view),
            selected_unit=self._result_unit,
            view_unit=self._result_values[4] if self._result_values else self._view_unit,
        )
        return payload if ok else None

    def state_payload(self) -> dict:
        return {
            "min_px": self.min_px.text(),
            "min_view": self.min_view.text(),
            "max_view": self.max_view.text(),
            "max_px": self.max_px.text(),
            "reverse_input": self.reverse_input.text(),
            "result_unit": self._result_unit,
            "view_unit": self._view_unit,
            "last_edited": self.last_edited,
            "result_text": self._current_result_text if self._result_values else "",
            "result_values": list(self._result_values) if self._result_values else None,
        }

    def apply_state(self, state: dict):
        self.min_px.setText(str(state.get("min_px", "")))
        self.min_view.setText(str(state.get("min_view", "")))
        self.max_view.setText(str(state.get("max_view", "")))
        self.max_px.setText(str(state.get("max_px", "")))
        self.reverse_input.setText(str(state.get("reverse_input", "")))
        self.set_result_unit(str(state.get("result_unit", "px")), save_state=False)
        self.set_view_unit(str(state.get("view_unit", "vw")), save_state=False)
        self.last_edited = state.get("last_edited")

        values = state.get("result_values")
        if isinstance(values, list) and len(values) == 5:
            try:
                self._result_values = (
                    str(values[0]),
                    str(values[1]),
                    float(values[2]),
                    float(values[3]),
                    str(values[4]),
                )
            except (TypeError, ValueError):
                self._result_values = None
        else:
            self._result_values = None

        result_text = state.get("result_text")
        if self._result_values and isinstance(result_text, str) and result_text:
            self._current_result_text = result_text
            self.result_label.setText(result_text)
            self.result_label.setProperty("state", "success")
        else:
            self._current_result_text = "clamp(...)"
            self.result_label.setText(self._current_result_text)
            self.result_label.setProperty("state", "start")
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)

    def _parse_value_with_unit(self, text: str) -> tuple[float, str]:
        ok, payload = parse_value_text(text)
        if not ok:
            raise ValueError("invalid value")
        return payload

    def _format_value_with_unit(self, value: float, unit: str) -> str:
        return f"{self._format_number(value)}{unit}"

    def _format_number(self, value: float) -> str:
        rounded = round(value)
        if abs(value - rounded) < 1e-9:
            return str(int(rounded))
        rounded_2 = round(value, 2)
        if abs(rounded_2 - round(rounded_2)) < 1e-9:
            return str(int(round(rounded_2)))
        return f"{rounded_2:.2f}".rstrip("0").rstrip(".")
