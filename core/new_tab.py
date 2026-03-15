from PySide6.QtWidgets import QWidget, QGridLayout, QPushButton

class NewTab(QWidget):

    def __init__(self, main):
        super().__init__()

        self.main = main

        grid = QGridLayout(self)

        tools = list(self.main.tools.items())
        cols = 2

        for i, (name, tool) in enumerate(tools):
            btn = QPushButton(tool.TOOL_DEFAULT_LABEL)

            row = i // cols
            col = i % cols

            grid.addWidget(btn, row, col)

            btn.clicked.connect(
                lambda _, t=tool: self.main.open_tool(t, self)
            )