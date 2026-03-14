from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget

from tabs.clamp.calculator import ClampCalculator
from tabs.clamp.history import ClampHistory


class ClampTab(QWidget):
    TOOL_NAME = "Clamp"
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        self.tabs = QTabWidget()
        
        self.calculator = ClampCalculator(self)
        self.history = ClampHistory()

        self.tabs.addTab(self.calculator, "Calculator")
        self.tabs.addTab(self.history, "History")

        layout.addWidget(self.tabs)

        self.setLayout(layout)