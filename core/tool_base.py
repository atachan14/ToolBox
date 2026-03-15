from PySide6.QtWidgets import QWidget


class ToolBase(QWidget):

    TOOL_NAME = "tool"
    TOOL_DEFAULT_LABEL = "Tool"
    TOOL_ORDER = 100
    TOOL_FILES = []
    
    def __init__(self, folder=None):
        super().__init__()
        self.folder = folder