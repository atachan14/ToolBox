from PySide6.QtWidgets import QVBoxLayout

from core.tool_base import ToolBase

from .window import ClipBoardWindow


class Tab(ToolBase):
    TOOL_NAME = "clipboard"
    TOOL_DEFAULT_LABEL = "ClipBoard"
    TOOL_ORDER = 25

    def __init__(self, tab_dir=None, tool_data_dir=None):
        super().__init__(tab_dir=tab_dir, tool_data_dir=tool_data_dir)

        layout = QVBoxLayout(self)
        data_path = self.tool_data_dir / "data.json" if self.tool_data_dir else None
        ui_path = self.tool_data_dir / "ui.json" if self.tool_data_dir else None
        self.window = ClipBoardWindow(data_path=data_path, ui_path=ui_path)
        layout.addWidget(self.window)
