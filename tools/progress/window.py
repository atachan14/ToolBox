from __future__ import annotations

import json
import re
from pathlib import Path

from PySide6.QtCore import QRegularExpression, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


DEFAULT_SEGMENT = {
    "progress_name": "",
    "start_p": "",
    "start_v": "",
    "end_p": "",
    "end_v": "",
}


def _default_segment() -> dict:
    return dict(DEFAULT_SEGMENT)


def _normalize_segment(payload) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    return {
        "progress_name": str(payload.get("progress_name") or ""),
        "start_p": str(payload.get("start_p") or ""),
        "start_v": str(payload.get("start_v") or ""),
        "end_p": str(payload.get("end_p") or ""),
        "end_v": str(payload.get("end_v") or ""),
    }


def _numeric_text(value: str, fallback: str) -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _value_text(value: str, fallback: str) -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _segment_display(segment: dict) -> dict:
    return {
        "progress_name": _value_text(segment.get("progress_name", ""), "p"),
        "start_p": _numeric_text(segment.get("start_p", ""), "0"),
        "start_v": _value_text(segment.get("start_v", ""), "0"),
        "end_p": _numeric_text(segment.get("end_p", ""), "1"),
        "end_v": _value_text(segment.get("end_v", ""), "100"),
    }


def _safe_js_name(value: str) -> str:
    candidate = "".join(char if (char.isalnum() or char == "_") else "_" for char in value.strip())
    if not candidate:
        return "p"
    if candidate[0].isdigit():
        return f"_{candidate}"
    return candidate


def _safe_css_var_name(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        return "--p"
    if candidate.startswith("--"):
        candidate = candidate[2:]
    candidate = "".join(char if (char.isalnum() or char in "-_") else "-" for char in candidate)
    candidate = candidate.strip("-_")
    return f"--{candidate or 'p'}"


def _numeric_string(value: str) -> str | None:
    text = value.strip()
    try:
        number = float(text)
    except ValueError:
        return None
    return str(int(number)) if number.is_integer() else str(number)


def _split_css_value(text: str) -> tuple[float, str] | None:
    match = re.fullmatch(r"\s*(-?(?:\d+|\d*\.\d+))\s*([a-zA-Z%]*)\s*", text)
    if not match:
        return None
    return float(match.group(1)), match.group(2)


def _format_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.12g}"


def _format_css_value(value: float, unit: str) -> str:
    return f"{_format_number(value)}{unit}"


def _delta_value(start_v: str, end_v: str) -> str:
    start_parts = _split_css_value(start_v)
    end_parts = _split_css_value(end_v)
    if start_parts and end_parts and start_parts[1] == end_parts[1]:
        return _format_css_value(end_parts[0] - start_parts[0], start_parts[1])
    if start_parts and end_parts:
        if start_parts[0] == 0 and not start_parts[1]:
            return _format_css_value(end_parts[0], end_parts[1])
        if end_parts[0] == 0 and not end_parts[1]:
            return _format_css_value(-start_parts[0], start_parts[1])
    return f"{end_v.strip()} - {start_v.strip()}"


def _progress_span(start_p: str, end_p: str) -> str:
    start_number = _numeric_string(start_p)
    end_number = _numeric_string(end_p)
    if start_number is not None and end_number is not None:
        return _format_number(float(end_number) - float(start_number))
    return f"{end_p.strip()} - {start_p.strip()}"


def _value_bounds(start_v: str, end_v: str) -> tuple[str, str]:
    start_text = start_v.strip()
    end_text = end_v.strip()

    start_number = _numeric_string(start_text)
    end_number = _numeric_string(end_text)
    if start_number is not None and end_number is not None:
        return (
            start_number if float(start_number) <= float(end_number) else end_number,
            end_number if float(start_number) <= float(end_number) else start_number,
        )

    start_parts = _split_css_value(start_text)
    end_parts = _split_css_value(end_text)
    if start_parts and end_parts and start_parts[1] == end_parts[1]:
        if start_parts[0] <= end_parts[0]:
            return start_text, end_text
        return end_text, start_text

    return start_text, end_text


def _middle_expression(start_v: str, end_v: str, progress_name: str, start_p: str, end_p: str) -> str:
    start_text = start_v.strip()
    factor = f"((var({progress_name}) - {start_p.strip()}) / {_progress_span(start_p, end_p)})"
    start_parts = _split_css_value(start_text)
    end_parts = _split_css_value(end_v.strip())

    if start_parts and end_parts and start_parts[1] == end_parts[1]:
        delta = end_parts[0] - start_parts[0]
        if delta == 0:
            return start_text
        delta_text = _format_css_value(abs(delta), start_parts[1])
        if start_parts[0] == 0:
            sign = "-" if delta < 0 else ""
            return f"{sign}{delta_text} * {factor}"
        signed_delta = _format_css_value(delta, start_parts[1])
        return f"{start_text} + ({signed_delta}) * {factor}"

    delta_text = _delta_value(start_v, end_v)
    if start_text == "0":
        return f"{delta_text} * {factor}"
    return f"{start_text} + ({delta_text}) * {factor}"


class ClickCopyCode(QPlainTextEdit):
    clicked = Signal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class ProgressWindow(QWidget):
    COPY_FEEDBACK_MS = 900
    MAX_HISTORY = 50
    DEFAULT_HISTORY_DIALOG_WIDTH = 620
    DEFAULT_HISTORY_DIALOG_HEIGHT = 360
    INDEX_COLUMN_WIDTH = 28
    DEFAULT_COLUMN_RATIOS = [3, 1, 1, 1, 1]
    DEFAULT_COLUMN_WIDTHS = [INDEX_COLUMN_WIDTH, 252, 84, 84, 84, 84]
    MIN_DATA_COLUMN_WIDTH = 24
    DEFAULT_SPLITTER_SIZES = [320, 220]

    def __init__(self, state_path: Path | None = None, history_path: Path | None = None):
        super().__init__()
        self.state_path = Path(state_path) if state_path else None
        self.history_path = Path(history_path) if history_path else None
        self._history_dialog_width = self.DEFAULT_HISTORY_DIALOG_WIDTH
        self._history_dialog_height = self.DEFAULT_HISTORY_DIALOG_HEIGHT
        self._segment_table_column_widths = list(self.DEFAULT_COLUMN_WIDTHS)
        self._has_custom_column_widths = False
        self._splitter_sizes = list(self.DEFAULT_SPLITTER_SIZES)
        self._feedback_timer = QTimer(self)
        self._feedback_timer.setSingleShot(True)
        self._feedback_timer.timeout.connect(self._restore_feedback)
        self._table_syncing = False
        self._build_ui()
        self._restore_state()
        self._refresh_segment_table()
        self._refresh_code()

    def set_state_path(self, state_path: Path | None):
        self.state_path = Path(state_path) if state_path else None
        self._save_state()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self.main_splitter = QSplitter(Qt.Vertical)
        root.addWidget(self.main_splitter, 1)

        segment_frame = QFrame()
        segment_frame.setFrameShape(QFrame.StyledPanel)
        segment_layout = QVBoxLayout(segment_frame)
        segment_layout.setContentsMargins(8, 8, 8, 8)
        segment_layout.setSpacing(6)

        segment_title = QLabel("segments")
        segment_title.setStyleSheet("font-weight: bold;")
        segment_layout.addWidget(segment_title)

        self.segment_table = QTableWidget(0, 6)
        self.segment_table.setHorizontalHeaderLabels(["#", "var", "start p", "end p", "start v", "end v"])
        self.segment_table.verticalHeader().setVisible(False)
        self.segment_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.segment_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.segment_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.AnyKeyPressed)
        self.segment_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.segment_table.itemChanged.connect(self._on_segment_table_changed)
        self.segment_table.customContextMenuRequested.connect(self._on_segment_table_context_requested)
        header = self.segment_table.horizontalHeader()
        for section in range(self.segment_table.columnCount()):
            header.setSectionResizeMode(section, QHeaderView.Interactive)
        header.setMinimumSectionSize(28)
        header.sectionResized.connect(self._on_segment_table_column_resized)
        segment_layout.addWidget(self.segment_table, 1)

        self.add_segment_button = QPushButton("add segment")
        self.add_segment_button.clicked.connect(self._add_segment)
        segment_layout.addWidget(self.add_segment_button)

        self.main_splitter.addWidget(segment_frame)

        code_frame = QFrame()
        code_frame.setFrameShape(QFrame.StyledPanel)
        code_layout = QVBoxLayout(code_frame)
        code_layout.setContentsMargins(8, 8, 8, 8)
        code_layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        title = QLabel("code")
        title.setStyleSheet("font-weight: bold;")
        header.addWidget(title)
        header.addStretch(1)

        self.feedback = QLabel("")
        self.feedback.setStyleSheet("color: palette(highlight);")
        header.addWidget(self.feedback)
        code_layout.addLayout(header)

        self.code = ClickCopyCode()
        self.code.setReadOnly(True)
        self.code.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.code.setPlaceholderText("Generated code will appear here.")
        self.code.clicked.connect(self._copy_code)
        code_layout.addWidget(self.code, 1)
        self.main_splitter.addWidget(code_frame)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.splitterMoved.connect(self._on_splitter_moved)

        button_wrap = QVBoxLayout()
        button_wrap.setContentsMargins(0, 0, 0, 0)
        button_wrap.setSpacing(4)

        top_buttons = QHBoxLayout()
        top_buttons.setContentsMargins(0, 0, 0, 0)
        top_buttons.setSpacing(4)
        self.save_history_button = QPushButton("履歴を保存")
        self.show_history_button = QPushButton("履歴を表示")
        top_buttons.addWidget(self.save_history_button)
        top_buttons.addWidget(self.show_history_button)
        button_wrap.addLayout(top_buttons)

        self.reset_button = QPushButton("リセット")
        button_wrap.addWidget(self.reset_button)

        root.addLayout(button_wrap)

        self.save_history_button.clicked.connect(self._save_current_to_history)
        self.show_history_button.clicked.connect(self._show_history_dialog)
        self.reset_button.clicked.connect(self._reset_state)

    def _restore_state(self):
        state = {}
        if self.state_path and self.state_path.exists():
            try:
                loaded = json.loads(self.state_path.read_text(encoding="utf-8") or "{}")
            except json.JSONDecodeError:
                loaded = {}
            if isinstance(loaded, dict):
                state = loaded

        segments = state.get("segments") if isinstance(state.get("segments"), list) else []
        self._segments = [_normalize_segment(item) for item in segments] or [_default_segment()]
        self._history_dialog_width = max(
            320,
            int(state.get("history_dialog_width", self.DEFAULT_HISTORY_DIALOG_WIDTH)),
        )
        self._history_dialog_height = max(
            240,
            int(state.get("history_dialog_height", self.DEFAULT_HISTORY_DIALOG_HEIGHT)),
        )
        splitter_sizes = state.get("splitter_sizes")
        if isinstance(splitter_sizes, list) and len(splitter_sizes) == 2:
            try:
                self._splitter_sizes = [max(80, int(size)) for size in splitter_sizes]
            except (TypeError, ValueError):
                self._splitter_sizes = list(self.DEFAULT_SPLITTER_SIZES)
        column_widths = state.get("segment_table_column_widths")
        if isinstance(column_widths, list) and len(column_widths) == self.segment_table.columnCount():
            try:
                self._segment_table_column_widths = [max(36, int(width)) for width in column_widths]
                self._segment_table_column_widths[0] = max(self.INDEX_COLUMN_WIDTH, int(column_widths[0]))
                self._has_custom_column_widths = True
            except (TypeError, ValueError):
                self._segment_table_column_widths = list(self.DEFAULT_COLUMN_WIDTHS)
                self._has_custom_column_widths = False

    def _save_state(self):
        if not self.state_path:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "segments": self._segments_from_table(),
            "history_dialog_width": self._history_dialog_width,
            "history_dialog_height": self._history_dialog_height,
            "segment_table_column_widths": list(self._segment_table_column_widths),
            "splitter_sizes": list(self.main_splitter.sizes()),
        }
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _refresh_segment_table(self):
        self._table_syncing = True
        self.segment_table.setRowCount(len(self._segments))
        for row, segment in enumerate(self._segments):
            index_item = QTableWidgetItem(str(row + 1))
            index_item.setFlags(index_item.flags() & ~Qt.ItemIsEditable)
            index_item.setTextAlignment(Qt.AlignCenter)
            self.segment_table.setItem(row, 0, index_item)
            values = [
                segment.get("progress_name", ""),
                segment.get("start_p", ""),
                segment.get("end_p", ""),
                segment.get("start_v", ""),
                segment.get("end_v", ""),
            ]
            for column, value in enumerate(values, start=1):
                item = self.segment_table.item(row, column)
                if item is None:
                    item = QTableWidgetItem()
                    if column in (2, 3):
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.segment_table.setItem(row, column, item)
                item.setText(str(value))
        self._apply_segment_table_widths()
        self._table_syncing = False

    def _apply_segment_table_widths(self):
        viewport_width = max(0, self.segment_table.viewport().width())

        if self._has_custom_column_widths:
            total_width = sum(self._segment_table_column_widths)
            if viewport_width > 0 and total_width > viewport_width:
                self._has_custom_column_widths = False
            else:
                for index, width in enumerate(self._segment_table_column_widths):
                    self.segment_table.setColumnWidth(index, width)
                return

        if viewport_width <= 0:
            for index, width in enumerate(self._segment_table_column_widths):
                self.segment_table.setColumnWidth(index, width)
            return

        fixed_width = min(self.INDEX_COLUMN_WIDTH, max(20, viewport_width))
        remaining_width = max(0, viewport_width - fixed_width)
        ratio_total = sum(self.DEFAULT_COLUMN_RATIOS)
        dynamic_widths: list[int] = []
        consumed = 0
        for ratio in self.DEFAULT_COLUMN_RATIOS[:-1]:
            width = round(remaining_width * ratio / ratio_total)
            dynamic_widths.append(width)
            consumed += width
        dynamic_widths.append(max(0, remaining_width - consumed))

        # Keep narrow viewports inside the table width budget.
        if remaining_width >= self.MIN_DATA_COLUMN_WIDTH * len(self.DEFAULT_COLUMN_RATIOS):
            dynamic_widths = [max(self.MIN_DATA_COLUMN_WIDTH, width) for width in dynamic_widths]
            overflow = fixed_width + sum(dynamic_widths) - viewport_width
            if overflow > 0:
                for index in range(len(dynamic_widths) - 1, -1, -1):
                    reducible = dynamic_widths[index] - self.MIN_DATA_COLUMN_WIDTH
                    if reducible <= 0:
                        continue
                    delta = min(reducible, overflow)
                    dynamic_widths[index] -= delta
                    overflow -= delta
                    if overflow <= 0:
                        break

        widths = [fixed_width, *dynamic_widths]
        self._segment_table_column_widths = widths
        for index, width in enumerate(widths):
            self.segment_table.setColumnWidth(index, width)

    def _schedule_segment_table_widths(self):
        if self._has_custom_column_widths:
            return
        QTimer.singleShot(0, self._apply_segment_table_widths)

    def _schedule_splitter_sizes(self):
        QTimer.singleShot(0, lambda: self.main_splitter.setSizes(self._splitter_sizes))

    def _segments_from_table(self) -> list[dict]:
        segments: list[dict] = []
        for row in range(self.segment_table.rowCount()):
            def _text(column: int) -> str:
                item = self.segment_table.item(row, column)
                return item.text() if item is not None else ""
            segments.append(
                {
                    "progress_name": _text(1),
                    "start_p": _text(2),
                    "end_p": _text(3),
                    "start_v": _text(4),
                    "end_v": _text(5),
                }
            )
        return segments or [_default_segment()]

    def _on_segment_table_changed(self, _item: QTableWidgetItem):
        if self._table_syncing:
            return
        self._segments = [_normalize_segment(item) for item in self._segments_from_table()]
        self._refresh_code()
        self._save_state()

    def _on_segment_table_context_requested(self, pos):
        row = self.segment_table.rowAt(pos.y())
        if row < 0:
            return
        menu = QMenu(self.segment_table)
        delete_action = menu.addAction("delete segment")
        if len(self._segments) <= 1:
            delete_action.setEnabled(False)
        action = menu.exec(self.segment_table.viewport().mapToGlobal(pos))
        if action == delete_action:
            self._remove_segment(row)

    def _on_segment_table_column_resized(self, section: int, _old_size: int, new_size: int):
        if not (0 <= section < len(self._segment_table_column_widths)):
            return
        width = max(self.INDEX_COLUMN_WIDTH if section == 0 else 36, int(new_size))
        if self._segment_table_column_widths[section] == width:
            return
        self._has_custom_column_widths = True
        self._segment_table_column_widths[section] = width
        self._save_state()

    def _on_splitter_moved(self, _pos: int, _index: int):
        self._splitter_sizes = [max(80, int(size)) for size in self.main_splitter.sizes()]
        self._save_state()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_segment_table_widths()

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_segment_table_widths()
        self._schedule_splitter_sizes()

    def _add_segment(self):
        self._segments = [_normalize_segment(item) for item in self._segments_from_table()]
        self._segments.append(_default_segment())
        self._refresh_segment_table()
        self.segment_table.selectRow(len(self._segments) - 1)
        self._refresh_code()
        self._save_state()

    def _remove_segment(self, index: int):
        if len(self._segments) <= 1:
            return
        current = self._segments_from_table()
        if 0 <= index < len(current):
            current.pop(index)
        self._segments = current or [_default_segment()]
        self._refresh_segment_table()
        if self._segments:
            self.segment_table.selectRow(min(index, len(self._segments) - 1))
        self._refresh_code()
        self._save_state()

    def _copy_code(self):
        text = self.code.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.feedback.setText("copied")
        self._feedback_timer.start(self.COPY_FEEDBACK_MS)

    def _restore_feedback(self):
        self.feedback.setText("")

    def _refresh_code(self):
        self.code.setPlainText(self._build_code(self._segments_from_table()))

    def _current_segments(self) -> list[dict]:
        return self._segments_from_table()

    def _reset_state(self):
        self._segments = [_default_segment()]
        self._refresh_segment_table()
        self.segment_table.selectRow(0)
        self._refresh_code()
        self._save_state()

    def _history_payload(self) -> dict:
        return {
            "segments": self._current_segments(),
            "code": self.code.toPlainText(),
        }

    def _load_history_entries(self) -> list[dict]:
        if not self.history_path or not self.history_path.exists():
            return []
        try:
            loaded = json.loads(self.history_path.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError:
            return []
        entries: list[dict] = []
        for item in loaded:
            if not isinstance(item, dict):
                continue
            segments = item.get("segments")
            if not isinstance(segments, list):
                continue
            normalized_segments = [_normalize_segment(segment) for segment in segments]
            if not normalized_segments:
                continue
            entries.append(
                {
                    "segments": normalized_segments,
                    "code": str(item.get("code") or self._build_code(normalized_segments)),
                }
            )
        return entries[: self.MAX_HISTORY]

    def _save_history_entries(self, entries: list[dict]):
        if not self.history_path:
            return
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_text(
            json.dumps(entries[: self.MAX_HISTORY], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_current_to_history(self):
        entries = self._load_history_entries()
        entry = self._history_payload()
        if entries and entries[0] == entry:
            return
        entries.insert(0, entry)
        self._save_history_entries(entries)
        self.feedback.setText("saved")
        self._feedback_timer.start(self.COPY_FEEDBACK_MS)

    def _apply_history_entry_state(self, payload: dict):
        segments = payload.get("segments")
        if not isinstance(segments, list):
            return
        self._segments = [_normalize_segment(segment) for segment in segments] or [_default_segment()]
        self._refresh_segment_table()
        self.segment_table.selectRow(0)
        self._refresh_code()
        self._save_state()

    def _show_history_dialog(self):
        entries = self._load_history_entries()
        if not entries:
            QMessageBox.information(self, "履歴", "履歴がありません")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Progress History")
        layout = QVBoxLayout(dialog)

        history_list = QListWidget()
        history_list.setSelectionMode(QListWidget.NoSelection)
        history_list.setWordWrap(True)
        history_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        layout.addWidget(history_list)

        for entry in entries:
            segments = entry["segments"]
            first = _segment_display(segments[0])
            header = f"[{first['start_p']} -> {segments[-1].get('end_p') or '1'}] {len(segments)} segment"
            text = f"{header}\n{entry['code']}"
            item = QListWidgetItem(text)
            item.setToolTip(entry["code"])
            item.setData(Qt.UserRole, entry)
            history_list.addItem(item)

        def on_item_clicked(item: QListWidgetItem):
            payload = item.data(Qt.UserRole)
            if not isinstance(payload, dict):
                return
            QApplication.clipboard().setText(str(payload.get("code") or ""))
            original_text = item.text()
            item.setForeground(QBrush(QColor("#4ecdc4")))
            item.setText("Copied and applied")

            def restore():
                row = history_list.row(item)
                if row >= 0:
                    current = history_list.item(row)
                    if current is not None:
                        current.setForeground(QBrush())
                        current.setText(original_text)

            QTimer.singleShot(700, restore)
            self._apply_history_entry_state(payload)

        def on_context_menu(pos):
            item = history_list.itemAt(pos)
            if item is None:
                return
            menu = QMenu(history_list)
            delete_action = menu.addAction("履歴から削除")
            action = menu.exec(history_list.viewport().mapToGlobal(pos))
            if action != delete_action:
                return
            row = history_list.row(item)
            if row < 0:
                return
            del entries[row]
            self._save_history_entries(entries)
            history_list.takeItem(row)

        history_list.itemClicked.connect(on_item_clicked)
        history_list.customContextMenuRequested.connect(on_context_menu)

        dialog.resize(self._history_dialog_width, self._history_dialog_height)

        def persist_dialog_size(_result: int):
            self._history_dialog_width = max(320, dialog.width())
            self._history_dialog_height = max(240, dialog.height())
            self._save_state()

        dialog.finished.connect(persist_dialog_size)
        dialog.exec()

    def _build_code(self, segments: list[dict]) -> str:
        display_segments = [_segment_display(segment) for segment in segments]
        if len(display_segments) == 1:
            segment = display_segments[0]
            progress_name = _safe_css_var_name(segment["progress_name"])
            min_value, max_value = _value_bounds(segment["start_v"], segment["end_v"])
            return "\n".join(
                [
                    "clamp(",
                    f"  {min_value},",
                    f"  {_middle_expression(segment['start_v'], segment['end_v'], progress_name, segment['start_p'], segment['end_p'])},",
                    f"  {max_value}",
                    ")",
                ]
            )

        lines = ["calc("]

        for index, segment in enumerate(display_segments):
            progress_name = _safe_css_var_name(segment["progress_name"])
            min_value, max_value = _value_bounds(segment["start_v"], segment["end_v"])
            prefix = "  " if index == 0 else "  + "
            lines.append(f"{prefix}clamp(")
            lines.append(f"      {min_value},")
            lines.append(f"      {_middle_expression(segment['start_v'], segment['end_v'], progress_name, segment['start_p'], segment['end_p'])},")
            lines.append(f"      {max_value}")
            lines.append("    )")

        lines.append(")")
        return "\n".join(lines)
