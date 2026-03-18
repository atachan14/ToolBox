from pathlib import Path
from PySide6.QtWidgets import QVBoxLayout, QFileDialog,QPushButton
from PySide6.QtCore import Qt, QPropertyAnimation,QTimer
from core.tool_base import ToolBase
from .editor import MarkdownEditor
from .menu import MarkdownMenu


class Tab(ToolBase):

    TOOL_NAME = "markdown"
    TOOL_DEFAULT_LABEL = "MarkDown"
    TOOL_ORDER = 0
    TOOL_FILES = ["file.md"]
    
    def __init__(self, folder):
        super().__init__()

        self.folder = Path(folder)
        self.file_path = self.folder / "file.md"

        layout = QVBoxLayout(self)

        self.editor = MarkdownEditor()
        
        self.toggle_bar = QPushButton("▲")
        self.toggle_bar.setFixedHeight(22)
        self.toggle_bar.clicked.connect(self.toggle_menu)
        self.toggle_bar.setStyleSheet("""
        QPushButton {
            border: none;
            border-top: 1px solid palette(mid);
            border-bottom: 1px solid palette(mid);
            background: palette(button);
            color: palette(button-text);
            font-size: 12px;
        }
        """)
        self.toggle_bar.setCursor(Qt.PointingHandCursor)

        self.menu = MarkdownMenu()
        self.menu.setMaximumHeight(0)
        self.menu_height = self.menu.sizeHint().height()
        
        self.menu_anim = QPropertyAnimation(self.menu, b"maximumHeight")
        self.menu_anim.setDuration(150)
        
        layout.addWidget(self.editor)
        layout.addWidget(self.toggle_bar)
        layout.addWidget(self.menu)
        
        self.connect_menu()
        
        self.load_file()

        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save_file)

        self.editor.textChanged.connect(self.schedule_save)
        
    def schedule_save(self):
        self.save_timer.start(500)
        
    def connect_menu(self):

        self.menu.font_up.clicked.connect(
            lambda: self.change_font(1)
        )

        self.menu.font_down.clicked.connect(
            lambda: self.change_font(-1)
        )

        self.menu.import_btn.clicked.connect(self.import_md)
        self.menu.export_btn.clicked.connect(self.export_md)

    def change_font(self, delta):

        font = self.editor.font()

        size = font.pointSize()

        if size <= 0:
            size = 12

        size = max(8, size + delta)

        font.setPointSize(size)

        self.editor.setFont(font)

    def import_md(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Markdown",
            "",
            "Markdown (*.md);;Text (*.txt)"
        )

        if not path:
            return

        with open(path, "r", encoding="utf-8") as f:
            self.editor.setPlainText(f.read())

    def export_md(self):

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Markdown",
            "",
            "Markdown (*.md)"
        )

        if not path:
            return

        with open(path, "w", encoding="utf-8") as f:
            f.write(self.editor.toPlainText())
            
    def toggle_menu(self):

        current = self.menu.maximumHeight()

        if current == 0:
            start = 0
            end = self.menu_height
            self.toggle_bar.setText("▼")
        else:
            start = self.menu_height
            end = 0
            self.toggle_bar.setText("▲")

        self.menu_anim.stop()
        self.menu_anim.setStartValue(start)
        self.menu_anim.setEndValue(end)
        self.menu_anim.start()
        
    def load_file(self):

        if self.file_path.exists():
            text = self.file_path.read_text(encoding="utf-8")
            self.editor.setPlainText(text)

    def save_file(self):

        text = self.editor.toPlainText()

        self.file_path.write_text(text, encoding="utf-8")