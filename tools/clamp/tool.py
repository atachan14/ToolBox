from pathlib import Path

from PySide6.QtWidgets import  QVBoxLayout, QTabWidget

from tools.clamp.calculator import ClampCalculator
from tools.clamp.history import ClampHistory
from core.tool_base import ToolBase


class Tab(ToolBase):
    TOOL_NAME = "clamp"
    TOOL_DEFAULT_LABEL = "Clamp"
    TOOL_ORDER = 10
    
    TOOL_FILES = ["history.json"]
    def __init__(self, folder=None):
        super().__init__(folder)

        self.folder = Path(folder) if folder else None

        layout = QVBoxLayout()

        self.tabs = QTabWidget()

        self.calculator = ClampCalculator(self)
        history_file = self.folder / "history.json" if self.folder else None
        self.history = ClampHistory(
            file_path=history_file,
            on_item_click=self.calculator.run_from_history,
        )

        self.tabs.addTab(self.calculator, "Calculator")
        self.tabs.addTab(self.history, "History")

        layout.addWidget(self.tabs)

        self.setLayout(layout)