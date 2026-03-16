import json
from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget,QApplication,QListWidgetItem
from PySide6.QtCore import QTimer
from PySide6.QtGui import QBrush, QColor

class ClampHistory(QWidget):

    MAX_HISTORY = 50

    def __init__(self, file_path=None, on_item_click=None):
        super().__init__()

        self.file_path = Path(file_path) if file_path else None
        self.on_item_click = on_item_click
        self.entries = []

        layout = QVBoxLayout()

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.NoSelection)
        self.list.setWordWrap(True)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        # self.list.setStyleSheet("""
        #     QListWidget {
        #         font-family: Consolas, monospace;
        #     }
        #     """)

        layout.addWidget(self.list)

        self.setLayout(layout)

        self.list.itemClicked.connect(self.handle_item_click)

        self.load_history()

    def add_history(self, clamp, min_px, min_view, max_view, max_px):

        entry = {
            "clamp": clamp,
            "min_px": min_px,
            "min_view": min_view,
            "max_view": max_view,
            "max_px": max_px,
        }

        if self.entries and self.entries[0] == entry:
            return

        self.entries.insert(0, entry)
        self.entries = self.entries[:self.MAX_HISTORY]

        self.render_list()
        self.save_history()



    def handle_item_click(self, item):

        row = self.list.row(item)

        if row < 0 or row >= len(self.entries):
            return

        entry = self.entries[row]

        # コピー
        QApplication.clipboard().setText(entry.get("clamp", ""))

        original_text = item.text()

        # 文字色変更
        item.setForeground(QBrush(QColor("#4ecdc4")))
        item.setText("Copied!")

        def restore():
            if row < self.list.count():
                it = self.list.item(row)
                if it:
                    it.setForeground(QBrush())
                    it.setText(original_text)

        QTimer.singleShot(500, restore)

        if self.on_item_click:
            self.on_item_click(entry)

    def load_history(self):

        if not self.file_path or not self.file_path.exists():
            self.entries = []
            self.render_list()
            return

        try:
            data = json.loads(self.file_path.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError:
            data = []

        entries = []
        for item in data:
            if not isinstance(item, dict):
                continue
            clamp = item.get("clamp")
            if not clamp:
                continue
            entries.append(
                {
                    "clamp": str(clamp),
                    "min_px": item.get("min_px", ""),
                    "min_view": item.get("min_view", ""),
                    "max_view": item.get("max_view", ""),
                    "max_px": item.get("max_px", ""),
                }
            )

        self.entries = entries[:self.MAX_HISTORY]
        self.render_list()

    def save_history(self):

        if not self.file_path:
            return

        self.file_path.write_text(
            json.dumps(self.entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def render_list(self):

        self.list.clear()

        for entry in self.entries:

            header = f"[{entry['min_px']} , {entry['min_view']} ~ {entry['max_view']} , {entry['max_px']}]"
            clamp = entry["clamp"]

            text = f"{header}\n{clamp}"

            item = QListWidgetItem(text)
            item.setToolTip(clamp)

            self.list.addItem(item)