from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QScrollArea, QSizePolicy, QTextBrowser, QVBoxLayout, QWidget

from .models import HelpDocument, HelpSection


def _font_size_for_level(level: int) -> int:
    return max(14, 24 - ((max(1, level) - 1) * 2))


class SectionMarkdownView(QTextBrowser):
    imageLinkClicked = Signal(Path)

    def __init__(self, markdown_path: Path, section: HelpSection, parent=None):
        super().__init__(parent)
        self._markdown_path = markdown_path
        self._section = section
        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)
        self.setFrameShape(QTextBrowser.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.document().setBaseUrl(QUrl.fromLocalFile(str(markdown_path.parent.resolve()) + "/"))
        self.anchorClicked.connect(self._on_anchor_clicked)
        self.setMarkdown(section.body_markdown or "")
        self.document().documentLayout().documentSizeChanged.connect(self._update_height)
        QTimer.singleShot(0, self._update_height)

    def _on_anchor_clicked(self, url: QUrl):
        target = url.toString()
        path = (self._markdown_path.parent / target).resolve()
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
            self.imageLinkClicked.emit(path)
            return
        QDesktopServices.openUrl(self.document().baseUrl().resolved(url))

    def _update_height(self, *_):
        margins = self.contentsMargins()
        doc_height = int(self.document().size().height())
        frame = self.frameWidth() * 2
        self.setFixedHeight(max(24, doc_height + margins.top() + margins.bottom() + frame + 6))

    def resizeEvent(self, event):
        self.document().setTextWidth(max(0, self.viewport().width()))
        super().resizeEvent(event)
        self._update_height()


class SectionWidget(QWidget):
    imageLinkClicked = Signal(Path)

    def __init__(self, markdown_path: Path, section: HelpSection, parent=None):
        super().__init__(parent)
        self.section = section

        layout = QVBoxLayout(self)
        has_body = bool((section.body_markdown or "").strip())
        layout.setContentsMargins(0, 0, 0, 14 if has_body else 6)
        layout.setSpacing(6)

        title = QLabel(section.title)
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        title.setStyleSheet(
            f"""
            font-weight: 700;
            font-size: {_font_size_for_level(section.level)}px;
            margin-top: 2px;
            """
        )
        layout.addWidget(title)

        self.body_view = None
        if has_body:
            self.body_view = SectionMarkdownView(markdown_path, section, self)
            self.body_view.imageLinkClicked.connect(self.imageLinkClicked.emit)
            layout.addWidget(self.body_view)


class HelpContentView(QScrollArea):
    imageLinkClicked = Signal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._section_widgets: dict[str, QWidget] = {}
        self._scroll_value = 0
        self._scroll_animation = QPropertyAnimation(self, b"animatedScrollValue", self)
        self._scroll_animation.setDuration(220)
        self._scroll_animation.setEasingCurve(QEasingCurve.OutCubic)

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(12, 12, 12, 12)
        self.container_layout.setSpacing(4)
        self.container_layout.addStretch(1)
        self.setWidget(self.container)

    def set_document(self, document: HelpDocument):
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._section_widgets = {}
        for section in document.sections:
            widget = SectionWidget(document.markdown_path, section, self.container)
            widget.imageLinkClicked.connect(self.imageLinkClicked.emit)
            self.container_layout.addWidget(widget)
            self._section_widgets[section.id] = widget
        self.container_layout.addStretch(1)
        self._scroll_animation.stop()
        self.verticalScrollBar().setValue(0)

    def get_animated_scroll_value(self) -> int:
        return self._scroll_value

    def set_animated_scroll_value(self, value: int):
        self._scroll_value = int(value)
        self.verticalScrollBar().setValue(self._scroll_value)

    animatedScrollValue = Property(int, get_animated_scroll_value, set_animated_scroll_value)

    def scroll_to_section(self, section_id: str):
        widget = self._section_widgets.get(section_id)
        if widget is None:
            return
        target = max(0, widget.y())
        current = self.verticalScrollBar().value()
        self._scroll_animation.stop()
        self._scroll_animation.setStartValue(current)
        self._scroll_animation.setEndValue(target)
        self._scroll_animation.start()
