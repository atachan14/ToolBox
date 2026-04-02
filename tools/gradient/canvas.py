from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget


@dataclass
class GradientCanvasConfig:
    size_getter: Callable[[], tuple[float, float, str]]
    grid_getter: Callable[[], tuple[bool, int]]
    guide_enabled_getter: Callable[[], bool]
    layers_getter: Callable[[], list[dict]]
    active_layer_getter: Callable[[], dict | None]
    active_layer_index_getter: Callable[[], int]
    selected_stop_index_getter: Callable[[], int | None]
    active_palette_color_getter: Callable[[], str]
    cursor_changed: Callable[[str], None]
    background_clicked: Callable[[], None]
    linear_stop_hovered: Callable[[float | None], None]
    linear_stop_clicked: Callable[[float], None]
    linear_stop_moved: Callable[[int, float], None]
    linear_stop_deleted: Callable[[int], None]
    radial_center_moved: Callable[[float, float], None]
    interaction_started: Callable[[], None]
    interaction_finished: Callable[[], None]


class GradientCanvas(QWidget):
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

    def __init__(self, config: GradientCanvasConfig):
        super().__init__()
        self.config = config
        self.margin = 24
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self.panning = False
        self.middle_panning = False
        self.last_mouse_screen = QPointF(0, 0)
        self._hover_position: float | None = None
        self._dragging_stop_index: int | None = None
        self._dragging_radial_center = False
        self._pending_add_position: float | None = None
        self._pending_background_click = False
        self._stop_hit_radius = 8.0
        self._interactive_render = False
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(16)
        self._animation_timer.timeout.connect(self._tick_view_animation)
        self._render_settle_timer = QTimer(self)
        self._render_settle_timer.setSingleShot(True)
        self._render_settle_timer.setInterval(120)
        self._render_settle_timer.timeout.connect(self._end_interactive_render)
        self._animation_progress = 0
        self._animation_steps = 12
        self._animation_start_zoom = 1.0
        self._animation_target_zoom = 1.0
        self._animation_start_pan = QPointF(0, 0)
        self._animation_target_pan = QPointF(0, 0)
        self._focus_stop_layer_id: int | None = None
        self._focus_stop_index: int | None = None
        self._focus_progress = 0
        self._focus_steps = 30
        self._radial_cache: dict[tuple, QImage] = {}
        self.setMouseTracking(True)
        self.setMinimumHeight(10)

    def _end_interactive_render(self):
        if self.panning or self.middle_panning or self._dragging_stop_index is not None or self._dragging_radial_center:
            return
        self._interactive_render = False
        self.update()

    def _layer_deg(self, layer: dict) -> float:
        mode = str(layer.get("deg_mode", "input"))
        if mode != "input":
            preset = self.DEGREE_PRESET_TO_VALUE.get(mode)
            if preset is not None:
                return float(preset)
        return float(layer.get("deg", 90))

    def _guide_rect_scene(self) -> QRectF:
        width = max(1.0, float(self.width()))
        height = max(1.0, float(self.height()))
        rect = QRectF(self.margin, self.margin, max(1.0, width - self.margin * 2), max(1.0, height - self.margin * 2))
        size_w, size_h, _unit = self.config.size_getter()
        if size_w > 0 and size_h > 0:
            target_ratio = size_w / size_h
            rect_ratio = rect.width() / rect.height()
            if rect_ratio > target_ratio:
                new_width = rect.height() * target_ratio
                rect = QRectF(rect.center().x() - new_width / 2, rect.y(), new_width, rect.height())
            else:
                new_height = rect.width() / target_ratio
                rect = QRectF(rect.x(), rect.center().y() - new_height / 2, rect.width(), new_height)
        return rect

    def _scene_to_screen(self, point: QPointF) -> QPointF:
        return QPointF(point.x() * self.zoom + self.pan.x(), point.y() * self.zoom + self.pan.y())

    def _screen_to_scene(self, point: QPointF) -> QPointF:
        return QPointF((point.x() - self.pan.x()) / self.zoom, (point.y() - self.pan.y()) / self.zoom)

    def _guide_rect_screen(self) -> QRectF:
        rect = self._guide_rect_scene()
        return QRectF(self._scene_to_screen(rect.topLeft()), self._scene_to_screen(rect.bottomRight())).normalized()

    def _grid_steps_normalized(self, grid_value: int) -> tuple[float, float]:
        size_w, size_h, unit = self.config.size_getter()
        if unit == "px":
            step_x = grid_value / max(size_w, 1.0)
            step_y = grid_value / max(size_h, 1.0)
            return max(step_x, 1e-6), max(step_y, 1e-6)
        step = grid_value / 100.0
        return max(step, 1e-6), max(step, 1e-6)

    def _gradient_direction(self, deg: float) -> QPointF:
        rad = math.radians(deg)
        return QPointF(math.sin(rad), -math.cos(rad))

    def _gradient_half_span(self, direction: QPointF) -> float:
        rect = self._guide_rect_scene()
        return abs(direction.x()) * rect.width() / 2.0 + abs(direction.y()) * rect.height() / 2.0

    def _guide_diagonal(self) -> float:
        rect = self._guide_rect_scene()
        return math.hypot(rect.width(), rect.height())

    def _normalized_deg(self, deg: float) -> float:
        return deg % 360.0

    def _axis_aligned_deg(self, deg: float) -> float | None:
        normalized = self._normalized_deg(deg)
        for candidate in (0.0, 90.0, 180.0, 270.0):
            if abs(normalized - candidate) <= 1e-6:
                return candidate
        return None

    def _project_point_to_position(self, point: QPointF, deg: float) -> float:
        rect = self._guide_rect_scene()
        center = QPointF(rect.center().x(), rect.center().y())
        direction = self._gradient_direction(deg)
        half_span = max(1e-6, self._gradient_half_span(direction))
        projected = ((point.x() - center.x()) * direction.x()) + ((point.y() - center.y()) * direction.y())
        return (projected / half_span + 1.0) / 2.0

    def _snap_position(self, position: float, deg: float) -> float:
        active, grid_value = self.config.grid_getter()
        if not active:
            return position
        size_w, size_h, unit = self.config.size_getter()
        if unit == "px":
            direction = self._gradient_direction(deg)
            span = abs(direction.x()) * size_w + abs(direction.y()) * size_h
            step = grid_value / max(span, 1e-6)
        else:
            step = grid_value / 100.0
        step = max(step, 1e-6)
        return round(position / step) * step

    def _snap_scene_point_to_grid(self, point: QPointF) -> QPointF:
        active, grid_value = self.config.grid_getter()
        if not active:
            return point
        rect = self._guide_rect_scene()
        step_x, step_y = self._grid_steps_normalized(max(1, grid_value))
        norm_x = (point.x() - rect.x()) / max(1e-6, rect.width())
        norm_y = (point.y() - rect.y()) / max(1e-6, rect.height())
        snapped_x = round(norm_x / step_x) * step_x
        snapped_y = round(norm_y / step_y) * step_y
        return QPointF(rect.x() + rect.width() * snapped_x, rect.y() + rect.height() * snapped_y)

    def _snap_radial_position(self, layer: dict, position: float) -> float:
        active, grid_value = self.config.grid_getter()
        if not active:
            return position
        size_w, size_h, unit = self.config.size_getter()
        if unit == "px":
            step = grid_value / max(self._radial_span(layer), 1e-6)
        else:
            step = grid_value / 100.0
        step = max(step, 1e-6)
        return round(position / step) * step

    def _position_to_scene(self, position: float, deg: float) -> QPointF:
        rect = self._guide_rect_scene()
        direction = self._gradient_direction(deg)
        center = QPointF(rect.center().x(), rect.center().y())
        half_span = self._gradient_half_span(direction)
        scale = (position * 2.0) - 1.0
        return QPointF(center.x() + direction.x() * half_span * scale, center.y() + direction.y() * half_span * scale)

    def _position_range_for_scene_rect(self, scene_rect: QRectF, deg: float) -> tuple[float, float]:
        corners = (
            scene_rect.topLeft(),
            scene_rect.topRight(),
            scene_rect.bottomLeft(),
            scene_rect.bottomRight(),
        )
        positions = [self._project_point_to_position(corner, deg) for corner in corners]
        return min(positions), max(positions)

    def _radial_center_scene(self, layer: dict, target_rect: QRectF | None = None) -> QPointF:
        rect = target_rect if target_rect is not None else self._guide_rect_scene()
        return QPointF(
            rect.x() + rect.width() * float(layer.get("center_x", 0.5)),
            rect.y() + rect.height() * float(layer.get("center_y", 0.5)),
        )

    def _radial_center_normalized(self, scene_point: QPointF, target_rect: QRectF | None = None) -> tuple[float, float]:
        rect = target_rect if target_rect is not None else self._guide_rect_scene()
        return (
            (scene_point.x() - rect.x()) / max(1e-6, rect.width()),
            (scene_point.y() - rect.y()) / max(1e-6, rect.height()),
        )

    def _radial_span(self, layer: dict, target_rect: QRectF | None = None) -> float:
        rect = target_rect if target_rect is not None else self._guide_rect_scene()
        center = self._radial_center_scene(layer, rect)
        corners = (rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight())
        return max(1e-6, max(math.hypot(corner.x() - center.x(), corner.y() - center.y()) for corner in corners))

    def _project_radial_point_to_position(self, point: QPointF, layer: dict, target_rect: QRectF | None = None) -> float:
        rect = target_rect if target_rect is not None else self._guide_rect_scene()
        center = self._radial_center_scene(layer, rect)
        return math.hypot(point.x() - center.x(), point.y() - center.y()) / self._radial_span(layer, rect)

    def _radial_position_to_scene(self, position: float, layer: dict, target_rect: QRectF | None = None) -> QPointF:
        rect = target_rect if target_rect is not None else self._guide_rect_scene()
        center = self._radial_center_scene(layer, rect)
        return QPointF(center.x() + self._radial_span(layer, rect) * position, center.y())

    def _prepared_linear_stops(self, layer: dict) -> list[tuple[float, QColor]]:
        prepared: list[tuple[float, QColor]] = []
        last_position: float | None = None
        for stop in layer.get("stops") or []:
            if stop.get("muted", False):
                continue
            position = float(stop.get("position", 0.0))
            if last_position is not None and position < last_position:
                position = last_position
            color = QColor(str(stop.get("color", "#ffffff")))
            prepared.append((position, color))
            last_position = position
        return prepared

    def _lerp_color(self, start: QColor, end: QColor, ratio: float) -> QColor:
        t = max(0.0, min(1.0, ratio))
        inv = 1.0 - t
        return QColor.fromRgbF(
            (start.redF() * inv) + (end.redF() * t),
            (start.greenF() * inv) + (end.greenF() * t),
            (start.blueF() * inv) + (end.blueF() * t),
            (start.alphaF() * inv) + (end.alphaF() * t),
        )

    def _sample_linear_color(self, stops: list[tuple[float, QColor]], position: float, repeat: bool) -> QColor:
        transparent = QColor(0, 0, 0, 0)
        if not stops:
            return transparent
        if len(stops) == 1:
            return stops[0][1]

        first_position = stops[0][0]
        last_position = stops[-1][0]
        if repeat:
            period = last_position - first_position
            if period <= 1e-9:
                return stops[-1][1]
            position = ((position - first_position) % period) + first_position
        else:
            if position <= first_position:
                return stops[0][1]
            if position >= last_position:
                return stops[-1][1]

        for index in range(len(stops) - 1):
            start_position, start_color = stops[index]
            end_position, end_color = stops[index + 1]
            if position < start_position:
                return start_color
            if abs(position - start_position) <= 1e-9:
                return end_color if end_position <= start_position + 1e-9 else start_color
            if end_position <= start_position + 1e-9:
                continue
            if position <= end_position + 1e-9:
                ratio = (position - start_position) / (end_position - start_position)
                return self._lerp_color(start_color, end_color, ratio)
        return stops[-1][1]

    def _build_linear_strip_image(self, layer: dict, sample_count: int, min_position: float, max_position: float, vertical: bool = False) -> QImage:
        image = QImage(1, max(1, sample_count), QImage.Format_ARGB32_Premultiplied) if vertical else QImage(max(1, sample_count), 1, QImage.Format_ARGB32_Premultiplied)
        stops = self._prepared_linear_stops(layer)
        repeat = bool(layer.get("repeat", False))
        sample_span = image.height() if vertical else image.width()
        position_span = max_position - min_position
        if sample_span == 1:
            image.setPixelColor(0, 0, self._sample_linear_color(stops, (min_position + max_position) / 2.0, repeat))
            return image
        for index in range(sample_span):
            ratio = index / (sample_span - 1)
            position = min_position + (position_span * ratio)
            if vertical:
                image.setPixelColor(0, index, self._sample_linear_color(stops, position, repeat))
            else:
                image.setPixelColor(index, 0, self._sample_linear_color(stops, position, repeat))
        return image

    def _build_radial_image(self, layer: dict, target_rect: QRectF) -> QImage:
        downsample = 2 if self._interactive_render else 1
        width = max(1, int(math.ceil(target_rect.width() / downsample)))
        height = max(1, int(math.ceil(target_rect.height() / downsample)))
        cache_key = (
            id(layer),
            round(float(layer.get("center_x", 0.5)), 6),
            round(float(layer.get("center_y", 0.5)), 6),
            bool(layer.get("repeat", False)),
            width,
            height,
            tuple(
                (
                    str(stop.get("color", "#ffffff")),
                    round(float(stop.get("position", 0.0)), 6),
                    bool(stop.get("muted", False)),
                )
                for stop in (layer.get("stops") or [])
            ),
        )
        cached = self._radial_cache.get(cache_key)
        if cached is not None:
            return cached
        image = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        stops = self._prepared_linear_stops(layer)
        repeat = bool(layer.get("repeat", False))
        center = self._radial_center_scene(layer, target_rect)
        span = self._radial_span(layer, target_rect)
        for y in range(height):
            sy = target_rect.y() + ((y + 0.5) * downsample)
            for x in range(width):
                sx = target_rect.x() + ((x + 0.5) * downsample)
                position = math.hypot(sx - center.x(), sy - center.y()) / span
                image.setPixelColor(x, y, self._sample_linear_color(stops, position, repeat))
        self._radial_cache = {cache_key: image}
        return image

    def _find_hit_stop_index(self, layer: dict, scene_point: QPointF) -> int | None:
        kind = layer.get("kind")
        nearest_idx = None
        nearest_dist = float("inf")
        for idx, stop in enumerate(layer.get("stops") or []):
            if stop.get("muted", False):
                continue
            if kind == "radial":
                stop_scene = self._radial_position_to_scene(float(stop.get("position", 0.0)), layer)
            else:
                stop_scene = self._position_to_scene(float(stop.get("position", 0.0)), self._layer_deg(layer))
            dx = stop_scene.x() - scene_point.x()
            dy = stop_scene.y() - scene_point.y()
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_idx = idx
        return nearest_idx if nearest_dist <= (self._stop_hit_radius / self.zoom) else None

    def _background_color(self) -> QColor:
        for layer in self.config.layers_getter():
            if layer.get("kind") == "background" and not layer.get("muted", False):
                return QColor(str(layer.get("color", "#20252e")))
        return QColor("#20252e")

    def _stop_scene_point(self, layer: dict, index: int) -> QPointF | None:
        stops = list(layer.get("stops") or [])
        if not (0 <= index < len(stops)):
            return None
        if layer.get("kind") == "radial":
            return self._radial_position_to_scene(float(stops[index].get("position", 0.0)), layer)
        return self._position_to_scene(float(stops[index].get("position", 0.0)), self._layer_deg(layer))

    def ensure_stop_visible(self, layer: dict, index: int):
        stop_scene = self._stop_scene_point(layer, index)
        if stop_scene is None:
            return
        stop_screen = self._scene_to_screen(stop_scene)
        padding = 24.0
        view_rect = QRectF(padding, padding, max(1.0, self.width() - padding * 2), max(1.0, self.height() - padding * 2))
        if view_rect.contains(stop_screen):
            self.update()
            return
        guide_rect = self._guide_rect_scene()
        bounds = guide_rect.united(QRectF(stop_scene.x(), stop_scene.y(), 1.0, 1.0)).adjusted(-padding, -padding, padding, padding)
        available_width = max(1.0, float(self.width()) - padding * 2)
        available_height = max(1.0, float(self.height()) - padding * 2)
        target_zoom = min(self.zoom, available_width / max(1.0, bounds.width()), available_height / max(1.0, bounds.height()))
        target_zoom = min(8.0, max(0.3, target_zoom))
        target_center = bounds.center()
        target_pan = QPointF((self.width() / 2.0) - target_center.x() * target_zoom, (self.height() / 2.0) - target_center.y() * target_zoom)
        self._start_view_animation(target_zoom, target_pan)

    def focus_stop(self, layer: dict, index: int):
        if self._stop_scene_point(layer, index) is None:
            return
        self._focus_stop_layer_id = id(layer)
        self._focus_stop_index = index
        self._focus_progress = 0
        if not self._animation_timer.isActive():
            self._animation_start_zoom = self.zoom
            self._animation_target_zoom = self.zoom
            self._animation_start_pan = QPointF(self.pan)
            self._animation_target_pan = QPointF(self.pan)
            self._animation_progress = 0
            self._animation_timer.start()
        self.update()

    def _start_view_animation(self, target_zoom: float, target_pan: QPointF):
        self._animation_start_zoom = self.zoom
        self._animation_target_zoom = target_zoom
        self._animation_start_pan = QPointF(self.pan)
        self._animation_target_pan = QPointF(target_pan)
        self._animation_progress = 0
        if self._animation_timer.isActive():
            self._animation_timer.stop()
        if abs(self._animation_start_zoom - target_zoom) <= 1e-6 and (self._animation_start_pan - target_pan).manhattanLength() <= 0.5:
            self.zoom = target_zoom
            self.pan = QPointF(target_pan)
            if self._focus_stop_index is not None:
                self._animation_progress = 0
                self._animation_timer.start()
            self.update()
            return
        self._animation_timer.start()

    def _tick_view_animation(self):
        self._animation_progress += 1
        progress = min(1.0, self._animation_progress / max(1, self._animation_steps))
        eased = 1.0 - ((1.0 - progress) ** 3)
        self.zoom = self._animation_start_zoom + (self._animation_target_zoom - self._animation_start_zoom) * eased
        self.pan = QPointF(
            self._animation_start_pan.x() + (self._animation_target_pan.x() - self._animation_start_pan.x()) * eased,
            self._animation_start_pan.y() + (self._animation_target_pan.y() - self._animation_start_pan.y()) * eased,
        )
        if self._focus_stop_index is not None:
            self._focus_progress = min(self._focus_steps, self._focus_progress + 1)
            if self._focus_progress >= self._focus_steps:
                self._focus_stop_layer_id = None
                self._focus_stop_index = None
        self.update()
        if progress >= 1.0 and self._focus_stop_index is None:
            self._animation_timer.stop()

    def mousePressEvent(self, event: QMouseEvent):
        self.setFocus()
        self.last_mouse_screen = event.position()
        scene_pos = self._screen_to_scene(event.position())
        active_layer = self.config.active_layer_getter()
        if (event.modifiers() & Qt.ControlModifier) and event.button() == Qt.LeftButton:
            self.panning = True
            self._interactive_render = True
            return
        if event.button() == Qt.MiddleButton:
            self.middle_panning = True
            self.panning = True
            self._interactive_render = True
            return
        if not active_layer:
            return
        if active_layer.get("muted", False):
            return
        if active_layer.get("kind") == "background":
            if event.button() == Qt.LeftButton:
                self._pending_background_click = True
            return
        if active_layer.get("kind") not in ("linear", "radial"):
            return
        if event.button() == Qt.LeftButton:
            if active_layer.get("kind") == "radial":
                center_scene = self._radial_center_scene(active_layer)
                if math.hypot(center_scene.x() - scene_pos.x(), center_scene.y() - scene_pos.y()) <= (self._stop_hit_radius / self.zoom):
                    self._dragging_radial_center = True
                    self._interactive_render = True
                    self.config.interaction_started()
                    return
            hit_index = self._find_hit_stop_index(active_layer, scene_pos)
            if hit_index is not None:
                self._dragging_stop_index = hit_index
                self._interactive_render = True
                self.config.interaction_started()
                return
            if active_layer.get("kind") == "radial":
                self._pending_add_position = self._snap_radial_position(active_layer, self._project_radial_point_to_position(scene_pos, active_layer))
            else:
                deg = self._layer_deg(active_layer)
                self._pending_add_position = self._snap_position(self._project_point_to_position(scene_pos, deg), deg)
            self._hover_position = self._pending_add_position
            self.config.linear_stop_hovered(self._hover_position)
            self.update()
            return
        if event.button() == Qt.RightButton:
            hit_index = self._find_hit_stop_index(active_layer, scene_pos)
            if hit_index is not None:
                self.config.linear_stop_deleted(hit_index)
                self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        scene_pos = self._screen_to_scene(event.position())
        if self.panning:
            delta = event.position() - self.last_mouse_screen
            self.pan += delta
            self.last_mouse_screen = event.position()
            self.update()
            return
        guide = self._guide_rect_scene()
        x_n = (scene_pos.x() - guide.x()) / guide.width()
        y_n = (scene_pos.y() - guide.y()) / guide.height()
        size_w, size_h, unit = self.config.size_getter()
        if unit == "px":
            self.config.cursor_changed(f"Cursor: x={x_n * size_w:.1f}px, y={y_n * size_h:.1f}px")
        else:
            self.config.cursor_changed(f"Cursor: x={x_n * 100:.2f}%, y={y_n * 100:.2f}%")
        active_layer = self.config.active_layer_getter()
        if active_layer and not active_layer.get("muted", False) and active_layer.get("kind") in ("linear", "radial"):
            if active_layer.get("kind") == "radial":
                if self._dragging_radial_center:
                    snapped_scene = self._snap_scene_point_to_grid(scene_pos)
                    center_x, center_y = self._radial_center_normalized(snapped_scene)
                    self.config.radial_center_moved(center_x, center_y)
                    self._hover_position = None
                elif self._dragging_stop_index is not None or self._pending_add_position is not None:
                    self._hover_position = self._snap_radial_position(active_layer, self._project_radial_point_to_position(scene_pos, active_layer))
                else:
                    self._hover_position = None
            else:
                deg = self._layer_deg(active_layer)
                if self._dragging_stop_index is not None or self._pending_add_position is not None:
                    self._hover_position = self._snap_position(self._project_point_to_position(scene_pos, deg), deg)
                else:
                    self._hover_position = None
            if self._dragging_stop_index is not None and self._hover_position is not None:
                self.config.linear_stop_moved(self._dragging_stop_index, self._hover_position)
            self.config.linear_stop_hovered(self._hover_position)
        else:
            self._hover_position = None
            self.config.linear_stop_hovered(None)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        scene_pos = self._screen_to_scene(event.position())
        active_layer = self.config.active_layer_getter()
        if event.button() == Qt.MiddleButton:
            self.middle_panning = False
            self.panning = False
            self._interactive_render = False
            return
        if event.button() != Qt.LeftButton:
            return
        if self.panning:
            self.panning = False
            self.middle_panning = False
            self._interactive_render = False
            return
        if not active_layer:
            self._dragging_stop_index = None
            self._dragging_radial_center = False
            self._pending_add_position = None
            self._pending_background_click = False
            self._interactive_render = False
            return
        if active_layer.get("muted", False):
            self._dragging_stop_index = None
            self._dragging_radial_center = False
            self._pending_add_position = None
            self._pending_background_click = False
            self._hover_position = None
            self.config.linear_stop_hovered(None)
            self._interactive_render = False
            self.update()
            return
        if active_layer.get("kind") == "background":
            if self._pending_background_click:
                self.config.background_clicked()
            self._pending_background_click = False
            self._interactive_render = False
            self.update()
            return
        if active_layer.get("kind") not in ("linear", "radial"):
            self._dragging_stop_index = None
            self._dragging_radial_center = False
            self._pending_add_position = None
            self._interactive_render = False
            return
        if self._dragging_radial_center:
            self._dragging_radial_center = False
            self._hover_position = None
            self.config.linear_stop_hovered(None)
            self.config.interaction_finished()
            self._interactive_render = False
            self.update()
            return
        if self._dragging_stop_index is not None:
            self._dragging_stop_index = None
            self._hover_position = None
            self.config.linear_stop_hovered(None)
            self.config.interaction_finished()
            self._interactive_render = False
            self.update()
            return
        if self._pending_add_position is not None:
            if active_layer.get("kind") == "radial":
                final_position = self._snap_radial_position(active_layer, self._project_radial_point_to_position(scene_pos, active_layer))
            else:
                deg = self._layer_deg(active_layer)
                final_position = self._snap_position(self._project_point_to_position(scene_pos, deg), deg)
            self.config.linear_stop_clicked(final_position)
        self._pending_add_position = None
        self._hover_position = None
        self.config.linear_stop_hovered(None)
        self._interactive_render = False
        self.update()

    def wheelEvent(self, event: QWheelEvent):
        if not (event.modifiers() & Qt.ControlModifier):
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        factor = 1.1 if delta > 0 else 0.9
        new_zoom = min(8.0, max(0.3, self.zoom * factor))
        mouse = event.position()
        before = self._screen_to_scene(mouse)
        self.zoom = new_zoom
        after = self._scene_to_screen(before)
        self.pan += mouse - after
        self._interactive_render = True
        self._render_settle_timer.start()
        self.update()
        event.accept()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self._background_color())

        guide_scene = self._guide_rect_scene()
        guide_screen = self._guide_rect_screen()
        painter.save()
        painter.setClipRect(guide_screen)
        painter.scale(self.zoom, self.zoom)
        painter.translate(self.pan.x() / self.zoom, self.pan.y() / self.zoom)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        painter.fillRect(guide_scene, self._background_color())
        for layer in self.config.layers_getter():
            if layer.get("muted", False):
                continue
            kind = layer.get("kind")
            if kind == "linear":
                deg = self._layer_deg(layer)
                min_position, max_position = self._position_range_for_scene_rect(guide_scene, deg)
                start_point = self._position_to_scene(min_position, deg)
                end_point = self._position_to_scene(max_position, deg)
                center = QPointF((start_point.x() + end_point.x()) / 2.0, (start_point.y() + end_point.y()) / 2.0)
                half_span = math.hypot(end_point.x() - start_point.x(), end_point.y() - start_point.y()) / 2.0
                thickness = max(1.0, self._guide_diagonal() * 2.0)
                sample_count = max(256, int(math.ceil(half_span * 2.0)))
                axis_aligned = self._axis_aligned_deg(deg)
                if axis_aligned in (90.0, 270.0):
                    strip = self._build_linear_strip_image(layer, sample_count, min_position, max_position, vertical=False)
                    painter.drawImage(
                        QRectF(center.x() - half_span, center.y() - thickness / 2.0, half_span * 2.0, thickness),
                        strip,
                        QRectF(0.0, 0.0, float(strip.width()), 1.0),
                    )
                elif axis_aligned in (0.0, 180.0):
                    strip = self._build_linear_strip_image(layer, sample_count, min_position, max_position, vertical=True)
                    painter.drawImage(
                        QRectF(center.x() - thickness / 2.0, center.y() - half_span, thickness, half_span * 2.0),
                        strip,
                        QRectF(0.0, 0.0, 1.0, float(strip.height())),
                    )
                else:
                    strip = self._build_linear_strip_image(layer, sample_count, min_position, max_position, vertical=False)
                    painter.save()
                    painter.translate(center)
                    painter.rotate(deg - 90.0)
                    painter.drawImage(
                        QRectF(-half_span, -thickness / 2.0, half_span * 2.0, thickness),
                        strip,
                        QRectF(0.0, 0.0, float(strip.width()), 1.0),
                    )
                    painter.restore()
            elif kind == "radial":
                radial_image = self._build_radial_image(layer, guide_scene)
                painter.drawImage(
                    guide_scene,
                    radial_image,
                    QRectF(0.0, 0.0, float(radial_image.width()), float(radial_image.height())),
                )
            elif kind == "conic":
                painter.fillRect(guide_scene, QColor(255, 255, 255, 10))
        painter.restore()

        active, grid_value = self.config.grid_getter()
        if active:
            painter.setPen(QPen(QColor("#3a4255"), 1))
            step_nx, step_ny = self._grid_steps_normalized(max(1, grid_value))
            step_x = guide_scene.width() * step_nx
            step_y = guide_scene.height() * step_ny
            screen_rect = self.rect()
            scene_top_left = self._screen_to_scene(screen_rect.topLeft())
            scene_bottom_right = self._screen_to_scene(screen_rect.bottomRight())
            x_start_idx = int((scene_top_left.x() - guide_scene.x()) // step_x) - 1
            x_end_idx = int((scene_bottom_right.x() - guide_scene.x()) // step_x) + 1
            y_start_idx = int((scene_top_left.y() - guide_scene.y()) // step_y) - 1
            y_end_idx = int((scene_bottom_right.y() - guide_scene.y()) // step_y) + 1
            for idx in range(x_start_idx, x_end_idx + 1):
                x = guide_scene.x() + step_x * idx
                sx = self._scene_to_screen(QPointF(x, 0)).x()
                painter.drawLine(QPointF(sx, float(screen_rect.top())), QPointF(sx, float(screen_rect.bottom())))
            for idx in range(y_start_idx, y_end_idx + 1):
                y = guide_scene.y() + step_y * idx
                sy = self._scene_to_screen(QPointF(0, y)).y()
                painter.drawLine(QPointF(float(screen_rect.left()), sy), QPointF(float(screen_rect.right()), sy))

        guide_enabled = self.config.guide_enabled_getter()
        if guide_enabled:
            for inset, color in ((0.5, "#f8fafc"), (1.5, "#111827"), (2.5, "#f8fafc")):
                painter.setPen(QPen(QColor(color), 1))
                painter.drawRect(guide_screen.adjusted(inset, inset, -inset, -inset))

        active_layer = self.config.active_layer_getter()
        if guide_enabled and active_layer and active_layer.get("kind") == "linear":
            deg = self._layer_deg(active_layer)
            direction = self._gradient_direction(deg)
            center = QPointF(guide_scene.center().x(), guide_scene.center().y())
            half_span = self._gradient_half_span(direction)
            start = self._scene_to_screen(QPointF(center.x() - direction.x() * half_span, center.y() - direction.y() * half_span))
            end = self._scene_to_screen(QPointF(center.x() + direction.x() * half_span, center.y() + direction.y() * half_span))
            painter.setPen(QPen(QColor("#9aa5ce"), 1, Qt.DashLine))
            painter.drawLine(start, end)
            for stop in active_layer.get("stops") or []:
                if stop.get("muted", False):
                    continue
                point = self._scene_to_screen(self._position_to_scene(float(stop.get("position", 0.0)), deg))
                painter.setPen(QPen(QColor("#f8fafc"), 2))
                painter.setBrush(QColor(str(stop.get("color", "#ffffff"))))
                painter.drawEllipse(point, 5, 5)
                painter.setPen(QPen(QColor("#111827"), 1))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(point, 7, 7)
            if self._focus_stop_index is not None and self._focus_stop_layer_id == id(active_layer):
                focused_stop = self._stop_scene_point(active_layer, self._focus_stop_index)
                if focused_stop is not None:
                    focused_point = self._scene_to_screen(focused_stop)
                    progress = min(1.0, self._focus_progress / max(1, self._focus_steps))
                    eased = 1.0 - ((1.0 - progress) ** 3)
                    outer_radius = 18.0 - (10.0 * eased)
                    inner_radius = max(7.0, outer_radius - 3.0)
                    outer_color = QColor("#4ecdc4")
                    outer_color.setAlphaF(max(0.0, 1.0 - eased))
                    inner_color = QColor("#f8fafc")
                    inner_color.setAlphaF(max(0.0, 0.9 - eased))
                    painter.setPen(QPen(outer_color, 3))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(focused_point, outer_radius, outer_radius)
                    painter.setPen(QPen(inner_color, 2))
                    painter.drawEllipse(focused_point, inner_radius, inner_radius)
            if self._hover_position is not None and self._pending_add_position is not None:
                hover_point = self._scene_to_screen(self._position_to_scene(self._hover_position, deg))
                painter.setPen(QPen(QColor("#4ecdc4"), 1))
                painter.setBrush(QColor(self.config.active_palette_color_getter()))
                painter.drawEllipse(hover_point, 6, 6)
        elif guide_enabled and active_layer and active_layer.get("kind") == "radial":
            center_scene = self._radial_center_scene(active_layer)
            center_screen = self._scene_to_screen(center_scene)
            radius = self._radial_span(active_layer)
            radius_screen = radius * self.zoom
            painter.setPen(QPen(QColor("#9aa5ce"), 1, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center_screen, radius_screen, radius_screen)
            painter.setPen(QPen(QColor("#f8fafc"), 2))
            painter.setBrush(QColor("#111827"))
            painter.drawEllipse(center_screen, 5, 5)
            painter.setPen(QPen(QColor("#111827"), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center_screen, 7, 7)
            for stop in active_layer.get("stops") or []:
                if stop.get("muted", False):
                    continue
                point = self._scene_to_screen(self._radial_position_to_scene(float(stop.get("position", 0.0)), active_layer))
                painter.setPen(QPen(QColor("#f8fafc"), 2))
                painter.setBrush(QColor(str(stop.get("color", "#ffffff"))))
                painter.drawEllipse(point, 5, 5)
                painter.setPen(QPen(QColor("#111827"), 1))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(point, 7, 7)
            if self._focus_stop_index is not None and self._focus_stop_layer_id == id(active_layer):
                focused_stop = self._stop_scene_point(active_layer, self._focus_stop_index)
                if focused_stop is not None:
                    focused_point = self._scene_to_screen(focused_stop)
                    progress = min(1.0, self._focus_progress / max(1, self._focus_steps))
                    eased = 1.0 - ((1.0 - progress) ** 3)
                    outer_radius = 18.0 - (10.0 * eased)
                    inner_radius = max(7.0, outer_radius - 3.0)
                    outer_color = QColor("#4ecdc4")
                    outer_color.setAlphaF(max(0.0, 1.0 - eased))
                    inner_color = QColor("#f8fafc")
                    inner_color.setAlphaF(max(0.0, 0.9 - eased))
                    painter.setPen(QPen(outer_color, 3))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(focused_point, outer_radius, outer_radius)
                    painter.setPen(QPen(inner_color, 2))
                    painter.drawEllipse(focused_point, inner_radius, inner_radius)
            if self._hover_position is not None and self._pending_add_position is not None:
                hover_point = self._scene_to_screen(self._radial_position_to_scene(self._hover_position, active_layer))
                painter.setPen(QPen(QColor("#4ecdc4"), 1))
                painter.setBrush(QColor(self.config.active_palette_color_getter()))
                painter.drawEllipse(hover_point, 6, 6)

        painter.setPen(QPen(QColor("#9aa5ce"), 1))
        index = self.config.active_layer_index_getter()
        painter.drawText(10, 20, f"Layer: {index + 1 if index >= 0 else '-'}  Zoom: {self.zoom:.2f}")
