from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton


class MarkdownMenu(QFrame):

    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)

        self.font_down = QPushButton("-")
        self.font_up = QPushButton("+")
        self.import_btn = QPushButton("import")
        self.export_btn = QPushButton("export")
        self.preview_btn = QPushButton("preview")

        layout.addWidget(self.font_down)
        layout.addWidget(self.font_up)
        layout.addStretch()
        layout.addWidget(self.import_btn)
        layout.addWidget(self.export_btn)
        layout.addWidget(self.preview_btn)
        layout.setContentsMargins(6,4,6,4)
        
        self.setObjectName("md-menu")
        self.setStyleSheet("""
        #md-menu {
            border-top:1px solid #333;
        }
        """)