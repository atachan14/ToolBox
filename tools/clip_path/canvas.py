from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget

from .state import MODE_CIRCLE, MODE_INPUT, MODE_VIEW, CircleGuide, ClipPoint


@dataclass
class CanvasConfig:
    mode_getter: Callable[[], str]
    points_getter: Callable[[], list[ClipPoint]]
    size_getter: Callable[[], tuple[float, float, str]]
    grid_getter: Callable[[], tuple[bool, int]]
    circles_getter: Callable[[], list[CircleGuide]]
    snap_points_getter: Callable[[], list[ClipPoint]]
    on_points_changed: Callable[[], None]
    on_cursor_changed: Callable[[ClipPoint, ClipPoint], None]
    on_push_history: Callable[[], None]
    on_circle_created: Callable[[ClipPoint, ClipPoint], None]
    on_circle_removed: Callable[[int], None]


class ClipPathCanvas(QWidget):

    def __init__(self, config: CanvasConfig):
        super().__init__()

        self.config = config

        self.dragging_index: int | None = None
        self.pending_insert_index: int | None = None
        self.panning = False
        self.circle_drag_start: ClipPoint | None = None
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
        snapped = point

        if active:
            step_x, step_y = self._grid_steps_normalized(max(1, grid_value))
            snapped = ClipPoint(
                round(point.x / step_x) * step_x,
                round(point.y / step_y) * step_y,
            )

        return self._snap_to_snap_points(snapped)

    def _snap_to_snap_points(self, point: ClipPoint) -> ClipPoint:
        snap_points = self.config.snap_points_getter()
        if not snap_points:
            return point

        guide = self._guide_rect_scene()
        threshold_nx = 12.0 / max(guide.width(), 1.0)
        threshold_ny = 12.0 / max(guide.height(), 1.0)
        threshold = max(threshold_nx, threshold_ny)

        best = point
        best_dist = float("inf")

        for snap in snap_points:
            dx = snap.x - point.x
            dy = snap.y - point.y
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best = snap

        return best if best_dist <= threshold else point

    def _grid_steps_normalized(self, grid_value: int) -> tuple[float, float]:
        size_w, size_h, unit = self.config.size_getter()

        if unit == "px":
            step_x = grid_value / max(size_w, 1.0)
            step_y = grid_value / max(size_h, 1.0)
            return max(step_x, 1e-6), max(step_y, 1e-6)

        step = grid_value / 100.0
        return max(step, 1e-6), max(step, 1e-6)

    def _grid_steps_normalized(self, grid_value: int) -> tuple[float, float]:
        size_w, size_h, unit = self.config.size_getter()

        if unit == "px":
            step_x = grid_value / max(size_w, 1.0)
            step_y = grid_value / max(size_h, 1.0)
            return max(step_x, 1e-6), max(step_y, 1e-6)

        step = grid_value / 100.0
        return max(step, 1e-6), max(step, 1e-6)

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

        if event.button() == Qt.MiddleButton:
            self.panning = True
            return

        if mode != MODE_INPUT:
            if mode == MODE_CIRCLE:
                self._handle_circle_press(event, scene_pos)
            return

        if event.button() == Qt.LeftButton:
            hit_idx = self._find_hit_point(scene_pos)

            if hit_idx is not None:
                self.config.on_push_history()
                self.dragging_index = hit_idx
                return

            normalized = self._scene_to_normalized(scene_pos)
            self.config.on_push_history()
            points.append(self._snap_normalized(normalized))
            self.pending_insert_index = len(points) - 1
            self.config.on_points_changed()
            self.update()
            return

        if event.button() == Qt.RightButton:
            hit_idx = self._find_hit_point(scene_pos)

            if hit_idx is not None:
                self.config.on_push_history()
                points.pop(hit_idx)
                self.config.on_points_changed()
                self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        scene_pos = self._screen_to_scene(event.position())
        normalized_raw = self._scene_to_normalized(scene_pos)
        normalized_snapped = self._snap_normalized(normalized_raw)
        self.config.on_cursor_changed(normalized_raw, normalized_snapped)

        points = self.config.points_getter()

        if self.panning:
            delta = event.position() - self.last_mouse_screen
            self.pan += delta
            self.last_mouse_screen = event.position()
            self.update()
            return

        active_idx = self.dragging_index

        if active_idx is None:
            active_idx = self.pending_insert_index

        if active_idx is None:
            return

        points[active_idx] = normalized_snapped

        self.config.on_points_changed()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if self.current_mode() == MODE_CIRCLE and self.circle_drag_start is not None:
                end = self._snap_normalized(self._scene_to_normalized(self._screen_to_scene(event.position())))
                self.config.on_circle_created(self.circle_drag_start, end)
                self.circle_drag_start = None
            self.dragging_index = None
            self.pending_insert_index = None
            self.panning = False
            return

        if event.button() == Qt.MiddleButton:
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
            step_nx, step_ny = self._grid_steps_normalized(max(1, grid_value))
            step_x = guide.width() * step_nx
            step_y = guide.height() * step_ny
            screen_rect = self.rect()
            scene_top_left = self._screen_to_scene(screen_rect.topLeft())
            scene_bottom_right = self._screen_to_scene(screen_rect.bottomRight())

            x_start_idx = int((scene_top_left.x() - guide.x()) // step_x) - 1
            x_end_idx = int((scene_bottom_right.x() - guide.x()) // step_x) + 1
            y_start_idx = int((scene_top_left.y() - guide.y()) // step_y) - 1
            y_end_idx = int((scene_bottom_right.y() - guide.y()) // step_y) + 1

            for idx in range(x_start_idx, x_end_idx + 1):
                x = guide.x() + step_x * idx
                sx = self._scene_to_screen(QPointF(x, 0)).x()
                painter.drawLine(
                    QPointF(sx, float(screen_rect.top())),
                    QPointF(sx, float(screen_rect.bottom())),
                )

            for idx in range(y_start_idx, y_end_idx + 1):
                y = guide.y() + step_y * idx
                sy = self._scene_to_screen(QPointF(0, y)).y()
                painter.drawLine(
                    QPointF(float(screen_rect.left()), sy),
                    QPointF(float(screen_rect.right()), sy),
                )

        points = self.config.points_getter()
        circles = self.config.circles_getter()

        painter.setPen(QPen(QColor("#7aa2f7"), 2))

        for idx in range(len(points) - 1):
            start = self._scene_to_screen(self._normalized_to_scene(points[idx]))
            end = self._scene_to_screen(self._normalized_to_scene(points[idx + 1]))
            painter.drawLine(start, end)
        if len(points) > 2:
            start = self._scene_to_screen(self._normalized_to_scene(points[-1]))
            end = self._scene_to_screen(self._normalized_to_scene(points[0]))
            painter.drawLine(start, end)

        painter.setPen(QPen(QColor("#f7768e"), 2))

        for point in points:
            screen = self._scene_to_screen(self._normalized_to_scene(point))
            painter.drawEllipse(screen, 4, 4)

        painter.setPen(QPen(QColor("#9ece6a"), 1))
        for circle in circles:
            center = self._scene_to_screen(self._normalized_to_scene(circle.center))
            guide = self._guide_rect_scene()
            rx = circle.radius * guide.width() * self.zoom
            ry = circle.radius * guide.height() * self.zoom
            painter.drawEllipse(center, rx, ry)
            for snap in circle.snap_points:
                snap_screen = self._scene_to_screen(self._normalized_to_scene(snap))
                painter.drawEllipse(snap_screen, 3, 3)

        mode_color = "#9ece6a" if self.current_mode() == MODE_INPUT else "#e0af68"
        painter.setPen(QPen(QColor(mode_color), 1))
        painter.drawText(10, 20, f"Mode: {self.current_mode()}  Zoom: {self.zoom:.2f}")

    def _handle_circle_press(self, event: QMouseEvent, scene_pos: QPointF):
        if event.button() == Qt.LeftButton:
            self.circle_drag_start = self._snap_normalized(self._scene_to_normalized(scene_pos))
            return

        if event.button() != Qt.RightButton:
            return

        point = self._scene_to_normalized(scene_pos)
        circles = self.config.circles_getter()
        for idx, circle in enumerate(circles):
            dx = point.x - circle.center.x
            dy = point.y - circle.center.y
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= circle.radius * 1.15:
                self.config.on_push_history()
                self.config.on_circle_removed(idx)
                self.config.on_points_changed()
                self.update()
                return
