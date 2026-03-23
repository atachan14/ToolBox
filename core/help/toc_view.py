from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from .models import HelpDocument


class HelpTocView(QTreeWidget):
    sectionSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(10)
        self.itemClicked.connect(self._on_item_clicked)

    def set_document(self, document: HelpDocument):
        self.clear()
        items: dict[str, QTreeWidgetItem] = {}
        for section in document.sections:
            item = QTreeWidgetItem([section.title])
            item.setData(0, 0x0100, section.id)
            if section.parent_id and section.parent_id in items:
                items[section.parent_id].addChild(item)
            else:
                self.addTopLevelItem(item)
            items[section.id] = item
        self.expandToDepth(0)
        if self.topLevelItemCount() > 0:
            self.setCurrentItem(self.topLevelItem(0))

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int):
        section_id = item.data(0, 0x0100)
        if isinstance(section_id, str):
            self.sectionSelected.emit(section_id)
