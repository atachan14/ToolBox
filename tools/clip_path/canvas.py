from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .state import ClipPoint


class ClipPathCanvas(QWidget):

    def __init__(
        self,
        points: list[ClipPoint],
        on_points_changed: Callable[[], None],
        on_cursor_changed: Callable[[float, float], None],
        snap_enabled: Callable[[], bool],
        snap_step: Callable[[], float],
    ):
        super().__init__()

        self.points = points
        self.on_points_changed = on_points_changed
        self.on_cursor_changed = on_cursor_changed
        self.snap_enabled = snap_enabled
        self.snap_step = snap_step

        self.dragging_index: int | None = None
        self.hit_radius = 12

        self.setMouseTracking(True)
        self.setMinimumSize(260, 260)

    def _snap(self, value: float) -> float:
        if not self.snap_enabled():
            return value

        step = max(1.0, self.snap_step())

        px = value
        px = round(px / step) * step
        return px

    def _find_nearest_point(self, pos: QPointF) -> int | None:
        nearest_index = None
        nearest_distance = float("inf")

        for idx, point in enumerate(self.points):
            dx = point.x * self.width() - pos.x()
            dy = point.y * self.height() - pos.y()
            distance = (dx * dx + dy * dy) ** 0.5

            if distance < nearest_distance:
                nearest_distance = distance
                nearest_index = idx

        if nearest_distance <= self.hit_radius:
            return nearest_index

        return None

    def mousePressEvent(self, event: QMouseEvent):
        pos = event.position()

        if event.button() == Qt.LeftButton:
            hit_index = self._find_nearest_point(pos)

            if hit_index is not None:
                self.dragging_index = hit_index
                return

            w = self.width()
            h = self.height()

            self.points.append(
                ClipPoint(
                    self._snap(pos.x()) / w,
                    self._snap(pos.y()) / h,
                )
            )
            
            self.on_points_changed()
            self.update()
            return

        if event.button() == Qt.RightButton:
            hit_index = self._find_nearest_point(pos)

            if hit_index is not None:
                self.points.pop(hit_index)
                self.on_points_changed()
                self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.position()
        self.on_cursor_changed(pos.x(), pos.y())

        if self.dragging_index is None:
            return

        point = self.points[self.dragging_index]
        point.x = self._snap(pos.x()) / self.width()
        point.y = self._snap(pos.y()) / self.height()

        self.on_points_changed()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.dragging_index = None

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#20252e"))

        painter.setRenderHint(QPainter.Antialiasing)

        line_pen = QPen(QColor("#7aa2f7"), 2)
        point_pen = QPen(QColor("#f7768e"), 2)

        painter.setPen(line_pen)

        for idx in range(len(self.points) - 1):
            start = QPointF(
                self.points[idx].x * self.width(),
                self.points[idx].y * self.height()
            )
            end = QPointF(
                self.points[idx + 1].x * self.width(),
                self.points[idx + 1].y * self.height()
            )
            painter.drawLine(start, end)
            
        if len(self.points) > 2:
            first = self.points[0]
            last = self.points[-1]

            w = self.width()
            h = self.height()
            
            painter.drawLine(
                QPointF(last.x * w, last.y * h),
                QPointF(first.x * w, first.y * h),
            )

        painter.setPen(point_pen)

        for point in self.points:
            painter.drawEllipse(
                QPointF(point.x * self.width(), point.y * self.height()),
                4,
                4
            )
