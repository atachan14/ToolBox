from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QInputDialog,
    QMenu,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.tool_base import ToolBase
from tools.clamp.calculator import ClampCalculator


class Tab(ToolBase):
    TOOL_NAME = "clamp"
    TOOL_DEFAULT_LABEL = "Clamp"
    TOOL_ORDER = 10

    def __init__(self, tab_dir=None, tool_data_dir=None):
        super().__init__(tab_dir=tab_dir, tool_data_dir=tool_data_dir)
        self._restoring = True
        self._normalizing_tabs = False

        layout = QVBoxLayout()
        self.tabs = QTabWidget()
        self.tabs.setMovable(True)
        layout.addWidget(self.tabs)
        self.setLayout(layout)

        self._plus_widget = QWidget()
        self.tabs.addTab(self._plus_widget, "+")
        self._restore_state()

        self.tabs.currentChanged.connect(self._on_current_changed)
        self.tabs.tabBarClicked.connect(self._on_tab_clicked)
        self.tabs.tabBar().tabMoved.connect(self._on_tab_moved)
        self.tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self._show_tab_menu)
        self.tabs.tabBarDoubleClicked.connect(self._rename_calculator)
        QShortcut(QKeySequence("F2"), self).activated.connect(
            lambda: self._rename_calculator(self.tabs.currentIndex())
        )
        self._restoring = False

    def _calculator_widgets(self) -> list[ClampCalculator]:
        return [
            self.tabs.widget(index)
            for index in range(self.tabs.count())
            if isinstance(self.tabs.widget(index), ClampCalculator)
        ]

    def _connect_calculator(self, calculator: ClampCalculator):
        for widget in (
            calculator.min_px,
            calculator.min_view,
            calculator.max_view,
            calculator.max_px,
            calculator.reverse_input,
        ):
            widget.textChanged.connect(self._save_state)

    def _default_calculator_name(self):
        names = {
            self.tabs.tabText(self.tabs.indexOf(calculator))
            for calculator in self._calculator_widgets()
        }
        number = 1
        while str(number) in names:
            number += 1
        return str(number)

    def _add_calculator(self, name=None, state=None, select=True):
        calculator = ClampCalculator(self)
        self._connect_calculator(calculator)
        plus_index = self.tabs.indexOf(self._plus_widget)
        tab_name = str(name).strip() if name is not None else self._default_calculator_name()
        index = self.tabs.insertTab(plus_index, calculator, tab_name or self._default_calculator_name())
        if isinstance(state, dict):
            calculator.apply_state(state)
        if select:
            self.tabs.setCurrentIndex(index)
        self.calculator = calculator
        return calculator

    def _restore_state(self):
        state = self.load_state()
        if "calculators" not in state:
            calculators = [{"name": "1", **state}]
        else:
            calculators = state.get("calculators")
            if not isinstance(calculators, list):
                calculators = []

        for item in calculators:
            if not isinstance(item, dict):
                continue
            self._add_calculator(item.get("name"), item, select=False)

        active_index = state.get("active_calculator", 0)
        try:
            active_index = int(active_index)
        except (TypeError, ValueError):
            active_index = 0
        calculators = self._calculator_widgets()
        if calculators:
            self.tabs.setCurrentIndex(max(0, min(active_index, len(calculators) - 1)))
            self.calculator = self.tabs.currentWidget()
        else:
            self.tabs.setCurrentWidget(self._plus_widget)
            self.calculator = None

    def _on_current_changed(self, index):
        current = self.tabs.widget(index)
        self.calculator = current if isinstance(current, ClampCalculator) else None
        self._save_state()

    def _on_tab_clicked(self, index):
        if self.tabs.widget(index) is self._plus_widget:
            self._add_calculator(select=True)
            self._save_state()

    def _on_tab_moved(self, *_):
        if self._normalizing_tabs:
            return
        plus_index = self.tabs.indexOf(self._plus_widget)
        if plus_index != self.tabs.count() - 1:
            self._normalizing_tabs = True
            current = self.tabs.currentWidget()
            self.tabs.removeTab(plus_index)
            self.tabs.addTab(self._plus_widget, "+")
            if current is not self._plus_widget:
                self.tabs.setCurrentWidget(current)
            self._normalizing_tabs = False
        self._save_state()

    def _show_tab_menu(self, pos):
        index = self.tabs.tabBar().tabAt(pos)
        if index < 0 or self.tabs.widget(index) is self._plus_widget:
            return
        menu = QMenu(self.tabs.tabBar())
        rename_action = menu.addAction("Rename")
        close_action = menu.addAction("Close")
        action = menu.exec(self.tabs.tabBar().mapToGlobal(pos))
        if action == rename_action:
            self._rename_calculator(index)
        elif action == close_action:
            self._close_calculator(index)

    def _rename_calculator(self, index):
        if index < 0 or self.tabs.widget(index) is self._plus_widget:
            return
        old_name = self.tabs.tabText(index)
        new_name, accepted = QInputDialog.getText(
            self,
            "Rename Calculator",
            "Name:",
            text=old_name,
        )
        if not accepted or not new_name.strip():
            return
        self.tabs.setTabText(index, new_name.strip())
        self._save_state()

    def _close_calculator(self, index):
        if (
            index < 0
            or self.tabs.widget(index) is self._plus_widget
        ):
            return
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        widget.deleteLater()
        current = self.tabs.currentWidget()
        self.calculator = current if isinstance(current, ClampCalculator) else None
        self._save_state()

    def _save_state(self, *_):
        if self._restoring:
            return
        calculators = []
        active_calculator = 0
        current = self.tabs.currentWidget()
        for index, calculator in enumerate(self._calculator_widgets()):
            payload = calculator.state_payload()
            payload["name"] = self.tabs.tabText(self.tabs.indexOf(calculator))
            calculators.append(payload)
            if calculator is current:
                active_calculator = index
        self.save_state(
            {
                "calculators": calculators,
                "active_calculator": active_calculator,
            }
        )
