from PySide6.QtWidgets import (
    QFrame, QPushButton, QWidget,
    QHBoxLayout
)

from core.flow_layout import FlowLayout  


class MarkdownMenu(QFrame):

    def __init__(self):
        super().__init__()

        layout = FlowLayout(self)

        # --- group1 ---
        g1 = QWidget()
        g1_l = QHBoxLayout(g1)
        g1_l.setContentsMargins(0,0,0,0)

        self.font_down = QPushButton("-")
        self.font_up = QPushButton("+")
        g1_l.addWidget(self.font_down)
        g1_l.addWidget(self.font_up)

        # --- group2 ---
        g2 = QWidget()
        g2_l = QHBoxLayout(g2)
        g2_l.setContentsMargins(0,0,0,0)

        self.import_btn = QPushButton("import")
        self.export_btn = QPushButton("export")
        g2_l.addWidget(self.import_btn)
        g2_l.addWidget(self.export_btn)

        # --- group3 ---

        layout.addWidget(g1)
        layout.addWidget(g2)

        layout.setContentsMargins(6,4,6,4)

        self.setObjectName("md-menu")
        self.setStyleSheet("""
        #md-menu {
            border-top:1px solid #333;
        }
        """)