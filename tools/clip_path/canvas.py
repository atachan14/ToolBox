from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget

from .state import MODE_INPUT, MODE_VIEW, ClipPoint


@dataclass
class CanvasConfig:
    mode_getter: Callable[[], str]
    points_getter: Callable[[], list[ClipPoint]]
    size_getter: Callable[[], tuple[float, float, str]]
    grid_getter: Callable[[], tuple[bool, int]]
    on_points_changed: Callable[[], None]
    on_cursor_changed: Callable[[float, float], None]


class ClipPathCanvas(QWidget):

    def __init__(self, config: CanvasConfig):
        super().__init__()

        self.config = config

        self.dragging_index: int | None = None
        self.panning = False
        self.last_mouse_scene = QPointF(0, 0)
        self.last_mouse_screen = QPointF(0, 0)

        self.zoom = 1.0
        self.pan = QPointF(0, 0)

        self.temp_mode: str | None = None

        self.hit_radius = 8
        self.margin = 24

        self.setMouseTracking(True)
        self.setMinimumSize(280, 280)
        self.setFocusPolicy(Qt.StrongFocus)

    def set_temp_mode(self, mode: str | None):
        self.temp_mode = mode
        self.update()

    def current_mode(self) -> str:
        return self.temp_mode or self.config.mode_getter()

    def _guide_rect_scene(self) -> QRectF:
        width = max(1.0, float(self.width()))
        height = max(1.0, float(self.height()))

        rect = QRectF(
            self.margin,
            self.margin,
            max(1.0, width - self.margin * 2),
            max(1.0, height - self.margin * 2),
        )

        size_w, size_h, unit = self.config.size_getter()

        if unit == "px" and size_w > 0 and size_h > 0:
            target_ratio = size_w / size_h
            rect_ratio = rect.width() / rect.height()

            if rect_ratio > target_ratio:
                new_width = rect.height() * target_ratio
                x = rect.center().x() - new_width / 2
                rect = QRectF(x, rect.y(), new_width, rect.height())
            else:
                new_height = rect.width() / target_ratio
                y = rect.center().y() - new_height / 2
                rect = QRectF(rect.x(), y, rect.width(), new_height)

        return rect

    def _scene_to_screen(self, point: QPointF) -> QPointF:
        return QPointF(
            point.x() * self.zoom + self.pan.x(),
            point.y() * self.zoom + self.pan.y(),
        )

    def _screen_to_scene(self, point: QPointF) -> QPointF:
        return QPointF(
            (point.x() - self.pan.x()) / self.zoom,
            (point.y() - self.pan.y()) / self.zoom,
        )

    def _normalized_to_scene(self, point: ClipPoint) -> QPointF:
        rect = self._guide_rect_scene()

        return QPointF(
            rect.x() + point.x * rect.width(),
            rect.y() + point.y * rect.height(),
        )

    def _scene_to_normalized(self, point: QPointF) -> ClipPoint:
        rect = self._guide_rect_scene()
        nx = (point.x() - rect.x()) / rect.width()
        ny = (point.y() - rect.y()) / rect.height()

        return ClipPoint(nx, ny)

    def _snap_normalized(self, point: ClipPoint) -> ClipPoint:
        active, grid_value = self.config.grid_getter()

        if not active:
            return point

        step = 1.0 / max(1, grid_value)

        return ClipPoint(
            round(point.x / step) * step,
            round(point.y / step) * step,
        )

    def _find_hit_point(self, scene_pos: QPointF) -> int | None:
        points = self.config.points_getter()
        nearest_idx = None
        nearest_dist = float("inf")

        for idx, point in enumerate(points):
            scene = self._normalized_to_scene(point)
            dx = scene.x() - scene_pos.x()
            dy = scene.y() - scene_pos.y()
            dist = (dx * dx + dy * dy) ** 0.5

            if dist < nearest_dist:
                nearest_dist = dist
                nearest_idx = idx

        if nearest_dist <= self.hit_radius:
            return nearest_idx

        return None

    def mousePressEvent(self, event: QMouseEvent):
        self.setFocus()

        scene_pos = self._screen_to_scene(event.position())
        self.last_mouse_scene = scene_pos
        self.last_mouse_screen = event.position()

        mode = self.current_mode()
        points = self.config.points_getter()

        if mode == MODE_VIEW and event.button() == Qt.LeftButton:
            self.panning = True
            return

        if mode != MODE_INPUT:
            return

        if event.button() == Qt.LeftButton:
            hit_idx = self._find_hit_point(scene_pos)

            if hit_idx is not None:
                self.dragging_index = hit_idx
                return

            normalized = self._scene_to_normalized(scene_pos)
            points.append(self._snap_normalized(normalized))
            self.config.on_points_changed()
            self.update()
            return

        if event.button() == Qt.RightButton:
            hit_idx = self._find_hit_point(scene_pos)

            if hit_idx is not None:
                points.pop(hit_idx)
                self.config.on_points_changed()
                self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        scene_pos = self._screen_to_scene(event.position())
        normalized = self._scene_to_normalized(scene_pos)
        self.config.on_cursor_changed(normalized.x, normalized.y)

        points = self.config.points_getter()

        if self.panning:
            delta = event.position() - self.last_mouse_screen
            self.pan += delta
            self.last_mouse_screen = event.position()
            self.update()
            return

        if self.dragging_index is None:
            return

        normalized = self._snap_normalized(normalized)
        points[self.dragging_index] = normalized

        self.config.on_points_changed()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.dragging_index = None
            self.panning = False

    def wheelEvent(self, event: QWheelEvent):
        if self.current_mode() != MODE_VIEW:
            return

        delta = event.angleDelta().y()

        if delta == 0:
            return

        factor = 1.1 if delta > 0 else 0.9
        new_zoom = min(8.0, max(0.3, self.zoom * factor))

        mouse = event.position()
        before = self._screen_to_scene(mouse)

        self.zoom = new_zoom

        after = self._scene_to_screen(before)
        self.pan += mouse - after

        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#20252e"))

        guide = self._guide_rect_scene()

        guide_tl = self._scene_to_screen(guide.topLeft())
        guide_br = self._scene_to_screen(guide.bottomRight())
        guide_screen = QRectF(guide_tl, guide_br).normalized()

        painter.setPen(QPen(QColor("#69738a"), 1))
        painter.drawRect(guide_screen)

        active, grid_value = self.config.grid_getter()

        if active:
            painter.setPen(QPen(QColor("#3a4255"), 1))
            step_x = guide.width() / max(1, grid_value)
            step_y = guide.height() / max(1, grid_value)

            for idx in range(1, grid_value):
                x = guide.x() + step_x * idx
                y = guide.y() + step_y * idx

                sx = self._scene_to_screen(QPointF(x, guide.y())).x()
                sy = self._scene_to_screen(QPointF(guide.x(), y)).y()

                painter.drawLine(
                    QPointF(sx, guide_screen.top()),
                    QPointF(sx, guide_screen.bottom()),
                )
                painter.drawLine(
                    QPointF(guide_screen.left(), sy),
                    QPointF(guide_screen.right(), sy),
                )

        points = self.config.points_getter()

        painter.setPen(QPen(QColor("#7aa2f7"), 2))

        for idx in range(len(points) - 1):
            start = self._scene_to_screen(self._normalized_to_scene(points[idx]))
            end = self._scene_to_screen(self._normalized_to_scene(points[idx + 1]))
            painter.drawLine(start, end)

        painter.setPen(QPen(QColor("#f7768e"), 2))

        for point in points:
            screen = self._scene_to_screen(self._normalized_to_scene(point))
            painter.drawEllipse(screen, 4, 4)

        mode_color = "#9ece6a" if self.current_mode() == MODE_INPUT else "#e0af68"
        painter.setPen(QPen(QColor(mode_color), 1))
        painter.drawText(10, 20, f"Mode: {self.current_mode()}  Zoom: {self.zoom:.2f}")
