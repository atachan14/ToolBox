from PySide6.QtWidgets import QVBoxLayout

from core.tool_base import ToolBase

from .window import ProgressWindow


class Tab(ToolBase):
    TOOL_NAME = "progress"
    TOOL_DEFAULT_LABEL = "Progress"
    TOOL_ORDER = 40

    def __init__(self, tab_dir=None, tool_data_dir=None):
        super().__init__(tab_dir=tab_dir, tool_data_dir=tool_data_dir)

        layout = QVBoxLayout(self)
        history_path = self.tool_data_dir / "history.json" if self.tool_data_dir else None
        self.window = ProgressWindow(state_path=self.state_path, history_path=history_path)
        layout.addWidget(self.window)

    def set_tab_dir(self, tab_dir):
        super().set_tab_dir(tab_dir)
        self.window.set_state_path(self.state_path)
