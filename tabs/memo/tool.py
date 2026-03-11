from PySide6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit


class MemoTab(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        self.editor = QPlainTextEdit()
        # self.editor.setPlaceholderText("")

        layout.addWidget(self.editor)

        self.setLayout(layout)