from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QPushButton,
    QHBoxLayout
)


class NewTab(QWidget):

    def __init__(self, main):
        super().__init__()

        self.main = main

        root = QVBoxLayout(self)

        # 中央に寄せるコンテナ
        center = QHBoxLayout()
        root.addLayout(center)
        root.addStretch()

        # 固定幅のボックス
        box = QWidget()
        box.setMaximumWidth(300)

        grid = QGridLayout(box)
        grid.setSpacing(12)

        memo = QPushButton("Memo")
        clamp = QPushButton("Clamp")

        memo.setMinimumHeight(40)
        clamp.setMinimumHeight(40)

        grid.addWidget(memo, 0, 0)
        grid.addWidget(clamp, 0, 1)

        memo.clicked.connect(lambda: self.main.replace_tab(self, "Memo"))
        clamp.clicked.connect(lambda: self.main.replace_tab(self, "Clamp"))

        center.addStretch()
        center.addWidget(box)
        center.addStretch()

        root.addStretch()