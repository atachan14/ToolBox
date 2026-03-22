from PySide6.QtWidgets import QVBoxLayout

from core.tool_base import ToolBase
from .window import GradientWindow


class Tab(ToolBase):
    TOOL_NAME = "gradient"
    TOOL_DEFAULT_LABEL = "Gradient"
    TOOL_ORDER = 30

    def __init__(self, tab_dir=None, tool_data_dir=None):
        super().__init__(tab_dir=tab_dir, tool_data_dir=tool_data_dir)

        layout = QVBoxLayout(self)
        history_path = self.tool_data_dir / "history.json" if self.tool_data_dir else None
        self.window = GradientWindow(state_path=self.state_path, history_path=history_path, tool_data_dir=self.tool_data_dir)
        layout.addWidget(self.window)

    def set_tab_dir(self, tab_dir):
        super().set_tab_dir(tab_dir)
        self.window.set_state_path(self.state_path)
