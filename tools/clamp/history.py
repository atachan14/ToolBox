from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QApplication


class ClampHistory(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.NoSelection)

        layout.addWidget(self.list)

        self.setLayout(layout)

        self.list.itemClicked.connect(self.copy_item)

    def add_history(self, view_range, clamp):

        text = f"[{view_range}]  {clamp}"
        
        if self.list.count() > 0:
            if self.list.item(0).text() == text:
                return

        self.list.insertItem(0, text)

        # 最大10件
        if self.list.count() > 10:
            self.list.takeItem(10)

    def copy_item(self, item):

        text = item.text()

        clamp = text.split(" ", 1)[1]

        QApplication.clipboard().setText(clamp)
        
        