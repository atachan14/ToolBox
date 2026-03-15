from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtCore import Qt
from .highlighter import MarkdownHighlighter
from core.paths import TABS_DIR

class MarkdownEditor(QPlainTextEdit):

    def __init__(self):
        super().__init__()

        MarkdownHighlighter(self.document())
        self.setTabStopDistance(20)
        
    def wheelEvent(self, event):

        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()

            parent = self.parent()

            if hasattr(parent, "change_font"):
                parent.change_font(1 if delta > 0 else -1)

        else:
            super().wheelEvent(event)
            