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
        super().__init__()

        layout = QVBoxLayout()

        self.tabs = QTabWidget()
        
        self.calculator = ClampCalculator(self)
        self.history = ClampHistory()

        self.tabs.addTab(self.calculator, "Calculator")
        self.tabs.addTab(self.history, "History")

        layout.addWidget(self.tabs)

        self.setLayout(layout)