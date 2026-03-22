from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QMimeData
from PySide6.QtGui import QColor, QDrag, QLinearGradient, QMouseEvent, QPainter, QPainterPath, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QStyle, QStyleOptionButton, QToolTip, QVBoxLayout, QWidget

from .color_utils import color_text_from_qcolor, parse_color_text, qcolor_from_text


def alpha_pattern_specs(color_text: str) -> tuple[QColor, QColor, float]:
    color = qcolor_from_text(color_text)
    base = QColor(color)
    base.setAlpha(255)
    alpha = color.alphaF()
    stripe_alpha = max(0.0, min(0.9, (1.0 - alpha) * 0.9))
    stripe_color = QColor("#f8fafc" if base.lightnessF() < 0.55 else "#111827")
    stripe_color.setAlphaF(stripe_alpha)
    return base, stripe_color, stripe_alpha


def alpha_pattern_text_color(color_text: str) -> str:
    base, _stripe, _alpha = alpha_pattern_specs(color_text)
    return "#111827" if base.lightnessF() > 0.62 else "#f8fafc"


def paint_alpha_pattern(painter: QPainter, rect: QRectF, color_text: str, border_color: str, border_width: int = 1, radius: float = 4.0):
    if rect.width() <= 0 or rect.height() <= 0:
        return
    base, stripe_color, stripe_alpha = alpha_pattern_specs(color_text)
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.fillPath(path, base)
    painter.setClipPath(path)
    if stripe_alpha > 0.0:
        pen = QPen(stripe_color, max(2, border_width + 1))
        painter.setPen(pen)
        spacing = 7
        start = int(rect.left()) - int(rect.height())
        end = int(rect.right()) + int(rect.height())
        bottom = int(rect.bottom())
        top = int(rect.top())
        for offset in range(start, end + spacing, spacing):
            painter.drawLine(offset, bottom, offset + int(rect.height()), top)
    painter.restore()
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(border_color), border_width))
    painter.setBrush(Qt.NoBrush)
    inset = border_width / 2.0
    painter.drawRoundedRect(rect.adjusted(inset, inset, -inset, -inset), radius, radius)
    painter.restore()


class PaletteButton(QPushButton):
    def __init__(self, color: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.color_value = color
        self._press_pos: QPoint | None = None
        self.setCheckable(True)
        self.setFixedSize(24, 24)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self._apply_style(False)

    def set_selected(self, selected: bool):
        self.setChecked(selected)
        self._apply_style(selected)

    def _apply_style(self, selected: bool):
        self._border_color = "#ffffff" if selected else "#4b5568"
        self.setText("")
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")
        self.update()

    def paintEvent(self, event):
        option = QStyleOptionButton()
        self.initStyleOption(option)
        painter = QPainter(self)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        paint_alpha_pattern(painter, rect, self.color_value, self._border_color, border_width=2, radius=4.0)
        if parse_color_text(self.color_value) == "#00000000":
            painter.setPen(QColor("#111827"))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(max(8, font.pointSize()))
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, "T")
        if self.hasFocus():
            focus = self.style().subElementRect(QStyle.SE_PushButtonFocusRect, option, self)
            pen = QPen(QColor("#4ecdc4"), 1, Qt.DotLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(focus.adjusted(2, 2, -2, -2))
        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.LeftButton) or self._press_pos is None:
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._press_pos).manhattanLength() < 4:
            super().mouseMoveEvent(event)
            return
        index = self.property("palette_index")
        if not isinstance(index, int):
            super().mouseMoveEvent(event)
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-gradient-palette-index", str(index).encode("utf-8"))
        mime.setData("application/x-gradient-color", self.color_value.encode("utf-8"))
        drag.setMimeData(mime)
        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.transparent)
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.position().toPoint())
        self._press_pos = None
        drag.exec(Qt.MoveAction)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._press_pos = None
        super().mouseReleaseEvent(event)


class ColorPreview(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._color = "#00000000"
        self.setFixedSize(40, 28)
        self._apply_style()

    def set_color(self, color: str):
        self._color = color
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet("QFrame { background: transparent; border: none; }")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        paint_alpha_pattern(painter, rect, self._color, "#6b7280", border_width=1, radius=4.0)
        event.accept()


class AlphaPatternLineEdit(QLineEdit):
    def __init__(self, color_text: str = "#00000000", parent: QWidget | None = None):
        super().__init__(parent)
        self._pattern_color = color_text
        self.setFrame(False)
        self.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: none; padding: 4px 8px; color: {alpha_pattern_text_color(color_text)}; }}"
        )

    def set_pattern_color(self, color_text: str):
        self._pattern_color = color_text
        self.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: none; padding: 4px 8px; color: {alpha_pattern_text_color(color_text)}; }}"
        )
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        paint_alpha_pattern(painter, rect, self._pattern_color, "#4b5568", border_width=1, radius=4.0)
        super().paintEvent(event)


class SaturationValuePicker(QWidget):
    def __init__(self, on_changed, parent: QWidget | None = None):
        super().__init__(parent)
        self._on_changed = on_changed
        self._hue = 0.0
        self._saturation = 1.0
        self._value = 1.0
        self.setMinimumSize(240, 180)

    def set_hsv(self, hue: float, saturation: float, value: float):
        self._hue = hue % 360.0
        self._saturation = max(0.0, min(1.0, saturation))
        self._value = max(0.0, min(1.0, value))
        self.update()

    def hsv(self) -> tuple[float, float, float]:
        return self._hue, self._saturation, self._value

    def mousePressEvent(self, event: QMouseEvent):
        self._apply_pointer(event.position())

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton:
            self._apply_pointer(event.position())

    def _apply_pointer(self, point: QPointF):
        width = max(1.0, float(self.width() - 1))
        height = max(1.0, float(self.height() - 1))
        self._saturation = max(0.0, min(1.0, point.x() / width))
        self._value = max(0.0, min(1.0, 1.0 - (point.y() / height)))
        self.update()
        self._on_changed()

    def paintEvent(self, _event):
        painter = QPainter(self)
        base = QColor()
        base.setHsvF(self._hue / 360.0, 1.0, 1.0)
        painter.fillRect(self.rect(), base)
        white = QLinearGradient(0, 0, self.width(), 0)
        white.setColorAt(0.0, QColor(255, 255, 255))
        white.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(self.rect(), white)
        black = QLinearGradient(0, 0, 0, self.height())
        black.setColorAt(0.0, QColor(0, 0, 0, 0))
        black.setColorAt(1.0, QColor(0, 0, 0))
        painter.fillRect(self.rect(), black)
        x = self._saturation * (self.width() - 1)
        y = (1.0 - self._value) * (self.height() - 1)
        painter.setPen(QColor("#ffffff"))
        painter.drawEllipse(QPointF(x, y), 5, 5)
        painter.setPen(QColor("#111827"))
        painter.drawEllipse(QPointF(x, y), 6, 6)


class HueSlider(QWidget):
    def __init__(self, on_changed, parent: QWidget | None = None):
        super().__init__(parent)
        self._on_changed = on_changed
        self._hue = 0.0
        self.setFixedHeight(20)

    def set_hue(self, hue: float):
        self._hue = hue % 360.0
        self.update()

    def hue(self) -> float:
        return self._hue

    def mousePressEvent(self, event: QMouseEvent):
        self._apply_pointer(event.position())

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton:
            self._apply_pointer(event.position())

    def _apply_pointer(self, point: QPointF):
        width = max(1.0, float(self.width() - 1))
        self._hue = max(0.0, min(359.0, (point.x() / width) * 359.0))
        self.update()
        self._on_changed()

    def paintEvent(self, _event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), 0)
        for stop, hue in ((0.0, 0), (1 / 6, 60), (2 / 6, 120), (3 / 6, 180), (4 / 6, 240), (5 / 6, 300), (1.0, 360)):
            color = QColor()
            color.setHsv(hue % 360, 255, 255)
            gradient.setColorAt(stop, color)
        painter.fillRect(self.rect(), gradient)
        x = (self._hue / 359.0) * (self.width() - 1) if self.width() > 1 else 0
        painter.setPen(QColor("#ffffff"))
        painter.drawLine(QPoint(int(x), 0), QPoint(int(x), self.height()))
        painter.setPen(QColor("#111827"))
        painter.drawLine(QPoint(int(x) + 1, 0), QPoint(int(x) + 1, self.height()))


class AlphaSlider(QWidget):
    def __init__(self, on_changed, parent: QWidget | None = None):
        super().__init__(parent)
        self._on_changed = on_changed
        self._hue = 0.0
        self._saturation = 1.0
        self._value = 1.0
        self._alpha = 1.0
        self.setFixedHeight(20)

    def set_color(self, hue: float, saturation: float, value: float, alpha: float):
        self._hue = hue % 360.0
        self._saturation = max(0.0, min(1.0, saturation))
        self._value = max(0.0, min(1.0, value))
        self._alpha = max(0.0, min(1.0, alpha))
        self.update()

    def alpha(self) -> float:
        return self._alpha

    def mousePressEvent(self, event: QMouseEvent):
        self._apply_pointer(event.position())

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton:
            self._apply_pointer(event.position())

    def _apply_pointer(self, point: QPointF):
        width = max(1.0, float(self.width() - 1))
        self._alpha = max(0.0, min(1.0, point.x() / width))
        self.update()
        self._on_changed()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#f8fafc"))
        checker = 8
        for y in range(0, self.height(), checker):
            for x in range(0, self.width(), checker):
                if ((x // checker) + (y // checker)) % 2 == 0:
                    painter.fillRect(x, y, checker, checker, QColor("#d1d5db"))
        gradient = QLinearGradient(0, 0, self.width(), 0)
        left = QColor()
        left.setHsvF(self._hue / 360.0, self._saturation, self._value, 0.0)
        right = QColor()
        right.setHsvF(self._hue / 360.0, self._saturation, self._value, 1.0)
        gradient.setColorAt(0.0, left)
        gradient.setColorAt(1.0, right)
        painter.fillRect(self.rect(), gradient)
        x = self._alpha * (self.width() - 1) if self.width() > 1 else 0
        painter.setPen(QColor("#ffffff"))
        painter.drawLine(QPoint(int(x), 0), QPoint(int(x), self.height()))
        painter.setPen(QColor("#111827"))
        painter.drawLine(QPoint(int(x) + 1, 0), QPoint(int(x) + 1, self.height()))


class SwatchDialog(QDialog):
    def __init__(self, color_text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Swatch")
        self.resize(420, 460)
        self._syncing = False
        self.original_color = color_text
        self.selected_color = color_text

        layout = QVBoxLayout(self)
        self.sv_picker = SaturationValuePicker(self._on_picker_widget_changed, self)
        self.hue_slider = HueSlider(self._on_picker_widget_changed, self)
        self.alpha_slider = AlphaSlider(self._on_picker_widget_changed, self)
        layout.addWidget(self.sv_picker)
        layout.addWidget(self.hue_slider)
        layout.addWidget(self.alpha_slider)

        self.input_edit = QLineEdit(color_text)
        layout.addWidget(self.input_edit)

        row = QHBoxLayout()
        self.old_preview = ColorPreview()
        self.old_preview.set_color(color_text)
        row.addWidget(self.old_preview)
        row.addWidget(QLabel("→"))
        self.new_preview = ColorPreview()
        self.new_preview.set_color(color_text)
        row.addWidget(self.new_preview)
        row.addStretch(1)
        self.ok_button = QPushButton("ok")
        self.cancel_button = QPushButton("cancel")
        row.addWidget(self.ok_button)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)

        self.input_edit.textChanged.connect(self._on_text_changed)
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self._set_from_color_text(color_text)

    def _set_from_color_text(self, text: str):
        color = qcolor_from_text(text)
        if color.alpha() == 0:
            hue, saturation, value, alpha = 0.0, 0.0, 0.0, 0.0
        else:
            hue = float(color.hue() if color.hue() >= 0 else 0)
            saturation = color.saturationF()
            value = color.valueF()
            alpha = color.alphaF()
        self._syncing = True
        self.selected_color = text
        self.sv_picker.set_hsv(hue, saturation, value)
        self.hue_slider.set_hue(hue)
        self.alpha_slider.set_color(hue, saturation, value, alpha)
        self.input_edit.setText(text)
        self.new_preview.set_color(text)
        self._syncing = False

    def _on_picker_widget_changed(self):
        if self._syncing:
            return
        self._syncing = True
        hue = self.hue_slider.hue()
        _h, saturation, value = self.sv_picker.hsv()
        alpha = self.alpha_slider.alpha()
        color = QColor()
        color.setHsvF(hue / 360.0, saturation, value, alpha)
        self.selected_color = color_text_from_qcolor(color)
        self.input_edit.setText(self.selected_color)
        self.new_preview.set_color(self.selected_color)
        self.sv_picker.set_hsv(hue, saturation, value)
        self.alpha_slider.set_color(hue, saturation, value, alpha)
        self._syncing = False

    def _on_text_changed(self, text: str):
        if self._syncing:
            return
        parsed = parse_color_text(text)
        if parsed is None:
            return
        self._set_from_color_text(parsed)


class CodeLineEdit(QLineEdit):
    def __init__(self, click_handler, wheel_handler, parent: QWidget | None = None):
        super().__init__(parent)
        self._click_handler = click_handler
        self._wheel_handler = wheel_handler

    def mousePressEvent(self, event: QMouseEvent):
        self._click_handler(event)
        super().mousePressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        self._wheel_handler(event)

    def enterEvent(self, event):
        if self.toolTip():
            QToolTip.showText(self.mapToGlobal(self.rect().bottomLeft()), self.toolTip(), self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        QToolTip.hideText()
        super().leaveEvent(event)
