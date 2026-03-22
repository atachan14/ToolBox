from __future__ import annotations

import json
import math
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPixmap, QResizeEvent, QTextLayout, QWheelEvent
from PySide6.QtWidgets import QApplication, QAbstractItemView, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from .canvas import GradientCanvas, GradientCanvasConfig
from .color_utils import combine_color_and_alpha, display_color_text, parse_color_text, split_color_and_alpha
from .footer import GradientFooter
from .layer_panels import build_background_inspector, build_linear_inspector, build_pending_inspector, populate_linear_stop_table, style_color_value_widget
from .palette_data_window import PaletteDataWindow
from .palette import GradientPalette
from .palette_storage import delete_palette, load_palettes, palette_dir, rename_palette, save_palette
from .toolbar import GradientToolbar
from .widgets import SwatchDialog


class GradientHistoryItemWidget(QWidget):
    def __init__(self, pixmap: QPixmap, code_text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._pixmap = pixmap
        self.base_code_text = code_text
        self._display_lines = [code_text]
        self._display_color = QColor(self.palette().color(self.foregroundRole()))
        self._text_width = 120

    def set_text_width(self, width: int):
        self._text_width = width
        self.update()

    def set_preview_lines(self, lines: list[str]):
        self._display_lines = lines or [""]
        self._display_color = QColor(self.palette().color(self.foregroundRole()))
        self.update()

    def set_feedback_text(self, text: str):
        self._display_lines = [text]
        self._display_color = QColor("#4ecdc4")
        self.update()

    def line_count(self) -> int:
        return max(1, len(self._display_lines) or 1)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        metrics = painter.fontMetrics()
        margin = 8
        gap = 10
        painter.drawPixmap(margin, margin, self._pixmap)
        painter.setPen(self._display_color)
        text_x = margin + self._pixmap.width() + gap
        line_y = margin + metrics.ascent()
        for line in self._display_lines:
            painter.drawText(text_x, line_y, line)
            line_y += metrics.lineSpacing()


class GradientWindow(QMainWindow):
    MAX_HISTORY = 100
    DEFAULT_HISTORY_DIALOG_WIDTH = 620
    DEFAULT_HISTORY_DIALOG_HEIGHT = 360
    PALETTE_COLORS = [
        "#00000000",
        "#000000",
        "#ffffff",
    ]

    parse_color_text = staticmethod(parse_color_text)

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
                active_palette_color_getter=lambda: self.selected_palette_color,
                cursor_changed=self._set_cursor_text,
                background_clicked=self._apply_palette_to_background_from_canvas,
                linear_stop_hovered=self._set_hover_position,
                linear_stop_clicked=self._add_stop_from_canvas,
                linear_stop_moved=self._move_stop_from_canvas,
                linear_stop_deleted=self._delete_stop_from_canvas,
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

        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        self.reset_button = QPushButton("Reset")
        self.show_history_button = QPushButton("履歴を表示")
        self.reset_button.setFixedHeight(self._toolbar_button_height)
        self.show_history_button.setFixedHeight(self._toolbar_button_height)
        buttons.addWidget(self.reset_button)
        buttons.addWidget(self.show_history_button)
        right_layout.addLayout(buttons)

        self.main_splitter.addWidget(right)
        left.setMinimumWidth(100)
        right.setMinimumWidth(150)
        self.main_splitter.setSizes([420, 180])

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
        self.show_history_button.clicked.connect(self._show_history_dialog)
        self.main_splitter.splitterMoved.connect(lambda *_: self._save_state())

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

    def _format_stop_value(self, layer: dict, position: float) -> str:
        def _compact(number: float) -> str:
            return str(int(round(number))) if abs(number - round(number)) < 1e-9 else f"{number:.2f}"
        if self._unit_name() == "px":
            return f"{_compact(position * self._gradient_span(float(layer.get('deg', 90))))}px"
        return f"{_compact(position * 100.0)}%"

    def _parse_stop_value(self, layer: dict, text: str) -> float | None:
        value_text = text.strip().lower()
        if not value_text:
            return None
        unit = self._unit_name()
        try:
            if value_text.endswith("px"):
                numeric = float(value_text[:-2].strip())
                return numeric / self._gradient_span(float(layer.get("deg", 90)))
            if value_text.endswith("%"):
                numeric = float(value_text[:-1].strip())
                return numeric / 100.0
            numeric = float(value_text)
        except ValueError:
            return None
        if unit == "px":
            return numeric / self._gradient_span(float(layer.get("deg", 90)))
        return numeric / 100.0

    def _set_cursor_text(self, text: str):
        self.footer.set_cursor_text(text)

    def _set_hover_position(self, position: float | None):
        self._hover_position = position
        layer = self._active_layer()
        if position is not None and layer and layer.get("kind") == "linear":
            self.footer.set_cursor_text(f"Cursor: value={self._format_stop_value(layer, position)}")
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
        return [
            {
                "kind": layer.get("kind", "linear"),
                "deg": int(layer.get("deg", 90)),
                "repeat": bool(layer.get("repeat", False)),
                "muted": bool(layer.get("muted", False)),
                "color": str(layer.get("color", "#00000000")),
                "stops": [
                    {
                        "color": str(stop.get("color", "#ffffff")),
                        "position": float(stop.get("position", 0.0)),
                        "muted": bool(stop.get("muted", False)),
                    }
                    for stop in layer.get("stops") or []
                ],
            }
            for layer in self.layers
        ]

    def _history_entry_state(self) -> dict:
        return {
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
        }

    def _apply_history_entry_state(self, payload: dict):
        state = payload.get("state") if isinstance(payload.get("state"), dict) else payload
        layers_state = state.get("layers") if isinstance(state, dict) else None
        if not isinstance(state, dict) or not isinstance(layers_state, list):
            return

        self.toolbar.size_h.setValue(max(1, int(state.get("size_h", 100))))
        self.toolbar.size_w.setValue(max(1, int(state.get("size_w", 100))))
        self.toolbar.grid_input.setValue(max(1, int(state.get("grid_value", 10))))
        self.toolbar.grid_check.setChecked(bool(state.get("grid_enabled", True)))
        self.toolbar.guide_check.setChecked(bool(state.get("guide_enabled", True)))
        unit = state.get("unit", "%")
        self.toolbar.unit_px.setChecked(unit == "px")
        self.toolbar.unit_percent.setChecked(unit != "px")

        palette_state = state.get("palette_colors")
        if isinstance(palette_state, list) and palette_state:
            colors = [parse_color_text(str(color)) or "#00000000" for color in palette_state]
            self.palette_colors = colors
            self.palette.set_palette_colors(colors)
        selected_palette = str(state.get("selected_palette_color", self.palette.palette_colors[0]))
        if selected_palette in self.palette.palette_colors:
            self.selected_palette_color = selected_palette
            self.palette.select_color(selected_palette)
        else:
            self.selected_palette_color = self.palette.palette_colors[0]
            self.palette.select_index(0)

        self.layers = []
        self.inspector_tabs.clear()
        for item in layers_state:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind", "linear"))
            default_name = "b" if kind == "background" else self._layer_default_name(kind)
            self._add_layer(
                kind,
                {
                    "kind": kind,
                    "name": str(item.get("name", default_name)),
                    "deg": int(item.get("deg", 90)),
                    "repeat": bool(item.get("repeat", False)),
                    "muted": bool(item.get("muted", False)),
                    "color": parse_color_text(str(item.get("color", "#00000000"))) or "#00000000",
                    "stops": [
                        {
                            "color": parse_color_text(str(stop.get("color", "#ffffff"))) or "#ffffff",
                            "position": float(stop.get("position", 0.0)),
                            "muted": bool(stop.get("muted", False)),
                        }
                        for stop in item.get("stops", [])
                        if isinstance(stop, dict)
                    ],
                },
            )
        if not self.layers or self.layers[0].get("kind") != "background":
            self.layers.insert(0, self._new_background_layer())
            self._rebuild_inspector_tabs()
        if self.inspector_tabs.count() > 0:
            self.inspector_tabs.setCurrentIndex(max(0, min(int(state.get("active_tab", 0)), self.inspector_tabs.count() - 1)))
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
        return {"kind": kind, "name": self._layer_default_name(kind), "deg": 90, "repeat": False, "stops": [], "muted": False}

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
            return build_background_inspector(layer)
        if kind == "linear":
            return build_linear_inspector(
                layer,
                self._format_stop_value,
                self._on_layer_deg_changed,
                self._on_layer_repeat_changed,
                self._on_stop_table_item_changed,
                self._on_stop_table_context_requested,
                self._on_stop_table_step_requested,
                self._on_stop_table_reorder_requested,
                self._on_stop_table_add_requested,
                self._on_stop_table_color_dropped,
            )
        return build_pending_inspector(str(kind))

    def _populate_stop_table(self, table: QTableWidget, layer: dict):
        self._table_syncing = True
        populate_linear_stop_table(table, layer, self._format_stop_value)
        self._table_syncing = False

    def _visible_stops(self, layer: dict) -> list[dict]:
        return [stop for stop in (layer.get("stops") or []) if not stop.get("muted", False)]

    def _linear_stops_css(self, layer: dict, stops: list[dict]) -> str:
        if not stops:
            return "rgba(0, 0, 0, 0) 0%, rgba(0, 0, 0, 0) 100%"
        parts: list[str] = []
        run_color = str(stops[0].get("color", "#ffffff"))
        run_start = float(stops[0].get("position", 0.0))
        run_end = run_start
        for stop in stops[1:]:
            color = str(stop.get("color", "#ffffff"))
            position = float(stop.get("position", 0.0))
            if color == run_color:
                run_end = position
                continue
            color_text = display_color_text(run_color)
            if abs(run_end - run_start) <= 1e-9:
                parts.append(f"{color_text} {self._format_stop_value(layer, run_start)}")
            else:
                parts.append(f"{color_text} {self._format_stop_value(layer, run_start)} {self._format_stop_value(layer, run_end)}")
            run_color = color
            run_start = position
            run_end = position
        color_text = display_color_text(run_color)
        if abs(run_end - run_start) <= 1e-9:
            parts.append(f"{color_text} {self._format_stop_value(layer, run_start)}")
        else:
            parts.append(f"{color_text} {self._format_stop_value(layer, run_start)} {self._format_stop_value(layer, run_end)}")
        return ", ".join(parts)

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
            return
        if item.column() == 3:
            parsed = self._parse_stop_value(layer, item.text())
            if parsed is None:
                self._populate_stop_table(table, layer)
                return
            stops[item.row()]["position"] = parsed
        elif item.column() in (1, 2):
            color_item = table.item(item.row(), 1)
            alpha_item = table.item(item.row(), 2)
            if color_item is None or alpha_item is None:
                self._populate_stop_table(table, layer)
                return
            combined = combine_color_and_alpha(color_item.text(), alpha_item.text())
            if combined is None:
                self._populate_stop_table(table, layer)
                return
            stops[item.row()]["color"] = combined
        else:
            return
        layer["stops"] = stops
        self._refresh_all()

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
            stops[item.row()]["color"] = dialog.selected_color
            layer["stops"] = stops
            self._refresh_all()
            return
        if action == mute_action:
            stops[item.row()]["muted"] = not bool(stops[item.row()].get("muted", False))
            layer["stops"] = stops
            self._refresh_all()
            return
        if action == duplicate_action:
            duplicate = {
                "color": str(stops[item.row()].get("color", "#ffffff")),
                "position": float(stops[item.row()].get("position", 0.0)),
                "muted": bool(stops[item.row()].get("muted", False)),
            }
            stops.insert(item.row() + 1, duplicate)
            layer["stops"] = stops
            self._refresh_all()
            return
        if action == delete_action:
            stops.pop(item.row())
            layer["stops"] = stops
            self._refresh_all()

    def _on_stop_table_step_requested(self, layer: dict, table: QTableWidget, row: int, column: int, delta: int):
        stops = list(layer.get("stops") or [])
        if not (0 <= row < len(stops)):
            return
        if column == 2:
            color_text, alpha_text = split_color_and_alpha(str(stops[row].get("color", "#ffffff")))
            current_alpha = alpha_text[:-1] if alpha_text.endswith("%") else alpha_text
            try:
                alpha = float(current_alpha)
            except ValueError:
                alpha = 100.0
            combined = combine_color_and_alpha(color_text, f"{max(0.0, min(100.0, alpha + delta))}%")
            if combined is None:
                return
            stops[row]["color"] = combined
        elif column == 3:
            current = float(stops[row].get("position", 0.0))
            if self._unit_name() == "px":
                current = current + (delta / self._gradient_span(float(layer.get("deg", 90))))
            else:
                current = current + (delta / 100.0)
            stops[row]["position"] = current
        else:
            return
        layer["stops"] = stops
        self._refresh_all()
        current_item = table.item(row, column)
        if current_item is not None:
            table.setCurrentItem(current_item)

    def _on_stop_table_reorder_requested(self, layer: dict, source_row: int, target_row: int):
        stops = list(layer.get("stops") or [])
        if not (0 <= source_row < len(stops) and 0 <= target_row < len(stops)):
            return
        stop = stops.pop(source_row)
        stops.insert(target_row, stop)
        layer["stops"] = stops
        self._refresh_all()
        table = layer.get("_stop_table")
        if isinstance(table, QTableWidget):
            target_item = table.item(target_row, 1) or table.item(target_row, 0)
            if target_item is not None:
                table.setCurrentItem(target_item)

    def _on_stop_table_add_requested(self, layer: dict):
        stops = list(layer.get("stops") or [])
        if stops:
            last_position = float(stops[-1].get("position", 0.0))
            if self._unit_name() == "px":
                increment = 1.0 / self._gradient_span(float(layer.get("deg", 90)))
            else:
                increment = 0.01
            position = last_position + increment
        else:
            position = 0.0
        stops.append({"color": self.selected_palette_color, "position": position, "muted": False})
        layer["stops"] = stops
        self._refresh_all()

    def _on_stop_table_color_dropped(self, layer: dict, row: int, color: str):
        stops = list(layer.get("stops") or [])
        if not (0 <= row < len(stops)):
            return
        parsed = parse_color_text(color)
        if parsed is None:
            return
        stops[row]["color"] = parsed
        layer["stops"] = stops
        self._refresh_all()

    def _refresh_active_table(self):
        layer = self._active_layer()
        if layer and layer.get("kind") == "linear":
            table = layer.get("_stop_table")
            if isinstance(table, QTableWidget):
                self._populate_stop_table(table, layer)

    def _on_layer_deg_changed(self, layer: dict, value: int):
        layer["deg"] = value
        self._refresh_all()

    def _on_layer_repeat_changed(self, layer: dict, checked: bool):
        layer["repeat"] = checked
        self._refresh_all()

    def _add_stop_from_canvas(self, position: float):
        layer = self._active_layer()
        if not layer or layer.get("kind") != "linear":
            return
        layer.setdefault("stops", []).append({"color": self.selected_palette_color, "position": float(position), "muted": False})
        self._refresh_all()

    def _move_stop_from_canvas(self, index: int, position: float):
        layer = self._active_layer()
        if not layer or layer.get("kind") != "linear":
            return
        stops = list(layer.get("stops") or [])
        if not (0 <= index < len(stops)):
            return
        stops[index]["position"] = float(position)
        layer["stops"] = stops
        self._refresh_all()

    def _delete_stop_from_canvas(self, index: int):
        layer = self._active_layer()
        if not layer or layer.get("kind") != "linear":
            return
        stops = list(layer.get("stops") or [])
        if not (0 <= index < len(stops)):
            return
        stops.pop(index)
        layer["stops"] = stops
        self._refresh_all()

    def _gradient_css(self, layer: dict) -> str:
        kind = layer.get("kind")
        if kind == "linear":
            repeat_prefix = "repeating-" if layer.get("repeat") else ""
            stops = self._visible_stops(layer)
            stops_text = self._linear_stops_css(layer, stops)
            return f"{repeat_prefix}linear-gradient({int(layer.get('deg', 90))}deg, {stops_text})"
        if kind == "radial":
            return "radial-gradient(/* pending */)"
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
            table = layer.get("_stop_table")
            if isinstance(table, QTableWidget):
                self._populate_stop_table(table, layer)
        self._refresh_code()
        self.canvas.update()
        self._save_state()

    def _on_ui_changed(self, *_):
        self._refresh_all()

    def _on_tab_changed(self, *_):
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

    def _serialize_layers(self) -> list[dict]:
        return [
            {
                "kind": layer.get("kind", "linear"),
                "name": layer.get("name", "L"),
                "deg": int(layer.get("deg", 90)),
                "repeat": bool(layer.get("repeat", False)),
                "muted": bool(layer.get("muted", False)),
                "color": str(layer.get("color", "#00000000")),
                "stops": [
                    {
                        "color": str(stop.get("color", "#ffffff")),
                        "position": float(stop.get("position", 0.0)),
                        "muted": bool(stop.get("muted", False)),
                    }
                    for stop in layer.get("stops") or []
                ],
            }
            for layer in self.layers
        ]

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
        self.toolbar.unit_px.setChecked(unit == "px")
        self.toolbar.unit_percent.setChecked(unit != "px")

        palette_state = state.get("palette_colors")
        if isinstance(palette_state, list) and palette_state:
            colors: list[str] = []
            for color in palette_state:
                parsed = self.parse_color_text(str(color))
                colors.append(parsed if parsed is not None else "#00000000")
            self.palette_colors = colors
            self.palette.set_palette_colors(colors)
        selected_palette = str(state.get("selected_palette_color", self.palette_colors[0]))
        if selected_palette in self.palette.palette_colors:
            self.selected_palette_color = selected_palette
            self.palette.select_color(selected_palette)
        else:
            self.selected_palette_color = self.palette.palette_colors[0]
            self.palette.select_index(0)

        for item in state.get("layers", []):
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind", "linear"))
            default_name = "b" if kind == "background" else self._layer_default_name(kind)
            self._add_layer(
                kind,
                {
                    "kind": kind,
                    "name": str(item.get("name", default_name)),
                    "deg": int(item.get("deg", 90)),
                    "repeat": bool(item.get("repeat", False)),
                    "muted": bool(item.get("muted", False)),
                    "color": parse_color_text(str(item.get("color", "#00000000"))) or "#00000000",
                    "stops": [
                        {
                            "color": parse_color_text(str(stop.get("color", "#ffffff"))) or "#ffffff",
                            "position": float(stop.get("position", 0.0)),
                            "muted": bool(stop.get("muted", False)),
                        }
                        for stop in item.get("stops", [])
                        if isinstance(stop, dict)
                    ],
                },
            )

        if not self.layers or self.layers[0].get("kind") != "background":
            self.layers.insert(0, self._new_background_layer())
            self._rebuild_inspector_tabs()
        if self.inspector_tabs.count() > 0:
            self.inspector_tabs.setCurrentIndex(max(0, min(int(state.get("active_tab", 0)), self.inspector_tabs.count() - 1)))

    def _save_state(self):
        if not self.state_path:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "size_h": self.toolbar.size_h.value(),
            "size_w": self.toolbar.size_w.value(),
            "unit": self._unit_name(),
            "grid_value": self.toolbar.grid_input.value(),
            "grid_enabled": self.toolbar.grid_check.isChecked(),
            "guide_enabled": self.toolbar.guide_check.isChecked(),
            "history_dialog_width": self._history_dialog_width,
            "history_dialog_height": self._history_dialog_height,
            "splitter_sizes": self.main_splitter.sizes(),
            "selected_palette_color": self.selected_palette_color,
            "palette_colors": self.palette.palette_colors,
            "active_tab": self.inspector_tabs.currentIndex(),
            "layers": self._serialize_layers(),
        }
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _reset_state(self):
        self.toolbar.size_h.setValue(100)
        self.toolbar.size_w.setValue(100)
        self.toolbar.unit_px.setChecked(False)
        self.toolbar.unit_percent.setChecked(True)
        self.toolbar.grid_input.setValue(10)
        self.toolbar.grid_check.setChecked(True)
        self.toolbar.guide_check.setChecked(True)
        self.layers = []
        self.inspector_tabs.clear()
        self._add_layer("background", self._new_background_layer())
        self._set_cursor_text("Cursor: x=0.00%, y=0.00%")
        self._refresh_all()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._update_code_label_layout()

    def _code_max_scroll_offset(self, text: str, available_width: int, font_metrics) -> int:
        if font_metrics.horizontalAdvance(text) <= available_width:
            return 0
        for offset in range(len(text)):
            candidate = f"{'...' if offset > 0 else ''}{text[offset:]}"
            if font_metrics.horizontalAdvance(candidate) <= available_width:
                return offset
        return max(0, len(text) - 1)

    def _code_display_text(self, text: str, offset: int, available_width: int, font_metrics) -> str:
        prefix = "..." if offset > 0 else ""
        visible = text[offset:]
        has_tail = False
        while visible and font_metrics.horizontalAdvance(f"{prefix}{visible}") > available_width:
            visible = visible[:-1]
            has_tail = True
        return f"{prefix}{visible}{'...' if has_tail else ''}"

    def _update_code_label_layout(self, reset_scroll: bool = False):
        text = self._code_full_text
        metrics = self.footer.code_label.fontMetrics()
        available_width = max(1, self.footer.code_label.width() - 8)
        if reset_scroll:
            self._code_scroll_offset = 0
        if metrics.horizontalAdvance(text) <= available_width:
            self.footer.code_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.footer.code_label.setText(text)
            self._code_scroll_offset = 0
            return
        self.footer.code_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        max_offset = self._code_max_scroll_offset(text, available_width, metrics)
        self._code_scroll_offset = max(0, min(self._code_scroll_offset, max_offset))
        self.footer.code_label.setText(self._code_display_text(text, self._code_scroll_offset, available_width, metrics))

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

    def _on_code_clicked(self, _event):
        code = self.copy_feedback_base_text
        QApplication.clipboard().setText(code)
        self._save_history_entry(code)
        self._code_full_text = "copy and saved"
        self.footer.code_label.setStyleSheet("padding: 0px 4px; color: #4ecdc4; background: transparent; border: none;")
        self._update_code_label_layout(reset_scroll=True)

        def _restore():
            self._code_full_text = self.copy_feedback_base_text
            self.footer.code_label.setStyleSheet("padding: 0px 4px; background: transparent; border: none;")
            self._update_code_label_layout(reset_scroll=True)

        QTimer.singleShot(700, _restore)

    def _build_history_preview_lines(self, text: str, width: int, max_lines: int, font_metrics: QFontMetrics) -> list[str]:
        layout = QTextLayout(text, self.font())
        lines: list[str] = []
        layout.beginLayout()
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

    def _history_preview_pixmap(self, entry: dict, size: QSize) -> QPixmap:
        pixmap = QPixmap(size)
        pixmap.fill(QColor("#20252e"))
        painter = QPainter(pixmap)
        rect = pixmap.rect()
        layers = entry.get("layers") if isinstance(entry.get("layers"), list) else []
        background_color = QColor("#20252e")
        for layer in layers:
            if isinstance(layer, dict) and layer.get("kind") == "background" and not layer.get("muted", False):
                background_color = QColor(str(layer.get("color", "#20252e")))
                break
        painter.fillRect(rect, background_color)
        guide_rect = rect.adjusted(8, 8, -8, -8)
        painter.fillRect(guide_rect, QColor("#1f2330"))

        def gradient_direction(deg: float) -> QPointF:
            rad = math.radians(deg)
            return QPointF(math.sin(rad), -math.cos(rad))

        def gradient_half_span(target_rect: QRectF, direction: QPointF) -> float:
            return abs(direction.x()) * target_rect.width() / 2.0 + abs(direction.y()) * target_rect.height() / 2.0

        def position_to_point(target_rect: QRectF, position: float, deg: float) -> QPointF:
            direction = gradient_direction(deg)
            center = QPointF(target_rect.center().x(), target_rect.center().y())
            half_span = gradient_half_span(target_rect, direction)
            scale = (position * 2.0) - 1.0
            return QPointF(center.x() + direction.x() * half_span * scale, center.y() + direction.y() * half_span * scale)

        def project_to_position(target_rect: QRectF, point: QPointF, deg: float) -> float:
            direction = gradient_direction(deg)
            center = QPointF(target_rect.center().x(), target_rect.center().y())
            half_span = max(1e-6, gradient_half_span(target_rect, direction))
            projected = ((point.x() - center.x()) * direction.x()) + ((point.y() - center.y()) * direction.y())
            return (projected / half_span + 1.0) / 2.0

        def position_range_for_rect(target_rect: QRectF, deg: float) -> tuple[float, float]:
            corners = (
                target_rect.topLeft(),
                target_rect.topRight(),
                target_rect.bottomLeft(),
                target_rect.bottomRight(),
            )
            positions = [project_to_position(target_rect, corner, deg) for corner in corners]
            return min(positions), max(positions)

        for layer in layers:
            if not isinstance(layer, dict) or layer.get("muted", False) or layer.get("kind") != "linear":
                continue
            deg = float(layer.get("deg", 90))
            direction = gradient_direction(deg)
            guide_rect_f = QRectF(guide_rect)
            min_position, max_position = position_range_for_rect(guide_rect_f, deg)
            start_point = position_to_point(guide_rect_f, min_position, deg)
            end_point = position_to_point(guide_rect_f, max_position, deg)
            center = QPointF((start_point.x() + end_point.x()) / 2.0, (start_point.y() + end_point.y()) / 2.0)
            half_span = math.hypot(end_point.x() - start_point.x(), end_point.y() - start_point.y()) / 2.0
            thickness = max(1.0, math.hypot(guide_rect.width(), guide_rect.height()) * 2.0)
            sample_count = max(256, int(math.ceil(half_span * 2.0)))
            axis_aligned = self.canvas._axis_aligned_deg(deg)
            if axis_aligned in (90.0, 270.0):
                strip = self.canvas._build_linear_strip_image(layer, sample_count, min_position, max_position, vertical=False)
                painter.drawImage(QRectF(center.x() - half_span, center.y() - thickness / 2.0, half_span * 2.0, thickness), strip, QRectF(0.0, 0.0, float(strip.width()), 1.0))
            elif axis_aligned in (0.0, 180.0):
                strip = self.canvas._build_linear_strip_image(layer, sample_count, min_position, max_position, vertical=True)
                painter.drawImage(QRectF(center.x() - thickness / 2.0, center.y() - half_span, thickness, half_span * 2.0), strip, QRectF(0.0, 0.0, 1.0, float(strip.height())))
            else:
                strip = self.canvas._build_linear_strip_image(layer, sample_count, min_position, max_position, vertical=False)
                painter.save()
                painter.translate(center)
                painter.rotate(deg - 90.0)
                painter.drawImage(QRectF(-half_span, -thickness / 2.0, half_span * 2.0, thickness), strip, QRectF(0.0, 0.0, float(strip.width()), 1.0))
                painter.restore()
        painter.setPen(QColor("#69738a"))
        painter.drawRect(guide_rect)
        painter.end()
        return pixmap

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
            widget = GradientHistoryItemWidget(self._history_preview_pixmap(entry, preview_size), code)
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
