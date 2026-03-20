from PySide6.QtWidgets import  QVBoxLayout, QTabWidget

from tools.clamp.calculator import ClampCalculator
from tools.clamp.history import ClampHistory
from core.tool_base import ToolBase


class Tab(ToolBase):
    TOOL_NAME = "clamp"
    TOOL_DEFAULT_LABEL = "Clamp"
    TOOL_ORDER = 10

    def __init__(self, tab_dir=None, tool_data_dir=None):
        super().__init__(tab_dir=tab_dir, tool_data_dir=tool_data_dir)

        layout = QVBoxLayout()

        self.tabs = QTabWidget()

        self.calculator = ClampCalculator(self)
        history_file = self.tool_data_dir / "history.json" if self.tool_data_dir else None
        self.history = ClampHistory(
            file_path=history_file,
            on_item_click=self.calculator.run_from_history,
        )

        self.tabs.addTab(self.calculator, "Calculator")
        self.tabs.addTab(self.history, "History")

        layout.addWidget(self.tabs)

        self.setLayout(layout)

        self._restore_state()
        self._connect_state_sync()

    def _connect_state_sync(self):
        for widget in (
            self.calculator.free_input,
            self.calculator.min_px,
            self.calculator.min_view,
            self.calculator.max_view,
            self.calculator.max_px,
            self.calculator.reverse_input,
        ):
            widget.textChanged.connect(self._save_state)
        self.tabs.currentChanged.connect(self._save_state)

    def _restore_state(self):
        state = self.load_state()
        self.calculator.free_input.setText(state.get("free_input", ""))
        self.calculator.min_px.setText(state.get("min_px", ""))
        self.calculator.min_view.setText(state.get("min_view", ""))
        self.calculator.max_view.setText(state.get("max_view", ""))
        self.calculator.max_px.setText(state.get("max_px", ""))
        self.calculator.reverse_input.setText(state.get("reverse_input", ""))
        self.calculator.last_edited = state.get("last_edited")
        self.tabs.setCurrentIndex(state.get("active_tab", 0))

    def _save_state(self, *_):
        self.save_state(
            {
                "free_input": self.calculator.free_input.text(),
                "min_px": self.calculator.min_px.text(),
                "min_view": self.calculator.min_view.text(),
                "max_view": self.calculator.max_view.text(),
                "max_px": self.calculator.max_px.text(),
                "reverse_input": self.calculator.reverse_input.text(),
                "last_edited": self.calculator.last_edited,
                "active_tab": self.tabs.currentIndex(),
            }
        )
