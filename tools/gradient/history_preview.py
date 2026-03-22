from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPixmap, QTextLayout
from PySide6.QtWidgets import QWidget


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


def build_history_preview_lines(text: str, width: int, max_lines: int, font, font_metrics: QFontMetrics) -> list[str]:
    layout = QTextLayout(text, font)
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


def history_preview_height(font_metrics: QFontMetrics, line_count: int) -> int:
    return max(1, line_count) * font_metrics.lineSpacing()


def render_history_preview_pixmap(entry: dict, size: QSize, canvas) -> QPixmap:
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
    painter.fillRect(guide_rect, background_color)
    painter.save()
    painter.setClipRect(guide_rect)

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
        guide_rect_f = QRectF(guide_rect)
        min_position, max_position = position_range_for_rect(guide_rect_f, deg)
        start_point = position_to_point(guide_rect_f, min_position, deg)
        end_point = position_to_point(guide_rect_f, max_position, deg)
        center = QPointF((start_point.x() + end_point.x()) / 2.0, (start_point.y() + end_point.y()) / 2.0)
        half_span = math.hypot(end_point.x() - start_point.x(), end_point.y() - start_point.y()) / 2.0
        thickness = max(1.0, math.hypot(guide_rect.width(), guide_rect.height()) * 2.0)
        sample_count = max(256, int(math.ceil(half_span * 2.0)))
        axis_aligned = canvas._axis_aligned_deg(deg)
        if axis_aligned in (90.0, 270.0):
            strip = canvas._build_linear_strip_image(layer, sample_count, min_position, max_position, vertical=False)
            painter.drawImage(
                QRectF(center.x() - half_span, center.y() - thickness / 2.0, half_span * 2.0, thickness),
                strip,
                QRectF(0.0, 0.0, float(strip.width()), 1.0),
            )
        elif axis_aligned in (0.0, 180.0):
            strip = canvas._build_linear_strip_image(layer, sample_count, min_position, max_position, vertical=True)
            painter.drawImage(
                QRectF(center.x() - thickness / 2.0, center.y() - half_span, thickness, half_span * 2.0),
                strip,
                QRectF(0.0, 0.0, 1.0, float(strip.height())),
            )
        else:
            strip = canvas._build_linear_strip_image(layer, sample_count, min_position, max_position, vertical=False)
            painter.save()
            painter.translate(center)
            painter.rotate(deg - 90.0)
            painter.drawImage(
                QRectF(-half_span, -thickness / 2.0, half_span * 2.0, thickness),
                strip,
                QRectF(0.0, 0.0, float(strip.width()), 1.0),
            )
            painter.restore()
    painter.restore()
    painter.setPen(QColor("#69738a"))
    painter.drawRect(guide_rect)
    painter.end()
    return pixmap
