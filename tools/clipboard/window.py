from __future__ import annotations

import json
import uuid
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QDrag, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


def _new_id() -> str:
    return uuid.uuid4().hex


def _normalize_value(payload) -> dict:
    if isinstance(payload, dict):
        return {
            "id": str(payload.get("id") or _new_id()),
            "text": str(payload.get("text") or ""),
        }
    return {"id": _new_id(), "text": str(payload or "")}


def _normalize_item(payload) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    values = payload.get("values")
    if not isinstance(values, list):
        values = []
    return {
        "id": str(payload.get("id") or _new_id()),
        "name": str(payload.get("name") or ""),
        "values": [_normalize_value(value) for value in values],
    }


def _normalize_list(payload) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    items = payload.get("items")
    if not isinstance(items, list):
        items = []
    return {
        "id": str(payload.get("id") or _new_id()),
        "name": str(payload.get("name") or ""),
        "items": [_normalize_item(item) for item in items],
    }


def _display_values(values: list[dict], editable: bool) -> list[dict]:
    rows = [_normalize_value(value) for value in values]
    if not editable:
        return rows
    return rows + [{"id": _new_id(), "text": ""}]


def _stored_values(values: list[dict]) -> list[dict]:
    return [_normalize_value(value) for value in values if str(value.get("text") or "") != ""]


class DragLabel(QLabel):
    dragStarted = Signal()
    clicked = Signal()

    def __init__(self, drag_payload: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._drag_payload = drag_payload
        self._press_pos: QPoint | None = None
        self.setCursor(Qt.OpenHandCursor)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._press_pos is None or not (event.buttons() & Qt.LeftButton):
            return super().mouseMoveEvent(event)
        distance = (event.position().toPoint() - self._press_pos).manhattanLength()
        if distance < QApplication.startDragDistance():
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self._drag_payload)
        drag.setMimeData(mime)
        self.dragStarted.emit()
        drag.exec(Qt.MoveAction)
        self._press_pos = None
        self.setCursor(Qt.OpenHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._press_pos is not None and event.button() == Qt.LeftButton:
            distance = (event.position().toPoint() - self._press_pos).manhattanLength()
            if distance < QApplication.startDragDistance():
                self.clicked.emit()
                event.accept()
                self._press_pos = None
                self.setCursor(Qt.OpenHandCursor)
                return
        self._press_pos = None
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)


class ValueRow(QFrame):
    copyRequested = Signal(str)
    reorderRequested = Signal(str, str)
    deleteRequested = Signal(str)
    changed = Signal(str, str)

    def __init__(self, item_id: str, value: dict, editable: bool, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.value_id = value["id"]
        self.setAcceptDrops(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.text_label = DragLabel(f"clipboard-value:{self.item_id}:{self.value_id}")
        self.text_label.setText(value["text"])
        self.text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.text_label.setStyleSheet("padding: 4px 6px; border: 1px solid palette(mid);")
        self.text_label.clicked.connect(lambda: self.copyRequested.emit(self.text_label.text()))

        self.text_edit = QLineEdit(value["text"])
        self.text_edit.textChanged.connect(lambda text: self.changed.emit(self.value_id, text))

        self.delete_button = QPushButton("x")
        self.delete_button.setFixedWidth(24)
        self.delete_button.clicked.connect(lambda: self.deleteRequested.emit(self.value_id))

        layout.addWidget(self.text_label, 1)
        layout.addWidget(self.text_edit, 1)
        layout.addWidget(self.delete_button)
        self.set_editable(editable)

    def set_editable(self, editable: bool):
        self.text_label.setVisible(not editable)
        self.text_edit.setVisible(editable)
        self.delete_button.setVisible(editable)

    def update_value(self, text: str, editable: bool):
        self.text_label.setText(text)
        if self.text_edit.text() != text:
            self.text_edit.blockSignals(True)
            self.text_edit.setText(text)
            self.text_edit.blockSignals(False)
        self.set_editable(editable)

    def dragEnterEvent(self, event):
        if event.mimeData().text().startswith(f"clipboard-value:{self.item_id}:"):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event):
        payload = event.mimeData().text()
        if payload.startswith(f"clipboard-value:{self.item_id}:"):
            self.reorderRequested.emit(payload.split(":")[-1], self.value_id)
            event.acceptProposedAction()
            return
        super().dropEvent(event)


class ItemCard(QFrame):
    copyRequested = Signal(str)
    addBelowRequested = Signal(str)
    deleteRequested = Signal(str)
    editToggled = Signal(str, bool)
    moveRequested = Signal(str, str)
    nameChanged = Signal(str, str)
    valueChanged = Signal(str, str, str)
    valueMoveRequested = Signal(str, str, str)
    valueDeleteRequested = Signal(str, str)

    def __init__(self, item: dict, editable: bool, parent=None):
        super().__init__(parent)
        self.item_id = item["id"]
        self._value_rows: dict[str, ValueRow] = {}
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("QFrame { border: 1px solid palette(mid); }")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        self.name_label = DragLabel(f"clipboard-item:{self.item_id}")
        self.name_label.setText(item["name"])
        self.name_label.setStyleSheet("padding: 4px 6px; border: 1px solid palette(mid); font-weight: bold;")
        self.name_label.clicked.connect(lambda: self.copyRequested.emit(self.name_label.text()))

        self.name_edit = QLineEdit(item["name"])
        self.name_edit.textChanged.connect(lambda text: self.nameChanged.emit(self.item_id, text))

        self.edit_button = QPushButton("save" if editable else "edit")
        self.edit_button.clicked.connect(lambda: self.editToggled.emit(self.item_id, not self._editable))

        header.addWidget(self.name_label, 1)
        header.addWidget(self.name_edit, 1)
        header.addWidget(self.edit_button)
        root.addLayout(header)

        self.values_layout = QVBoxLayout()
        self.values_layout.setContentsMargins(0, 0, 0, 0)
        self.values_layout.setSpacing(4)
        root.addLayout(self.values_layout)

        self._editable = False
        self.set_editable(editable)
        self.sync_values(item["values"], editable)

    def set_editable(self, editable: bool):
        self._editable = editable
        self.name_label.setVisible(not editable)
        self.name_edit.setVisible(editable)
        self.edit_button.setText("save" if editable else "edit")
        for row in self._value_rows.values():
            row.set_editable(editable)

    def sync_values(self, values: list[dict], editable: bool):
        current = set(self._value_rows.keys())
        incoming = {value["id"] for value in values}
        for value_id in current - incoming:
            row = self._value_rows.pop(value_id)
            row.deleteLater()

        while self.values_layout.count():
            item = self.values_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        for value in _display_values(values, editable):
            row = self._value_rows.get(value["id"])
            if row is None:
                row = ValueRow(self.item_id, value, editable, self)
                row.copyRequested.connect(self.copyRequested.emit)
                row.reorderRequested.connect(lambda source, target, item_id=self.item_id: self.valueMoveRequested.emit(item_id, source, target))
                row.deleteRequested.connect(lambda value_id, item_id=self.item_id: self.valueDeleteRequested.emit(item_id, value_id))
                row.changed.connect(lambda value_id, text, item_id=self.item_id: self.valueChanged.emit(item_id, value_id, text))
                self._value_rows[value["id"]] = row
            row.update_value(value["text"], editable)
            self.values_layout.addWidget(row)

    def _show_menu(self, pos):
        menu = QMenu(self)
        add_action = QAction("下にitemを追加", menu)
        delete_action = QAction("削除", menu)
        menu.addAction(add_action)
        menu.addAction(delete_action)
        action = menu.exec(self.mapToGlobal(pos))
        if action == add_action:
            self.addBelowRequested.emit(self.item_id)
        elif action == delete_action:
            self.deleteRequested.emit(self.item_id)

    def dragEnterEvent(self, event):
        if event.mimeData().text().startswith("clipboard-item:"):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event):
        payload = event.mimeData().text()
        if payload.startswith("clipboard-item:"):
            self.moveRequested.emit(payload.split(":")[-1], self.item_id)
            event.acceptProposedAction()
            return
        super().dropEvent(event)


class DraftItemCard(QFrame):
    saveRequested = Signal()
    nameChanged = Signal(str)
    valueChanged = Signal(str, str)
    valueDeleteRequested = Signal(str)

    def __init__(self, draft: dict, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("QFrame { border: 1px dashed palette(highlight); }")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        self.name_edit = QLineEdit(draft.get("name", ""))
        self.name_edit.textChanged.connect(self.nameChanged.emit)

        self.save_button = QPushButton("save")
        self.save_button.clicked.connect(self.saveRequested.emit)

        header.addWidget(self.name_edit, 1)
        header.addWidget(self.save_button)
        root.addLayout(header)

        self.values_layout = QVBoxLayout()
        self.values_layout.setContentsMargins(0, 0, 0, 0)
        self.values_layout.setSpacing(4)
        root.addLayout(self.values_layout)

        self.sync_values(draft.get("values") or [])

    def sync_values(self, values: list[dict]):
        while self.values_layout.count():
            item = self.values_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for value in _display_values(values, True):
            row = QWidget(self)
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            edit = QLineEdit(value.get("text", ""))
            edit.textChanged.connect(lambda text, value_id=value["id"]: self.valueChanged.emit(value_id, text))
            delete_button = QPushButton("x")
            delete_button.setFixedWidth(24)
            delete_button.clicked.connect(lambda _, value_id=value["id"]: self.valueDeleteRequested.emit(value_id))
            layout.addWidget(edit, 1)
            layout.addWidget(delete_button)
            self.values_layout.addWidget(row)


class ClipBoardWindow(QMainWindow):
    def __init__(self, data_path: Path | None = None, ui_path: Path | None = None):
        super().__init__()
        self.data_path = Path(data_path) if data_path else None
        self.ui_path = Path(ui_path) if ui_path else None
        self.data = {"lists": []}
        self.ui_state = {
            "selected_list_id": None,
            "list_search": "",
            "item_search": "",
            "editing_item_ids": [],
            "drafts": {},
        }
        self._feedback_timer = QTimer(self)
        self._feedback_timer.setSingleShot(True)
        self._feedback_timer.timeout.connect(self._clear_feedback)

        self._build_ui()
        self._load()
        self._refresh_ui()

    def _build_ui(self):
        self.setWindowTitle("ClipBoard")
        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        self.list_name_label = QLabel("")
        self.list_name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        top_row.addWidget(self.list_name_label, 1)

        self.new_list_button = QPushButton("新規List")
        self.new_list_button.clicked.connect(self._create_list)
        top_row.addWidget(self.new_list_button)
        root.addLayout(top_row)

        list_row = QHBoxLayout()
        list_row.setContentsMargins(0, 0, 0, 0)
        list_row.setSpacing(6)
        self.list_search_edit = QLineEdit()
        self.list_search_edit.setPlaceholderText("List検索")
        self.list_search_edit.textChanged.connect(self._on_list_search_changed)
        self.list_selector = QComboBox()
        self.list_selector.currentIndexChanged.connect(self._on_list_selector_changed)
        list_row.addWidget(self.list_search_edit, 1)
        list_row.addWidget(self.list_selector, 1)
        root.addLayout(list_row)

        self.item_search_edit = QLineEdit()
        self.item_search_edit.setPlaceholderText("item検索")
        self.item_search_edit.textChanged.connect(self._on_item_search_changed)
        root.addWidget(self.item_search_edit)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_body = QWidget()
        self.items_layout = QVBoxLayout(self.scroll_body)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(6)
        self.scroll.setWidget(self.scroll_body)
        root.addWidget(self.scroll, 1)

        self.feedback_label = QLabel("")
        self.feedback_label.setStyleSheet("color: palette(highlight);")
        root.addWidget(self.feedback_label)

        self.setCentralWidget(body)

    def _default_list(self) -> dict:
        return {"id": _new_id(), "name": "List", "items": []}

    def _load(self):
        if self.data_path and self.data_path.exists():
            try:
                loaded = json.loads(self.data_path.read_text(encoding="utf-8") or "{}")
            except json.JSONDecodeError:
                loaded = {}
            lists = loaded.get("lists") if isinstance(loaded, dict) else []
            if isinstance(lists, list):
                self.data["lists"] = [_normalize_list(item) for item in lists]
        if not self.data["lists"]:
            self.data["lists"] = [self._default_list()]
            self._save_data()

        if self.ui_path and self.ui_path.exists():
            try:
                loaded = json.loads(self.ui_path.read_text(encoding="utf-8") or "{}")
            except json.JSONDecodeError:
                loaded = {}
            if isinstance(loaded, dict):
                self.ui_state["selected_list_id"] = loaded.get("selected_list_id")
                self.ui_state["list_search"] = str(loaded.get("list_search") or "")
                self.ui_state["item_search"] = str(loaded.get("item_search") or "")
                editing = loaded.get("editing_item_ids")
                if isinstance(editing, list):
                    self.ui_state["editing_item_ids"] = [str(item) for item in editing]
                drafts = loaded.get("drafts")
                if isinstance(drafts, dict):
                    normalized_drafts: dict[str, dict] = {}
                    for list_id, draft in drafts.items():
                        if not isinstance(draft, dict):
                            continue
                        values = draft.get("values")
                        insert_index = draft.get("insert_index", 0)
                        try:
                            normalized_index = max(0, int(insert_index))
                        except (TypeError, ValueError):
                            normalized_index = 0
                        normalized_drafts[str(list_id)] = {
                            "name": str(draft.get("name") or ""),
                            "insert_index": normalized_index,
                            "values": [_normalize_value(value) for value in values] if isinstance(values, list) else [],
                        }
                    self.ui_state["drafts"] = normalized_drafts

        if not self._selected_list():
            self.ui_state["selected_list_id"] = self.data["lists"][0]["id"]
        self.list_search_edit.setText(self.ui_state["list_search"])
        self.item_search_edit.setText(self.ui_state["item_search"])

    def _save_data(self):
        if not self.data_path:
            return
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.data_path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_ui(self):
        if not self.ui_path:
            return
        self.ui_path.parent.mkdir(parents=True, exist_ok=True)
        self.ui_path.write_text(json.dumps(self.ui_state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_all(self):
        self._save_data()
        self._save_ui()

    def _filtered_lists(self) -> list[dict]:
        keyword = self.list_search_edit.text()
        if not keyword:
            return list(self.data["lists"])
        return [entry for entry in self.data["lists"] if keyword in entry["name"]]

    def _selected_list(self) -> dict | None:
        selected_id = self.ui_state.get("selected_list_id")
        for entry in self.data["lists"]:
            if entry["id"] == selected_id:
                return entry
        return None

    def _set_selected_list(self, list_id: str):
        self.ui_state["selected_list_id"] = list_id
        self._save_ui()
        self._refresh_ui()

    def _current_draft(self) -> dict:
        selected = self._selected_list()
        if selected is None:
            return {"name": "", "insert_index": 0, "values": []}
        drafts = self.ui_state["drafts"]
        draft = drafts.get(selected["id"])
        if draft is None:
            draft = {"name": "", "insert_index": len(selected["items"]), "values": []}
            drafts[selected["id"]] = draft
            self._save_ui()
        return draft

    def _refresh_ui(self):
        selected = self._selected_list()
        if selected is None and self.data["lists"]:
            selected = self.data["lists"][0]
            self.ui_state["selected_list_id"] = selected["id"]
        self.list_name_label.setText(selected["name"] if selected else "")
        self._refresh_list_selector()
        self._refresh_items()
        self._save_ui()

    def _refresh_list_selector(self):
        selected = self._selected_list()
        filtered = self._filtered_lists()
        self.list_selector.blockSignals(True)
        self.list_selector.clear()
        for entry in filtered:
            self.list_selector.addItem(entry["name"] or "(empty)", entry["id"])
        if filtered and selected is not None:
            for index in range(self.list_selector.count()):
                if self.list_selector.itemData(index) == selected["id"]:
                    self.list_selector.setCurrentIndex(index)
                    break
        self.list_selector.blockSignals(False)

    def _refresh_items(self):
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        selected = self._selected_list()
        if selected is None:
            self.items_layout.addStretch(1)
            return

        keyword = self.item_search_edit.text()
        items = selected["items"]
        filtered_ids = {item["id"] for item in items if not keyword or keyword in item["name"]}

        draft = self._current_draft()
        draft_index = len(items) if keyword else max(0, min(int(draft.get("insert_index", len(items))), len(items)))

        for index, item in enumerate(items):
            if not keyword and index == draft_index:
                self.items_layout.addWidget(self._build_draft_card(draft))
            if item["id"] not in filtered_ids:
                continue
            editable = item["id"] in self.ui_state["editing_item_ids"]
            self.items_layout.addWidget(self._build_item_card(item, editable))

        if keyword or draft_index >= len(items):
            self.items_layout.addWidget(self._build_draft_card(draft))
        self.items_layout.addStretch(1)

    def _build_item_card(self, item: dict, editable: bool) -> ItemCard:
        card = ItemCard(item, editable, self.scroll_body)
        card.copyRequested.connect(self._copy_text)
        card.addBelowRequested.connect(self._prepare_new_item_below)
        card.deleteRequested.connect(self._delete_item)
        card.editToggled.connect(self._set_item_editing)
        card.moveRequested.connect(self._move_item)
        card.nameChanged.connect(self._set_item_name)
        card.valueChanged.connect(self._set_value_text)
        card.valueMoveRequested.connect(self._move_value)
        card.valueDeleteRequested.connect(self._delete_value)
        return card

    def _build_draft_card(self, draft: dict) -> DraftItemCard:
        card = DraftItemCard(draft, self.scroll_body)
        card.nameChanged.connect(self._set_draft_name)
        card.valueChanged.connect(self._set_draft_value_text)
        card.valueDeleteRequested.connect(self._delete_draft_value)
        card.saveRequested.connect(self._commit_draft_item)
        return card

    def _on_list_search_changed(self, text: str):
        self.ui_state["list_search"] = text
        filtered = self._filtered_lists()
        selected = self._selected_list()
        if filtered and (selected is None or selected["id"] not in {entry["id"] for entry in filtered}):
            self.ui_state["selected_list_id"] = filtered[0]["id"]
        self._refresh_ui()

    def _on_item_search_changed(self, text: str):
        self.ui_state["item_search"] = text
        self._refresh_ui()

    def _on_list_selector_changed(self, index: int):
        if index < 0:
            return
        list_id = self.list_selector.itemData(index)
        if isinstance(list_id, str):
            self._set_selected_list(list_id)

    def _create_list(self):
        name, ok = QInputDialog.getText(self, "新規List", "List名")
        if not ok:
            return
        entry = {"id": _new_id(), "name": name, "items": []}
        self.data["lists"].append(entry)
        self.ui_state["selected_list_id"] = entry["id"]
        self.ui_state["drafts"][entry["id"]] = {"name": "", "insert_index": 0, "values": []}
        self._save_all()
        self._refresh_ui()

    def _prepare_new_item_below(self, item_id: str):
        selected = self._selected_list()
        if selected is None:
            return
        index = next((idx for idx, item in enumerate(selected["items"]) if item["id"] == item_id), len(selected["items"]) - 1)
        self.ui_state["drafts"][selected["id"]] = {"name": "", "insert_index": index + 1, "values": []}
        self._save_ui()
        self._refresh_ui()

    def _commit_draft_item(self):
        selected = self._selected_list()
        if selected is None:
            return
        draft = deepcopy(self._current_draft())
        item = {
            "id": _new_id(),
            "name": draft["name"],
            "values": _stored_values(draft["values"]),
        }
        insert_index = max(0, min(int(draft.get("insert_index", len(selected["items"]))), len(selected["items"])))
        selected["items"].insert(insert_index, item)
        self.ui_state["drafts"][selected["id"]] = {
            "name": "",
            "insert_index": len(selected["items"]),
            "values": [],
        }
        self._save_all()
        self._refresh_ui()

    def _set_item_editing(self, item_id: str, editing: bool):
        current = list(self.ui_state["editing_item_ids"])
        if editing and item_id not in current:
            current.append(item_id)
        if not editing:
            current = [entry for entry in current if entry != item_id]
        self.ui_state["editing_item_ids"] = current
        self._save_ui()
        self._refresh_ui()

    def _find_item(self, item_id: str) -> tuple[dict | None, dict | None]:
        selected = self._selected_list()
        if selected is None:
            return None, None
        for item in selected["items"]:
            if item["id"] == item_id:
                return selected, item
        return selected, None

    def _set_item_name(self, item_id: str, text: str):
        _selected, item = self._find_item(item_id)
        if item is None:
            return
        item["name"] = text
        self._save_data()

    def _set_value_text(self, item_id: str, value_id: str, text: str):
        _selected, item = self._find_item(item_id)
        if item is None:
            return
        if value_id not in {value["id"] for value in item["values"]}:
            item["values"].append({"id": value_id, "text": ""})
        for value in item["values"]:
            if value["id"] == value_id:
                value["text"] = text
                break
        item["values"] = _stored_values(item["values"])
        self._save_data()

    def _set_draft_name(self, text: str):
        draft = self._current_draft()
        draft["name"] = text
        self._save_ui()

    def _set_draft_value_text(self, value_id: str, text: str):
        draft = self._current_draft()
        if value_id not in {value["id"] for value in draft["values"]}:
            draft["values"].append({"id": value_id, "text": ""})
        for value in draft["values"]:
            if value["id"] == value_id:
                value["text"] = text
                break
        draft["values"] = _stored_values(draft["values"])
        self._save_ui()

    def _delete_draft_value(self, value_id: str):
        draft = self._current_draft()
        draft["values"] = [value for value in draft["values"] if value["id"] != value_id]
        self._save_ui()
        self._refresh_ui()

    def _delete_item(self, item_id: str):
        selected = self._selected_list()
        if selected is None:
            return
        selected["items"] = [item for item in selected["items"] if item["id"] != item_id]
        self.ui_state["editing_item_ids"] = [entry for entry in self.ui_state["editing_item_ids"] if entry != item_id]
        self._save_all()
        self._refresh_ui()

    def _move_item(self, source_item_id: str, target_item_id: str):
        if source_item_id == target_item_id:
            return
        selected = self._selected_list()
        if selected is None:
            return
        items = selected["items"]
        source_index = next((idx for idx, item in enumerate(items) if item["id"] == source_item_id), -1)
        target_index = next((idx for idx, item in enumerate(items) if item["id"] == target_item_id), -1)
        if source_index < 0 or target_index < 0:
            return
        item = items.pop(source_index)
        if source_index < target_index:
            target_index -= 1
        items.insert(target_index, item)
        self._save_data()
        self._refresh_ui()

    def _move_value(self, item_id: str, source_value_id: str, target_value_id: str):
        _selected, item = self._find_item(item_id)
        if item is None or source_value_id == target_value_id:
            return
        values = item["values"]
        source_index = next((idx for idx, value in enumerate(values) if value["id"] == source_value_id), -1)
        target_index = next((idx for idx, value in enumerate(values) if value["id"] == target_value_id), -1)
        if source_index < 0 or target_index < 0:
            return
        value = values.pop(source_index)
        if source_index < target_index:
            target_index -= 1
        values.insert(target_index, value)
        self._save_data()
        self._refresh_ui()

    def _delete_value(self, item_id: str, value_id: str):
        _selected, item = self._find_item(item_id)
        if item is None:
            return
        item["values"] = [value for value in item["values"] if value["id"] != value_id]
        self._save_data()
        self._refresh_ui()

    def _copy_text(self, text: str):
        QApplication.clipboard().setText(text)
        self.feedback_label.setText(f"copied: {text}")
        self._feedback_timer.start(900)

    def _clear_feedback(self):
        self.feedback_label.setText("")
