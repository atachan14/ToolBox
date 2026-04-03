from __future__ import annotations

import json
import math
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetrics, QKeySequence, QResizeEvent, QShortcut, QShowEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QAbstractItemView, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from .canvas import GradientCanvas, GradientCanvasConfig
from .color_utils import display_color_text, parse_color_text
from .footer import GradientFooter
from .history_preview import GradientHistoryItemWidget, build_history_preview_lines, history_preview_height, render_history_preview_pixmap
from .layer_panels import build_background_inspector, build_linear_inspector, build_pending_inspector, build_radial_inspector, populate_linear_stop_table, style_color_value_widget
from .linear_layer import append_stop, append_stop_after_last, delete_stop, duplicate_stop, linear_stops_css, move_stop, reorder_stop, set_stop_color, step_stop, toggle_stop_muted, update_stop_from_table
from .palette_data_window import PaletteDataWindow
from .palette import GradientPalette
from .palette_storage import delete_palette, load_palettes, palette_dir, rename_palette, save_palette
from .state import normalize_layer_payload, normalize_palette_colors, serialize_layers
from .toolbar import GradientToolbar
from .widgets import SwatchDialog


class GradientWindow(QMainWindow):
    MAX_HISTORY = 100
    MAX_UNDO = 200
    DEFAULT_HISTORY_DIALOG_WIDTH = 620
    DEFAULT_HISTORY_DIALOG_HEIGHT = 360
    PALETTE_COLORS = [
        "#00000000",
        "#000000",
        "#ffffff",
    ]

    parse_color_text = staticmethod(parse_color_text)
    DEGREE_PRESET_TO_VALUE = {
        "to top": 0,
        "to top right": 45,
        "to right": 90,
        "to bottom right": 135,
        "to bottom": 180,
        "to bottom left": 225,
        "to left": 270,
        "to top left": 315,
    }

    def __init__(self, state_path: Path | None = None, history_path: Path | None = None, tool_data_dir: Path | None = None):
        super().__init__()
        self.state_path = Path(state_path) if state_path else None
        self.history_path = Path(history_path) if history_path else None
        self.tool_data_dir = Path(tool_data_dir) if tool_data_dir else None
        self.palette_storage_dir = palette_dir(self.tool_data_dir)
        self._toolbar_button_height = 24
        self.layers: list[dict] = []
        self.palette_colors = list(self.PALETTE_COLORS)
        self.selected_palette_color = self.PALETTE_COLORS[0]
        self._hover_position: float | None = None
        self._building_tabs = False
        self._table_syncing = False
        self._code_full_text = "background: none;"
        self._code_scroll_offset = 0
        self.copy_feedback_base_text = ""
        self._history_dialog_width = self.DEFAULT_HISTORY_DIALOG_WIDTH
        self._history_dialog_height = self.DEFAULT_HISTORY_DIALOG_HEIGHT
        self._stop_table_column_widths = [52, 48, 52, 42]
        self._selected_stop_index: int | None = None
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._applying_undo_redo = False
        self._undo_batch_depth = 0
        self._state_commit_timer = QTimer(self)
        self._state_commit_timer.setSingleShot(True)
        self._state_commit_timer.setInterval(120)
        self._state_commit_timer.timeout.connect(self._commit_state_snapshot)

        self._build_ui()
        self._connect_ui()
        self._restore_state()
        self._refresh_all()

    def set_state_path(self, state_path: Path | None):
        self.state_path = Path(state_path) if state_path else None
        self._save_state()

    def _build_ui(self):
        self.setWindowTitle("Gradient")
        body = QWidget()
        root_layout = QVBoxLayout(body)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        self.toolbar = GradientToolbar(self._toolbar_button_height)
        root_layout.addWidget(self.toolbar)

        self.main_splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(self.main_splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.inspector_tabs_placeholder_index = -1
        self.canvas = GradientCanvas(
            GradientCanvasConfig(
                size_getter=self._get_size,
                grid_getter=self._get_grid,
                guide_enabled_getter=self._guide_enabled,
                layers_getter=lambda: self.layers,
                active_layer_getter=self._active_layer,
                active_layer_index_getter=lambda: self.inspector_tabs.currentIndex(),
                selected_stop_index_getter=lambda: self._selected_stop_index,
                active_palette_color_getter=lambda: self.selected_palette_color,
                cursor_changed=self._set_cursor_text,
                background_clicked=self._apply_palette_to_background_from_canvas,
                linear_stop_hovered=self._set_hover_position,
                linear_stop_clicked=self._add_stop_from_canvas,
                linear_stop_moved=self._move_stop_from_canvas,
                linear_stop_deleted=self._delete_stop_from_canvas,
                radial_center_moved=self._move_radial_center_from_canvas,
                interaction_started=self._begin_undo_batch,
                interaction_finished=self._end_undo_batch,
            )
        )
        left_layout.addWidget(self.canvas, 1)

        self.palette = GradientPalette(self.palette_colors)
        left_layout.addWidget(self.palette)
        self.main_splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        add_buttons = QHBoxLayout()
        add_buttons.setSpacing(4)
        self.add_linear_button = QPushButton("linear")
        self.add_radial_button = QPushButton("radial")
        self.add_conic_button = QPushButton("conic")
        for button in (self.add_linear_button, self.add_radial_button, self.add_conic_button):
            button.setFixedHeight(self._toolbar_button_height)
            add_buttons.addWidget(button)
        right_layout.addLayout(add_buttons)

        from PySide6.QtWidgets import QTabWidget  # local import keeps module dependencies shallow
        self.inspector_tabs = QTabWidget()
        self.inspector_tabs.setMovable(True)
        right_layout.addWidget(self.inspector_tabs, 1)

        buttons_wrap = QVBoxLayout()
        buttons_wrap.setSpacing(4)
        buttons_row1 = QHBoxLayout()
        buttons_row1.setSpacing(4)
        buttons_row2 = QHBoxLayout()
        buttons_row2.setSpacing(4)
        self.reset_button = QPushButton("Reset")
        self.save_history_button = QPushButton("履歴に保存")
        self.show_history_button = QPushButton("履歴を表示")
        self.reset_button.setFixedHeight(self._toolbar_button_height)
        self.save_history_button.setFixedHeight(self._toolbar_button_height)
        self.show_history_button.setFixedHeight(self._toolbar_button_height)
        buttons_row1.addWidget(self.reset_button)
        buttons_row2.addWidget(self.save_history_button)
        buttons_row2.addWidget(self.show_history_button)
        buttons_wrap.addLayout(buttons_row1)
        buttons_wrap.addLayout(buttons_row2)
        right_layout.addLayout(buttons_wrap)

        self.main_splitter.addWidget(right)
        left.setMinimumWidth(1)
        right.setMinimumWidth(180)
        right.setMaximumWidth(16777215)
        self.main_splitter.setSizes([200, 200])

        self.footer = GradientFooter(self._on_code_clicked, self._on_code_wheel)
        root_layout.addWidget(self.footer)
        self.setCentralWidget(body)

    def _connect_ui(self):
        self.toolbar.changed.connect(self._on_ui_changed)
        self.palette.colorSelected.connect(self._on_palette_selected)
        self.palette.colorsChanged.connect(self._on_palette_colors_changed)
        self.palette.saveRequested.connect(self._on_palette_save_requested)
        self.palette.loadRequested.connect(self._show_palette_data_window)
        self.palette.resetRequested.connect(self._reset_palette)
        self.add_linear_button.clicked.connect(lambda: self._add_layer("linear"))
        self.add_radial_button.clicked.connect(lambda: self._add_layer("radial"))
        self.add_conic_button.clicked.connect(lambda: self._add_layer("conic"))
        self.inspector_tabs.currentChanged.connect(self._on_tab_changed)
        self.inspector_tabs.tabBar().tabMoved.connect(self._on_tab_moved)
        self.inspector_tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.inspector_tabs.tabBar().customContextMenuRequested.connect(self._show_layer_tab_menu)
        self.reset_button.clicked.connect(self._reset_state)
        self.save_history_button.clicked.connect(self._save_current_to_history)
        self.show_history_button.clicked.connect(self._show_history_dialog)
        self.main_splitter.splitterMoved.connect(lambda *_: self._save_state())
        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.undo_shortcut.activated.connect(self._undo)
        self.redo_shortcut = QShortcut(QKeySequence("Ctrl+Y"), self)
        self.redo_shortcut.activated.connect(self._redo)
        self.redo_alt_shortcut = QShortcut(QKeySequence.Redo, self)
        self.redo_alt_shortcut.activated.connect(self._redo)

    def _get_size(self) -> tuple[float, float, str]:
        return self.toolbar.get_size()

    def _get_grid(self) -> tuple[bool, int]:
        return self.toolbar.get_grid()

    def _guide_enabled(self) -> bool:
        return self.toolbar.guide_enabled()

    def _unit_name(self) -> str:
        return self.toolbar.unit_name()

    def _gradient_span(self, deg: float) -> float:
        width, height, _unit = self._get_size()
        rad = math.radians(deg)
        return max(1e-6, abs(math.sin(rad)) * width + abs(math.cos(rad)) * height)

    def _radial_span(self, layer: dict, axis: str = "radius") -> float:
        width, height, _unit = self._get_size()
        if axis == "x":
            return max(1e-6, width)
        if axis == "y":
            return max(1e-6, height)
        center_x = self._resolve_radial_axis_value(layer, "x") * width
        center_y = self._resolve_radial_axis_value(layer, "y") * height
        corners = ((0.0, 0.0), (width, 0.0), (0.0, height), (width, height))
        return max(1e-6, max(math.hypot(center_x - x, center_y - y) for x, y in corners))

    def _layer_effective_deg(self, layer: dict) -> float:
        mode = str(layer.get("deg_mode", "input"))
        if mode != "input":
            preset_value = self.DEGREE_PRESET_TO_VALUE.get(mode)
            if preset_value is not None:
                return float(preset_value)
        return float(layer.get("deg", 90))

    def _compact_number(self, number: float) -> str:
        return str(int(round(number))) if abs(number - round(number)) < 1e-9 else f"{number:.2f}"

    def _convert_between_units(self, value: float, from_unit: str, to_unit: str, span: float) -> float:
        if from_unit == to_unit:
            return value
        normalized = (value / max(1e-6, span)) if from_unit == "px" else (value / 100.0)
        return normalized * max(1e-6, span) if to_unit == "px" else normalized * 100.0

    def _default_stop_unit(self, layer: dict) -> str:
        if layer.get("kind") == "linear":
            return self._unit_name()
        stops = list(layer.get("stops") or [])
        if stops:
            return str(stops[-1].get("unit", "%"))
        return "%"

    def _stop_span(self, layer: dict) -> float:
        return self._radial_span(layer, "radius") if layer.get("kind") == "radial" else self._gradient_span(self._layer_effective_deg(layer))

    def _stop_unit_name(self, layer: dict, stop: dict | None = None) -> str:
        if stop is not None:
            return str(stop.get("unit", self._default_stop_unit(layer)))
        return self._default_stop_unit(layer)

    def _resolve_stop_position(self, layer: dict, stop: dict) -> float:
        unit = self._stop_unit_name(layer, stop)
        value = float(stop.get("position", 0.0))
        if unit == "px":
            return value / self._stop_span(layer)
        return value / 100.0

    def _normalized_to_stop_value(self, layer: dict, position: float, unit: str) -> float:
        if unit == "px":
            return position * self._stop_span(layer)
        return position * 100.0

    def _format_stop_value(self, layer: dict, stop: dict) -> str:
        return self._compact_number(float(stop.get("position", 0.0)))

    def _format_stop_css_value(self, layer: dict, stop: dict) -> str:
        unit = self._stop_unit_name(layer, stop)
        return f"{self._compact_number(float(stop.get('position', 0.0)))}{unit}"

    def _format_hover_stop_value(self, layer: dict, position: float) -> str:
        unit = self._default_stop_unit(layer)
        raw_value = self._normalized_to_stop_value(layer, position, unit)
        return f"{self._compact_number(raw_value)}{unit}"

    def _parse_stop_value(self, layer: dict, text: str, unit: str) -> float | None:
        value_text = text.strip().lower()
        if not value_text:
            return None
        span = self._stop_span(layer)
        try:
            if value_text.endswith("px"):
                numeric = float(value_text[:-2].strip())
                return self._convert_between_units(numeric, "px", unit, span)
            if value_text.endswith("%"):
                numeric = float(value_text[:-1].strip())
                return self._convert_between_units(numeric, "%", unit, span)
            return float(value_text)
        except ValueError:
            return None

    def _radial_axis_unit_name(self, layer: dict, axis: str) -> str:
        return str(layer.get(f"center_{axis}_unit", "%"))

    def _resolve_radial_axis_value(self, layer: dict, axis: str) -> float:
        raw_value = float(layer.get(f"center_{axis}", 50.0 if self._radial_axis_unit_name(layer, axis) == "%" else self._radial_span(layer, axis) / 2.0))
        unit = self._radial_axis_unit_name(layer, axis)
        if unit == "px":
            return raw_value / self._radial_span(layer, axis)
        return raw_value / 100.0

    def _normalized_to_radial_axis_value(self, layer: dict, axis: str, normalized: float, unit: str | None = None) -> float:
        target_unit = unit or self._radial_axis_unit_name(layer, axis)
        if target_unit == "px":
            return normalized * self._radial_span(layer, axis)
        return normalized * 100.0

    def _format_radial_position_value(self, layer: dict, axis: str) -> str:
        return self._compact_number(float(layer.get(f"center_{axis}", 0.0)))

    def _format_radial_position_css(self, layer: dict, axis: str) -> str:
        unit = self._radial_axis_unit_name(layer, axis)
        return f"{self._compact_number(float(layer.get(f'center_{axis}', 0.0)))}{unit}"

    def _parse_radial_position_value(self, layer: dict, text: str, axis: str) -> float | None:
        value_text = text.strip().lower()
        if not value_text:
            return None
        unit = self._radial_axis_unit_name(layer, axis)
        span = self._radial_span(layer, axis)
        try:
            if value_text.endswith("px"):
                numeric = float(value_text[:-2].strip())
                return self._convert_between_units(numeric, "px", unit, span)
            if value_text.endswith("%"):
                numeric = float(value_text[:-1].strip())
                return self._convert_between_units(numeric, "%", unit, span)
            return float(value_text)
        except ValueError:
            return None

    def _set_cursor_text(self, text: str):
        self.footer.set_cursor_text(text)

    def _default_cursor_text(self) -> str:
        size_w, size_h, unit = self._get_size()
        if unit == "px":
            return f"Cursor: x={0.0:.1f}px, y={0.0:.1f}px"
        return "Cursor: x=0.00%, y=0.00%"

    def _refresh_cursor_text(self):
        layer = self._active_layer()
        if self._hover_position is not None and layer and layer.get("kind") in ("linear", "radial"):
            self.footer.set_cursor_text(f"Cursor: stop={self._format_hover_stop_value(layer, self._hover_position)}")
            return
        self.footer.set_cursor_text(self._default_cursor_text())

    def _set_hover_position(self, position: float | None):
        self._hover_position = position
        layer = self._active_layer()
        if position is not None and layer and layer.get("kind") in ("linear", "radial"):
            self.footer.set_cursor_text(f"Cursor: stop={self._format_hover_stop_value(layer, position)}")
        elif position is None:
            self._refresh_cursor_text()
        self._refresh_active_table()

    def _on_palette_selected(self, color: str):
        self.selected_palette_color = color
        self.canvas.update()
        self._save_state()

    def _on_palette_colors_changed(self, colors: list[str]):
        self.palette_colors = list(colors)
        self._save_state()

    def _on_palette_save_requested(self):
        save_palette(self.palette_storage_dir, self.palette.palette_colors)

    def _reset_palette(self):
        self.palette_colors = list(self.PALETTE_COLORS)
        self.palette.set_palette_colors(self.palette_colors)
        self.selected_palette_color = self.palette_colors[0]
        self.palette.select_index(0)
        self._save_state()

    def _show_palette_data_window(self):
        dialog = PaletteDataWindow(
            load_entries=lambda: load_palettes(self.palette_storage_dir),
            apply_palette=self._apply_loaded_palette,
            rename_palette=self._rename_saved_palette,
            delete_palette=self._delete_saved_palette,
            parent=self,
        )
        dialog.exec()

    def _apply_loaded_palette(self, entry: dict):
        colors = list(entry.get("colors") or [])
        if not colors:
            return
        normalized = [parse_color_text(str(color)) or "#00000000" for color in colors]
        self.palette_colors = normalized
        self.palette.set_palette_colors(normalized)
        self.selected_palette_color = normalized[0]
        self.palette.select_index(0)
        self._save_state()

    def _rename_saved_palette(self, path: Path, new_name: str):
        rename_palette(path, new_name)

    def _delete_saved_palette(self, path: Path):
        delete_palette(path)

    def _history_entry_layers(self) -> list[dict]:
        return serialize_layers(self.layers)

    def _apply_palette_state(self, palette_state, selected_palette_color):
        colors = normalize_palette_colors(palette_state)
        if colors:
            self.palette_colors = colors
            self.palette.set_palette_colors(colors)
        selected_palette = str(selected_palette_color or self.palette.palette_colors[0])
        if selected_palette in self.palette.palette_colors:
            self.selected_palette_color = selected_palette
            self.palette.select_color(selected_palette)
        else:
            self.selected_palette_color = self.palette.palette_colors[0]
            self.palette.select_index(0)

    def _apply_layers_state(self, layers_state, active_tab: int = 0):
        self.layers = []
        self.inspector_tabs.clear()
        if isinstance(layers_state, list):
            for item in layers_state:
                normalized = normalize_layer_payload(item, self._layer_default_name, self._unit_name())
                if normalized is not None:
                    self._add_layer(normalized["kind"], normalized)
        if not self.layers or self.layers[0].get("kind") != "background":
            self.layers.insert(0, self._new_background_layer())
            self._rebuild_inspector_tabs()
        if self.inspector_tabs.count() > 0:
            self.inspector_tabs.setCurrentIndex(max(0, min(int(active_tab), self.inspector_tabs.count() - 1)))

    def _history_entry_state(self) -> dict:
        return self._state_payload(include_ui=False)

    def _record_undo_snapshot(self, clear_redo: bool = True):
        if self._applying_undo_redo or self._undo_batch_depth > 0:
            return
        snapshot = self._state_payload(include_ui=False)
        if self._undo_stack and self._undo_stack[-1] == snapshot:
            return
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self.MAX_UNDO:
            self._undo_stack = self._undo_stack[-self.MAX_UNDO :]
        if clear_redo:
            self._redo_stack.clear()

    def _commit_state_snapshot(self):
        self._save_state()
        self._record_undo_snapshot()

    def _schedule_state_commit(self):
        self._state_commit_timer.start()

    def _apply_snapshot(self, snapshot: dict):
        self._applying_undo_redo = True
        try:
            self._apply_history_entry_state(snapshot)
        finally:
            self._applying_undo_redo = False

    def _begin_undo_batch(self):
        self._undo_batch_depth += 1

    def _end_undo_batch(self):
        if self._undo_batch_depth <= 0:
            return
        self._undo_batch_depth -= 1
        if self._undo_batch_depth == 0:
            self._record_undo_snapshot()

    def _undo(self):
        if len(self._undo_stack) < 2:
            return
        current = self._undo_stack.pop()
        self._redo_stack.append(current)
        self._apply_snapshot(self._undo_stack[-1])

    def _redo(self):
        if not self._redo_stack:
            return
        snapshot = self._redo_stack.pop()
        self._apply_snapshot(snapshot)
        self._undo_stack.append(snapshot)

    def _state_payload(self, include_ui: bool) -> dict:
        payload = {
            "size_w": self.toolbar.size_w.value(),
            "size_h": self.toolbar.size_h.value(),
            "unit": self._unit_name(),
            "grid_value": self.toolbar.grid_input.value(),
            "grid_enabled": self.toolbar.grid_check.isChecked(),
            "guide_enabled": self.toolbar.guide_check.isChecked(),
            "palette_colors": list(self.palette.palette_colors),
            "selected_palette_color": self.selected_palette_color,
            "active_tab": self.inspector_tabs.currentIndex(),
            "layers": self._history_entry_layers(),
            "stop_table_column_widths": list(self._stop_table_column_widths),
        }
        if include_ui:
            payload.update(
                {
                    "history_dialog_width": self._history_dialog_width,
                    "history_dialog_height": self._history_dialog_height,
                    "splitter_sizes": self.main_splitter.sizes(),
                }
            )
        return payload

    def _apply_history_entry_state(self, payload: dict):
        state = payload.get("state") if isinstance(payload.get("state"), dict) else payload
        layers_state = state.get("layers") if isinstance(state, dict) else None
        if not isinstance(state, dict) or not isinstance(layers_state, list):
            return
        self._selected_stop_index = None

        self.toolbar.size_h.setValue(max(1, int(state.get("size_h", 100))))
        self.toolbar.size_w.setValue(max(1, int(state.get("size_w", 100))))
        self.toolbar.grid_input.setValue(max(1, int(state.get("grid_value", 10))))
        self.toolbar.grid_check.setChecked(bool(state.get("grid_enabled", True)))
        self.toolbar.guide_check.setChecked(bool(state.get("guide_enabled", True)))
        unit = state.get("unit", "%")
        self.toolbar.set_unit_name(str(unit))
        column_widths = state.get("stop_table_column_widths")
        if isinstance(column_widths, list) and len(column_widths) == 4:
            try:
                self._stop_table_column_widths = [max(36, int(width)) for width in column_widths]
            except (TypeError, ValueError):
                self._stop_table_column_widths = [52, 48, 52, 42]
        self._apply_palette_state(state.get("palette_colors"), state.get("selected_palette_color", self.palette.palette_colors[0]))
        self._apply_layers_state(layers_state, int(state.get("active_tab", 0)))
        self._refresh_all()

    def _layer_default_name(self, kind: str) -> str:
        if kind == "background":
            return "b"
        prefix = {"linear": "L", "radial": "R", "conic": "C"}[kind]
        used = {layer.get("name", "") for layer in self.layers if layer.get("kind") == kind}
        if prefix not in used:
            return prefix
        index = 1
        while f"{prefix}{index}" in used:
            index += 1
        return f"{prefix}{index}"

    def _new_layer(self, kind: str) -> dict:
        if kind == "radial":
            return {
                "kind": kind,
                "name": self._layer_default_name(kind),
                "center_x": 50.0,
                "center_x_unit": "%",
                "center_y": 50.0,
                "center_y_unit": "%",
                "shape": "circle",
                "repeat": False,
                "stops": [],
                "muted": False,
            }
        return {"kind": kind, "name": self._layer_default_name(kind), "deg": 90, "deg_mode": "input", "repeat": False, "stops": [], "muted": False}

    def _new_background_layer(self) -> dict:
        return {"kind": "background", "name": "b", "color": "#00000000", "muted": False}

    def _active_layer(self) -> dict | None:
        index = self.inspector_tabs.currentIndex()
        if 0 <= index < len(self.layers):
            return self.layers[index]
        return None

    def _add_layer(self, kind: str, layer_data: dict | None = None):
        layer = dict(layer_data) if layer_data is not None else self._new_layer(kind)
        if kind == "background":
            self.layers.insert(0, layer)
        else:
            self.layers.append(layer)
        self._rebuild_inspector_tabs()
        self.inspector_tabs.setCurrentIndex(self.layers.index(layer))
        self._refresh_all()

    def _rebuild_inspector_tabs(self):
        self._building_tabs = True
        self.inspector_tabs.clear()
        for layer in self.layers:
            self.inspector_tabs.addTab(self._build_layer_inspector(layer), str(layer.get("name", "?")))
        self._building_tabs = False
        self._update_tab_visuals()

    def _build_layer_inspector(self, layer: dict) -> QWidget:
        kind = layer.get("kind")
        if kind == "background":
            return build_background_inspector(
                layer,
                self._on_background_value_edited,
                self._on_background_context_requested,
                self._on_background_color_dropped,
            )
        if kind == "linear":
            return build_linear_inspector(
                layer,
                self._format_stop_value,
                self._on_layer_deg_changed,
                self._on_layer_deg_mode_changed,
                self._on_layer_repeat_changed,
                self._on_stop_table_cell_clicked,
                self._on_stop_table_item_changed,
                self._on_stop_table_context_requested,
                self._on_stop_table_step_requested,
                self._on_stop_table_reorder_requested,
                self._on_stop_table_add_requested,
                self._on_stop_table_color_dropped,
                self._stop_table_column_widths,
                self._on_stop_table_column_resized,
            )
        if kind == "radial":
            return build_radial_inspector(
                layer,
                self._format_radial_position_value,
                self._on_radial_center_changed,
                self._on_radial_center_step_requested,
                self._on_radial_shape_changed,
                self._on_radial_center_unit_changed,
                self._on_layer_repeat_changed,
                self._on_stop_table_cell_clicked,
                self._on_stop_table_item_changed,
                self._on_stop_table_context_requested,
                self._on_stop_table_step_requested,
                self._on_stop_table_reorder_requested,
                self._on_stop_table_add_requested,
                self._on_stop_table_color_dropped,
                self._stop_table_column_widths,
                self._on_stop_table_column_resized,
            )
        return build_pending_inspector(str(kind))

    def _populate_stop_table(self, table: QTableWidget, layer: dict):
        self._table_syncing = True
        populate_linear_stop_table(table, layer, self._format_stop_value)
        for index, width in enumerate(self._stop_table_column_widths):
            table.setColumnWidth(index, width)
        if layer is self._active_layer() and self._selected_stop_index is not None:
            stops = list(layer.get("stops") or [])
            if 0 <= self._selected_stop_index < len(stops):
                current_column = table.currentColumn() if table.currentColumn() >= 0 else 0
                selected_item = table.item(self._selected_stop_index, min(current_column, table.columnCount() - 1))
                if selected_item is not None:
                    table.setCurrentItem(selected_item)
        self._table_syncing = False

    def _on_stop_table_column_resized(self, source_table: QTableWidget, section: int, width: int):
        width = max(36, int(width))
        if not (0 <= section < len(self._stop_table_column_widths)):
            return
        if self._stop_table_column_widths[section] == width:
            return
        self._stop_table_column_widths[section] = width
        for layer in self.layers:
            table = layer.get("_stop_table")
            if isinstance(table, QTableWidget) and table is not source_table and section < table.columnCount():
                table.blockSignals(True)
                table.setColumnWidth(section, width)
                table.blockSignals(False)
        self._save_state()

    def _linear_stops_css(self, layer: dict) -> str:
        return linear_stops_css(layer, self._format_stop_css_value)

    def _update_tab_visuals(self):
        tab_bar = self.inspector_tabs.tabBar()
        for index, layer in enumerate(self.layers):
            if index >= tab_bar.count():
                break
            muted = bool(layer.get("muted", False))
            tab_bar.setTabTextColor(index, QColor("#8a93a5") if muted else QColor("#e5e7eb"))
            tab_bar.setTabToolTip(index, "非表示中" if muted else "")

    def _set_background_color(self, layer: dict, color: str):
        layer["color"] = color
        color_value = layer.get("_background_color_value")
        if isinstance(color_value, QLineEdit):
            color_value.setText(display_color_text(color))
            style_color_value_widget(color_value, color)
        self._refresh_all()

    def _on_radial_center_changed(self, layer: dict, x_widget: QLineEdit, y_widget: QLineEdit):
        parsed_x = self._parse_radial_position_value(layer, x_widget.text(), "x")
        parsed_y = self._parse_radial_position_value(layer, y_widget.text(), "y")
        if parsed_x is None or parsed_y is None:
            x_widget.setText(self._format_radial_position_value(layer, "x"))
            y_widget.setText(self._format_radial_position_value(layer, "y"))
            return
        layer["center_x"] = parsed_x
        layer["center_y"] = parsed_y
        x_widget.setText(self._format_radial_position_value(layer, "x"))
        y_widget.setText(self._format_radial_position_value(layer, "y"))
        self._refresh_all()

    def _on_radial_center_step_requested(self, layer: dict, x_widget: QLineEdit, y_widget: QLineEdit, axis: str, delta: int):
        current = float(layer.get(f"center_{axis}", 0.0))
        current += delta
        if axis == "x":
            layer["center_x"] = current
        else:
            layer["center_y"] = current
        x_widget.setText(self._format_radial_position_value(layer, "x"))
        y_widget.setText(self._format_radial_position_value(layer, "y"))
        self._refresh_lightweight(layer)
        self._schedule_state_commit()

    def _on_radial_shape_changed(self, layer: dict, value: str):
        layer["shape"] = value
        self._refresh_all()

    def _on_radial_center_unit_changed(self, layer: dict, axis: str, value: str):
        old_unit = self._radial_axis_unit_name(layer, axis)
        if value == old_unit:
            return
        current = float(layer.get(f"center_{axis}", 0.0))
        converted = self._convert_between_units(current, old_unit, value, self._radial_span(layer, axis))
        layer[f"center_{axis}"] = converted
        layer[f"center_{axis}_unit"] = value
        self._refresh_all()

    def _move_radial_center_from_canvas(self, center_x: float, center_y: float):
        layer = self._active_layer()
        if not layer or layer.get("kind") != "radial":
            return
        layer["center_x"] = self._normalized_to_radial_axis_value(layer, "x", center_x)
        layer["center_y"] = self._normalized_to_radial_axis_value(layer, "y", center_y)
        self._refresh_all()

    def _on_background_value_edited(self, layer: dict, widget: QLineEdit):
        parsed = parse_color_text(widget.text())
        if parsed is None:
            widget.setText(display_color_text(str(layer.get("color", "#00000000"))))
            style_color_value_widget(widget, str(layer.get("color", "#00000000")))
            return
        self._set_background_color(layer, parsed)

    def _on_background_context_requested(self, layer: dict, widget: QLineEdit, pos: QPoint):
        menu = QMenu(widget)
        color_pick_action = menu.addAction("カラーピック")
        action = menu.exec(widget.mapToGlobal(pos))
        if action != color_pick_action:
            return
        dialog = SwatchDialog(str(layer.get("color", "#00000000")), self)
        if dialog.exec() != QDialog.Accepted:
            return
        self._set_background_color(layer, dialog.selected_color)

    def _on_background_color_dropped(self, layer: dict, color: str):
        parsed = parse_color_text(color)
        if parsed is None:
            return
        self._set_background_color(layer, parsed)

    def _apply_palette_to_background_from_canvas(self):
        layer = self._active_layer()
        if not layer or layer.get("kind") != "background":
            return
        self._set_background_color(layer, self.selected_palette_color)

    def _on_stop_table_item_changed(self, layer: dict, table: QTableWidget, item: QTableWidgetItem):
        if self._table_syncing:
            return
        stops = list(layer.get("stops") or [])
        if not (0 <= item.row() < len(stops)):
            self._populate_stop_table(table, layer)
            return
        color_item = table.item(item.row(), 0)
        alpha_item = table.item(item.row(), 1)
        value_item = table.item(item.row(), 2)
        unit_item = table.item(item.row(), 3)
        if color_item is None or alpha_item is None or value_item is None or unit_item is None:
            self._populate_stop_table(table, layer)
            return
        if item.column() == 3:
            new_unit = unit_item.text().strip().lower()
            if new_unit not in {"px", "%"}:
                self._populate_stop_table(table, layer)
                return
            stop = stops[item.row()]
            old_unit = self._stop_unit_name(layer, stop)
            if new_unit != old_unit:
                stop["position"] = self._convert_between_units(float(stop.get("position", 0.0)), old_unit, new_unit, self._stop_span(layer))
                stop["unit"] = new_unit
                layer["stops"] = stops
                self._refresh_all()
            else:
                self._populate_stop_table(table, layer)
            return
        if not update_stop_from_table(
            layer,
            item.row(),
            item.column(),
            color_item.text(),
            alpha_item.text(),
            value_item.text(),
            unit_item.text(),
            self._parse_stop_value,
        ):
            return
        self._refresh_all()

    def _on_stop_table_cell_clicked(self, layer: dict, table: QTableWidget, row: int, column: int):
        stops = list(layer.get("stops") or [])
        if not (0 <= row < len(stops)):
            return
        if column == 3:
            stop = stops[row]
            old_unit = self._stop_unit_name(layer, stop)
            new_unit = "%" if old_unit == "px" else "px"
            stop["position"] = self._convert_between_units(float(stop.get("position", 0.0)), old_unit, new_unit, self._stop_span(layer))
            stop["unit"] = new_unit
            layer["stops"] = stops
            self._selected_stop_index = row
            self._refresh_all()
            toggled_item = table.item(row, column)
            if toggled_item is not None:
                table.setCurrentItem(toggled_item)
            return
        self._selected_stop_index = row
        current_item = table.item(row, column)
        if current_item is not None:
            table.setCurrentItem(current_item)
        self.canvas.focus_stop(layer, row)
        self.canvas.ensure_stop_visible(layer, row)

    def _on_stop_table_context_requested(self, layer: dict, table: QTableWidget, pos: QPoint):
        item = table.itemAt(pos)
        if item is None:
            return
        stops = list(layer.get("stops") or [])
        if not (0 <= item.row() < len(stops)):
            return
        menu = QMenu(table)
        color_pick_action = menu.addAction("カラーピック")
        mute_action = menu.addAction("再表示" if stops[item.row()].get("muted", False) else "非表示")
        duplicate_action = menu.addAction("複製")
        delete_action = menu.addAction("削除")
        action = menu.exec(table.viewport().mapToGlobal(pos))
        if action == color_pick_action:
            dialog = SwatchDialog(str(stops[item.row()].get("color", "#ffffff")), self)
            if dialog.exec() != QDialog.Accepted:
                return
            set_stop_color(layer, item.row(), dialog.selected_color)
            self._refresh_all()
            return
        if action == mute_action:
            toggle_stop_muted(layer, item.row())
            self._refresh_all()
            return
        if action == duplicate_action:
            duplicate_stop(layer, item.row())
            self._refresh_all()
            return
        if action == delete_action:
            delete_stop(layer, item.row())
            self._refresh_all()

    def _on_stop_table_step_requested(self, layer: dict, table: QTableWidget, row: int, column: int, delta: int):
        if not step_stop(layer, row, column, delta):
            return
        self._selected_stop_index = row
        self._refresh_lightweight(layer)
        self._schedule_state_commit()
        current_item = table.item(row, column)
        if current_item is not None:
            table.setCurrentItem(current_item)

    def _on_stop_table_reorder_requested(self, layer: dict, source_row: int, target_row: int):
        if not reorder_stop(layer, source_row, target_row):
            return
        if self._selected_stop_index == source_row:
            self._selected_stop_index = target_row
        elif self._selected_stop_index is not None:
            if source_row < self._selected_stop_index <= target_row:
                self._selected_stop_index -= 1
            elif target_row <= self._selected_stop_index < source_row:
                self._selected_stop_index += 1
        self._refresh_all()
        table = layer.get("_stop_table")
        if isinstance(table, QTableWidget):
            target_item = table.item(target_row, 0)
            if target_item is not None:
                table.setCurrentItem(target_item)

    def _on_stop_table_add_requested(self, layer: dict):
        append_stop_after_last(layer, self.selected_palette_color, self._default_stop_unit(layer))
        self._selected_stop_index = len(layer.get("stops", [])) - 1
        self._refresh_all()

    def _on_stop_table_color_dropped(self, layer: dict, row: int, color: str):
        if not set_stop_color(layer, row, color):
            return
        self._selected_stop_index = row
        self._refresh_all()

    def _refresh_active_table(self):
        layer = self._active_layer()
        if layer and layer.get("kind") in ("linear", "radial"):
            table = layer.get("_stop_table")
            if isinstance(table, QTableWidget):
                self._populate_stop_table(table, layer)

    def _refresh_lightweight(self, target_layer: dict | None = None):
        self.palette.select_color(self.selected_palette_color)
        self._update_tab_visuals()
        if target_layer is not None:
            table = target_layer.get("_stop_table")
            if isinstance(table, QTableWidget):
                self._populate_stop_table(table, target_layer)
            if target_layer.get("kind") == "radial":
                x_widget = target_layer.get("_radial_cx_input")
                y_widget = target_layer.get("_radial_cy_input")
                if isinstance(x_widget, QLineEdit):
                    x_widget.setText(self._format_radial_position_value(target_layer, "x"))
                if isinstance(y_widget, QLineEdit):
                    y_widget.setText(self._format_radial_position_value(target_layer, "y"))
        self._refresh_code()
        self.canvas.update()

    def _on_layer_deg_changed(self, layer: dict, value: int):
        layer["deg"] = value
        self._refresh_all()

    def _on_layer_deg_mode_changed(self, layer: dict, mode: str):
        layer["deg_mode"] = mode
        self._refresh_all()

    def _on_layer_repeat_changed(self, layer: dict, checked: bool):
        layer["repeat"] = checked
        self._refresh_all()

    def _add_stop_from_canvas(self, position: float):
        layer = self._active_layer()
        if not layer or layer.get("kind") not in ("linear", "radial"):
            return
        stop_unit = self._default_stop_unit(layer)
        append_stop(layer, self.selected_palette_color, self._normalized_to_stop_value(layer, position, stop_unit), stop_unit)
        self._selected_stop_index = len(layer.get("stops", [])) - 1
        self._refresh_all()

    def _move_stop_from_canvas(self, index: int, position: float):
        layer = self._active_layer()
        if not layer or layer.get("kind") not in ("linear", "radial"):
            return
        stops = list(layer.get("stops") or [])
        if not (0 <= index < len(stops)):
            return
        stop_unit = self._stop_unit_name(layer, stops[index])
        if not move_stop(layer, index, self._normalized_to_stop_value(layer, position, stop_unit)):
            return
        self._selected_stop_index = index
        self._refresh_all()

    def _delete_stop_from_canvas(self, index: int):
        layer = self._active_layer()
        if not layer or layer.get("kind") not in ("linear", "radial"):
            return
        if not delete_stop(layer, index):
            return
        stops = list(layer.get("stops") or [])
        if not stops:
            self._selected_stop_index = None
        elif self._selected_stop_index is not None:
            self._selected_stop_index = max(0, min(self._selected_stop_index, len(stops) - 1))
        self._refresh_all()

    def _gradient_css(self, layer: dict) -> str:
        kind = layer.get("kind")
        if kind == "linear":
            repeat_prefix = "repeating-" if layer.get("repeat") else ""
            stops_text = self._linear_stops_css(layer)
            deg_mode = str(layer.get("deg_mode", "input"))
            deg_text = deg_mode if deg_mode != "input" else f"{int(layer.get('deg', 90))}deg"
            return f"{repeat_prefix}linear-gradient({deg_text}, {stops_text})"
        if kind == "radial":
            repeat_prefix = "repeating-" if layer.get("repeat") else ""
            cx = self._format_radial_position_css(layer, "x")
            cy = self._format_radial_position_css(layer, "y")
            stops_text = self._linear_stops_css(layer)
            shape = str(layer.get("shape", "circle"))
            return f"{repeat_prefix}radial-gradient({shape} at {cx} {cy}, {stops_text})"
        return "conic-gradient(/* pending */)"

    def _refresh_code(self):
        code_layers = [layer for layer in self.layers if layer.get("kind") != "background" and not layer.get("muted", False)]
        if not code_layers:
            self.copy_feedback_base_text = "background: none;"
            self._code_full_text = self.copy_feedback_base_text
            self._update_code_label_layout(reset_scroll=True)
            return
        self.copy_feedback_base_text = f"background: {', '.join(self._gradient_css(layer) for layer in reversed(code_layers))};"
        self._code_full_text = self.copy_feedback_base_text
        self._update_code_label_layout(reset_scroll=True)

    def _refresh_all(self):
        self.palette.select_color(self.selected_palette_color)
        self._update_tab_visuals()
        for layer in self.layers:
            if layer.get("kind") == "radial":
                x_widget = layer.get("_radial_cx_input")
                y_widget = layer.get("_radial_cy_input")
                shape_select = layer.get("_radial_shape_select")
                x_unit_toggle = layer.get("_radial_cx_unit_toggle")
                y_unit_toggle = layer.get("_radial_cy_unit_toggle")
                if isinstance(x_widget, QLineEdit):
                    x_widget.setText(self._format_radial_position_value(layer, "x"))
                if isinstance(y_widget, QLineEdit):
                    y_widget.setText(self._format_radial_position_value(layer, "y"))
                if shape_select is not None and getattr(shape_select, "currentText", None):
                    if shape_select.currentText() != str(layer.get("shape", "circle")):
                        shape_select.setCurrentText(str(layer.get("shape", "circle")))
                if isinstance(x_unit_toggle, QPushButton):
                    x_unit_toggle.setText(str(layer.get("center_x_unit", "%")))
                if isinstance(y_unit_toggle, QPushButton):
                    y_unit_toggle.setText(str(layer.get("center_y_unit", "%")))
            table = layer.get("_stop_table")
            if isinstance(table, QTableWidget):
                self._populate_stop_table(table, layer)
        self._refresh_code()
        self.canvas.update()
        self._save_state()
        self._record_undo_snapshot()

    def _on_ui_changed(self, *_):
        self._refresh_cursor_text()
        self._refresh_all()

    def _on_tab_changed(self, *_):
        layer = self._active_layer()
        if not layer or layer.get("kind") not in ("linear", "radial"):
            self._selected_stop_index = None
        else:
            stops = list(layer.get("stops") or [])
            if self._selected_stop_index is not None and not (0 <= self._selected_stop_index < len(stops)):
                self._selected_stop_index = None
        if not self._building_tabs:
            self._refresh_all()

    def _on_tab_moved(self, from_index: int, to_index: int):
        if self._building_tabs or from_index == to_index:
            return
        if from_index == 0 or to_index == 0:
            self._rebuild_inspector_tabs()
            self.inspector_tabs.setCurrentIndex(0)
            return
        layer = self.layers.pop(from_index)
        self.layers.insert(to_index, layer)
        self._refresh_all()

    def _show_layer_tab_menu(self, pos):
        tab_bar = self.inspector_tabs.tabBar()
        index = tab_bar.tabAt(pos)
        if index < 0 or not (0 <= index < len(self.layers)):
            return
        layer = self.layers[index]
        menu = QMenu(tab_bar)
        mute_action = menu.addAction("再表示" if layer.get("muted", False) else "非表示")
        close_action = menu.addAction("タブを閉じる")
        if layer.get("kind") == "background":
            close_action.setEnabled(False)
        action = menu.exec(tab_bar.mapToGlobal(pos))
        if action == mute_action:
            layer["muted"] = not bool(layer.get("muted", False))
            self._refresh_all()
            return
        if action == close_action and close_action.isEnabled():
            self._close_layer_tab(index)

    def _close_layer_tab(self, index: int):
        if not (0 <= index < len(self.layers)) or self.layers[index].get("kind") == "background":
            return
        self.layers.pop(index)
        self._rebuild_inspector_tabs()
        self.inspector_tabs.setCurrentIndex(max(0, min(index - 1, self.inspector_tabs.count() - 1)))
        self._refresh_all()

    def _restore_state(self):
        self.selected_palette_color = self.palette_colors[0]
        if not self.state_path or not self.state_path.exists():
            self._add_layer("background", self._new_background_layer())
            return
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            self._add_layer("background", self._new_background_layer())
            return
        if not isinstance(state, dict):
            self._add_layer("background", self._new_background_layer())
            return

        self.toolbar.size_h.setValue(max(1, int(state.get("size_h", 100))))
        self.toolbar.size_w.setValue(max(1, int(state.get("size_w", 100))))
        self.toolbar.grid_input.setValue(max(1, int(state.get("grid_value", 10))))
        self.toolbar.grid_check.setChecked(bool(state.get("grid_enabled", True)))
        self.toolbar.guide_check.setChecked(bool(state.get("guide_enabled", True)))
        self._history_dialog_width = max(320, int(state.get("history_dialog_width", self.DEFAULT_HISTORY_DIALOG_WIDTH)))
        self._history_dialog_height = max(240, int(state.get("history_dialog_height", self.DEFAULT_HISTORY_DIALOG_HEIGHT)))
        splitter_sizes = state.get("splitter_sizes")
        if isinstance(splitter_sizes, list) and len(splitter_sizes) == 2:
            try:
                self.main_splitter.setSizes([max(1, int(splitter_sizes[0])), max(1, int(splitter_sizes[1]))])
            except (TypeError, ValueError):
                pass
        unit = state.get("unit", "%")
        self.toolbar.set_unit_name(str(unit))

        self._apply_palette_state(state.get("palette_colors"), state.get("selected_palette_color", self.palette_colors[0]))
        self._apply_layers_state(state.get("layers", []), int(state.get("active_tab", 0)))

    def _save_state(self):
        if not self.state_path:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._state_payload(include_ui=True)
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _reset_state(self):
        self._selected_stop_index = None
        self.toolbar.size_h.setValue(100)
        self.toolbar.size_w.setValue(100)
        self.toolbar.set_unit_name("%")
        self.toolbar.grid_input.setValue(10)
        self.toolbar.grid_check.setChecked(True)
        self.toolbar.guide_check.setChecked(True)
        self._stop_table_column_widths = [52, 48, 52, 42]
        self.layers = []
        self.inspector_tabs.clear()
        self._add_layer("background", self._new_background_layer())
        self._set_cursor_text(self._default_cursor_text())
        self._refresh_all()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._update_code_label_layout()

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        QTimer.singleShot(0, lambda: self._update_code_label_layout(reset_scroll=True))

    def _code_max_scroll_offset(self, text: str, available_width: int, font_metrics) -> int:
        if font_metrics.horizontalAdvance(text) <= available_width:
            return 0
        for offset in range(len(text)):
            candidate = f"{'...' if offset > 0 else ''}{text[offset:]}"
            if font_metrics.horizontalAdvance(candidate) <= available_width:
                return offset
        return max(0, len(text) - 1)

    def _code_display_text(self, text: str, offset: int, available_width: int, font_metrics) -> tuple[str, bool]:
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
        metrics = self.footer.code_label.fontMetrics()
        available_width = max(1, self.footer.code_label.width() - 8)
        if reset_scroll:
            self._code_scroll_offset = 0
        if metrics.horizontalAdvance(text) <= available_width:
            self.footer.code_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.footer.code_label.setText(text)
            self.footer.code_label.setCursorPosition(0)
            self._code_scroll_offset = 0
            return
        self.footer.code_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        max_offset = self._code_max_scroll_offset(text, available_width, metrics)
        self._code_scroll_offset = max(0, min(self._code_scroll_offset, max_offset))
        display_text, _ = self._code_display_text(text, self._code_scroll_offset, available_width, metrics)
        self.footer.code_label.setText(display_text)
        self.footer.code_label.setCursorPosition(0)

    def _on_code_wheel(self, event: QWheelEvent):
        if not self._code_full_text:
            event.ignore()
            return
        metrics = self.footer.code_label.fontMetrics()
        available_width = max(1, self.footer.code_label.width() - 8)
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

    def _load_history_entries(self) -> list[dict]:
        if not self.history_path or not self.history_path.exists():
            return []
        try:
            loaded = json.loads(self.history_path.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError:
            return []
        entries: list[dict] = []
        for item in loaded:
            if isinstance(item, str):
                entries.append({"code": item})
            elif isinstance(item, dict) and isinstance(item.get("code"), str):
                entries.append(item)
        return entries

    def _save_history_entry(self, code: str):
        if not self.history_path:
            return
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        entries = self._load_history_entries()
        entry = {"code": code, "layers": self._history_entry_layers(), "state": self._history_entry_state()}
        if entries and entries[0].get("code") == code:
            return
        entries.insert(0, entry)
        self.history_path.write_text(json.dumps(entries[: self.MAX_HISTORY], ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_current_to_history(self):
        self._save_history_entry(self.copy_feedback_base_text)

    def _on_code_clicked(self, _event):
        code = self.copy_feedback_base_text
        QApplication.clipboard().setText(code)
        self._save_history_entry(code)
        self._code_full_text = "copy and saved"
        self.footer.code_label.setStyleSheet("color: #4ecdc4; background: transparent; border: none;")
        self._update_code_label_layout(reset_scroll=True)

        def _restore():
            self._code_full_text = self.copy_feedback_base_text
            self.footer.code_label.setStyleSheet("background: transparent; border: none;")
            self._update_code_label_layout(reset_scroll=True)

        QTimer.singleShot(700, _restore)

    def _show_history_dialog(self):
        items = self._load_history_entries()
        if not items:
            QMessageBox.information(self, "履歴", "履歴がありません")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Gradient History")
        layout = QVBoxLayout(dlg)
        lst = QListWidget()
        lst.setContextMenuPolicy(Qt.CustomContextMenu)
        lst.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        lst.verticalScrollBar().setSingleStep(12)
        preview_size = QSize(96, 96)
        row_widgets: dict[int, GradientHistoryItemWidget] = {}
        for entry in items:
            code = entry.get("code")
            if not isinstance(code, str):
                continue
            item = QListWidgetItem()
            item.setData(Qt.UserRole, entry)
            lst.addItem(item)
            widget = GradientHistoryItemWidget(render_history_preview_pixmap(entry, preview_size, self.canvas), code)
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
                preview_lines = build_history_preview_lines(widget.base_code_text, code_width, 3, lst.font(), metrics)
                widget.set_text_width(code_width)
                widget.set_preview_lines(preview_lines)
                code_height = history_preview_height(metrics, widget.line_count())
                item.setSizeHint(QSize(lst.viewport().width(), max(preview_size.height(), code_height) + 16))

        def resize_event(event):
            QDialog.resizeEvent(dlg, event)
            relayout_items()

        dlg.resizeEvent = resize_event

        def on_item_clicked(it: QListWidgetItem):
            payload = it.data(Qt.UserRole)
            code = payload.get("code") if isinstance(payload, dict) else None
            if not isinstance(code, str):
                return
            QApplication.clipboard().setText(code)
            clicked_widget = row_widgets.get(id(it))
            if clicked_widget is not None:
                clicked_widget.set_feedback_text("copy and send")

                def _restore_feedback(widget: GradientHistoryItemWidget = clicked_widget):
                    if widget in row_widgets.values():
                        relayout_items()

                QTimer.singleShot(900, _restore_feedback)
            if isinstance(payload, dict):
                self._apply_history_entry_state(payload)

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
            if self.history_path:
                self.history_path.parent.mkdir(parents=True, exist_ok=True)
                self.history_path.write_text(json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8")

        lst.itemClicked.connect(on_item_clicked)
        lst.customContextMenuRequested.connect(on_context_menu)
        dlg.resize(self._history_dialog_width, self._history_dialog_height)

        def persist_history_dialog_size(_result: int):
            self._history_dialog_width = max(320, dlg.width())
            self._history_dialog_height = max(240, dlg.height())
            self._save_state()

        dlg.finished.connect(persist_history_dialog_size)
        QTimer.singleShot(0, relayout_items)
        dlg.exec()
