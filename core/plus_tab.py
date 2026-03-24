from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QGridLayout, QMenu, QPushButton

class PlusTab(QWidget):

    def __init__(self, main):
        super().__init__()

        self.main = main

        grid = QGridLayout(self)

        tools = list(self.main.tools.items())
        cols = 2

        for i, (name, tool) in enumerate(tools):

            btn = QPushButton(tool.TOOL_DEFAULT_LABEL)
            btn.setContextMenuPolicy(Qt.CustomContextMenu)

            row = i // cols
            col = i % cols

            grid.addWidget(btn, row, col)

            btn.clicked.connect(
                lambda _, t=tool: self.main.open_tool(t)
            )
            btn.customContextMenuRequested.connect(
                lambda pos, button=btn, t=tool: self._show_tool_menu(button, t, pos)
            )

    def _show_tool_menu(self, button, tool_class, pos):
        menu = QMenu(button)
        if not tool_class.has_help():
            return
        help_action = menu.addAction(f"{tool_class.TOOL_DEFAULT_LABEL} Help")

        action = menu.exec(button.mapToGlobal(pos))
        if action == help_action:
            self.main.open_help_for_tool(tool_class)
