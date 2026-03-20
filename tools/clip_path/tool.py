from PySide6.QtWidgets import QVBoxLayout

from core.tool_base import ToolBase
from .window import ClipPathWindow


class Tab(ToolBase):
    TOOL_NAME = "clip-path"
    TOOL_DEFAULT_LABEL = "Clip-Path"
    TOOL_ORDER = 20

    def __init__(self, folder=None):
        super().__init__(folder)

        layout = QVBoxLayout(self)

        self.window = ClipPathWindow()
        layout.addWidget(self.window)
