import json
from pathlib import Path

from PySide6.QtWidgets import QWidget


class ToolBase(QWidget):

    TOOL_NAME = "tool"
    TOOL_DEFAULT_LABEL = "Tool"
    TOOL_ORDER = 100
    TAB_FILES = []
    HELP_ENTRY = "help/index.md"

    def __init__(self, tab_dir=None, tool_data_dir=None):
        super().__init__()
        self.tab_dir = Path(tab_dir) if tab_dir else None
        self.tool_data_dir = Path(tool_data_dir) if tool_data_dir else None
        self.meta_path = self.tab_dir / "meta.json" if self.tab_dir else None
        self.state_path = self.tab_dir / "state.json" if self.tab_dir else None

    def set_tab_dir(self, tab_dir):
        self.tab_dir = Path(tab_dir) if tab_dir else None
        self.meta_path = self.tab_dir / "meta.json" if self.tab_dir else None
        self.state_path = self.tab_dir / "state.json" if self.tab_dir else None

    def load_state(self, default=None):
        default = {} if default is None else default
        if not self.state_path or not self.state_path.exists():
            return default
        try:
            loaded = json.loads(self.state_path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return default
        return loaded if isinstance(loaded, dict) else default

    def save_state(self, data):
        if not self.state_path:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def get_tool_dir(cls):
        return Path(__file__).resolve().parent.parent / "tools" / cls.TOOL_NAME.replace("-", "_")

    @classmethod
    def get_help_path(cls):
        entry = getattr(cls, "HELP_ENTRY", None)
        if not entry:
            return None
        return cls.get_tool_dir() / entry

    @classmethod
    def has_help(cls):
        path = cls.get_help_path()
        return path is not None and path.exists()
