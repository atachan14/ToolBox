from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPalette, QPen, QShortcut
from PySide6.QtCore import QEvent, QSettings, Qt, QTimer, Signal
import sys
from core.flow_layout import FlowLayout
from core.help import HelpWindow
from core.migration import migrate_user_data
from core.plus_tab import PlusTab
from core.tool_loader import load_tools
from core.paths import TABS_DIR
from core.version import VERSION
from core.tab_storage import (
    create_tab_folder,
    ensure_tool_data_dir,
    iter_saved_tabs,
    iter_trashed_tabs,
    load_tab_meta,
    move_tab_to_trash,
    restore_tab_from_trash,
    save_tab_meta,
)

IS_WINDOWS = sys.platform.startswith("win")

if IS_WINDOWS:
    import win32con
    import win32gui


def _mix_colors(base, overlay, ratio):
    ratio = max(0.0, min(1.0, ratio))
    inv = 1.0 - ratio
    return QColor(
        round(base.red() * inv + overlay.red() * ratio),
        round(base.green() * inv + overlay.green() * ratio),
        round(base.blue() * inv + overlay.blue() * ratio),
        round(base.alpha() * inv + overlay.alpha() * ratio),
    )


class CloseTabButton(QToolButton):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._background = QColor("transparent")
        self._hover_background = QColor("transparent")
        self._border = QColor("transparent")
        self._icon = QColor("black")
        self._hovered = False
        self.setCursor(Qt.PointingHandCursor)
        self.setAutoRaise(True)
        self.setFixedSize(14, 14)

    def set_colors(self, background, hover_background, border, icon):
        self._background = QColor(background)
        self._hover_background = QColor(hover_background)
        self._border = QColor(border)
        self._icon = QColor(icon)
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "_refresh_style"):
            parent._refresh_style()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "_refresh_style"):
            parent._refresh_style()
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        painter.fillRect(self.rect(), self._hover_background if self._hovered else self._background)
        painter.setPen(QPen(self._border))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        pen = QPen(self._icon)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawLine(4, 4, 9, 9)
        painter.drawLine(9, 4, 4, 9)


class RestoreTabsDialog(QDialog):

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Restore Closed Tab")
        self.resize(360, 320)
        self.selected_folder_name = None

        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        for item in reversed(items):
            label = item["folder_name"]
            deleted_at = item.get("deleted_at")
            if deleted_at:
                label = f"{label} ({deleted_at})"
            list_item = QListWidgetItem(label)
            list_item.setData(Qt.UserRole, item["folder_name"])
            self.list_widget.addItem(list_item)
        self.list_widget.itemDoubleClicked.connect(self._restore_selected)
        layout.addWidget(self.list_widget)

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        restore_button = QPushButton("Restore")
        restore_button.clicked.connect(self._restore_selected)
        button_row.addWidget(restore_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_row.addWidget(cancel_button)

        layout.addLayout(button_row)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _restore_selected(self):
        item = self.list_widget.currentItem()
        if item is None:
            return
        self.selected_folder_name = item.data(Qt.UserRole)
        self.accept()

class MainWindow(QMainWindow):
    


    def __init__(self):
        super().__init__()
        
        self.always_on_top = False
        self.help_windows = {}
        QShortcut(QKeySequence("Alt+W"), self, self.toggle_always_on_top)
        QShortcut(QKeySequence("F2"), self, self.rename_current_hover_tab)

        self.tools = load_tools()
        migrate_user_data()

        self.settings = QSettings("toolbox", "toolbox")

        self.setWindowTitle(f"ToolBox v{VERSION}")

        self.tabs = WrappedTabWidget()
        self.tabs.tabBar().setMovable(True)
        self.tabs.setTabsClosable(True)
        
        self.tabs.tabCloseRequested.connect(self.close_tab)

        # --- wrapper作成 ---
        wrapper = QWidget()
        wrapper.setObjectName("window_frame")  # ←これ追加
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(3, 3, 3, 3)  # ←これが“枠の太さ”
        layout.addWidget(self.tabs)

        self.wrapper = wrapper  # ←後で使うから保持

        self.setCentralWidget(wrapper)

        self.add_plus_tab()
        
        # 前回のサイズを復元
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(400, 800)
        
        self.restore_tabs()

    def add_plus_tab(self):

        plus_tab = PlusTab(self)

        index = self.tabs.addTab(plus_tab, "+")
        self.tabs.tabBar().setTabClosable(index, False)

    def close_tab(self, index):

        if self.tabs.tabText(index) == "+":
            return

        tab_name = self.tabs.tabText(index)
        move_tab_to_trash(tab_name)

        self.tabs.removeTab(index)
        
    def closeEvent(self, event):

        self.settings.setValue("geometry", self.saveGeometry())

        self.save_tab_order()

        super().closeEvent(event)
        
    def save_tab_order(self):

        for i in range(self.tabs.count()):

            tab_name = self.tabs.tabText(i)

            if tab_name == "+":
                continue

            folder = TABS_DIR / tab_name
            if not folder.exists():
                continue

            data = load_tab_meta(folder)
            if not data:
                continue
            data["order"] = i
            data["label"] = folder.name
            save_tab_meta(folder, data)
        
    def open_tool(self, tool_class, replace_widget=None):

        tab_name, folder, tool_data_dir = create_tab_folder(tool_class)

        widget = tool_class(tab_dir=folder, tool_data_dir=tool_data_dir)

        if replace_widget:
            index = self.tabs.indexOf(replace_widget)

            self.tabs.removeTab(index)
            self.tabs.insertTab(index, widget, tab_name)
            self.tabs.setCurrentIndex(index)

        else:
            plus_index = self.tabs.count() - 1

            self.tabs.insertTab(plus_index, widget, tab_name)
            self.tabs.setCurrentIndex(plus_index)

    def restore_closed_tab(self):
        items = iter_trashed_tabs()
        if not items:
            QMessageBox.information(self, "Restore Closed Tab", "No closed tabs found.")
            return

        dialog = RestoreTabsDialog(items, self)
        if dialog.exec() != QDialog.Accepted or not dialog.selected_folder_name:
            return

        selected = next(
            (item for item in items if item["folder_name"] == dialog.selected_folder_name),
            None,
        )
        if selected is None:
            QMessageBox.warning(self, "Restore Failed", "The selected tab no longer exists.")
            return

        meta = selected["meta"]
        tool_name = meta.get("tool")
        tool_class = self.tools.get(tool_name)
        if not tool_class:
            QMessageBox.warning(self, "Restore Failed", "The tool for this tab is not available.")
            return

        folder = restore_tab_from_trash(dialog.selected_folder_name)
        if folder is None:
            QMessageBox.warning(self, "Restore Failed", "Could not restore the selected tab.")
            return

        widget = tool_class(
            tab_dir=folder,
            tool_data_dir=ensure_tool_data_dir(tool_name),
        )
        plus_index = self.tabs.count() - 1
        self.tabs.insertTab(plus_index, widget, folder.name)
        self.tabs.setCurrentIndex(plus_index)
            
    def restore_tabs(self):
        for _, folder, data in iter_saved_tabs():

            tool_name = data.get("tool")
            tool_class = self.tools.get(tool_name)

            if not tool_class:
                continue

            widget = tool_class(
                tab_dir=folder,
                tool_data_dir=ensure_tool_data_dir(tool_name),
            )

            plus_index = self.tabs.count() - 1
            self.tabs.insertTab(plus_index, widget, folder.name)
        
    def rename_tab(self, index):

        old_name = self.tabs.tabText(index)

        new_name, ok = QInputDialog.getText(
            self,
            "Rename Tab",
            "New name:",
            text=old_name
        )

        if not ok:
            return

        new_name = new_name.strip()

        if not new_name:
            return

        invalid_chars = r'\/:*?"<>|'

        if any(c in new_name for c in invalid_chars):
            QMessageBox.warning(
                self,
                "Invalid Name",
                "Tab名に使用できない文字が含まれています。"
            )
            return

        old_path = TABS_DIR / old_name
        new_path = TABS_DIR / new_name

        if new_path.exists():
            QMessageBox.warning(
                self,
                "Name Exists",
                "同じTab名は利用できません"
            )
            return

        try:
            old_path.rename(new_path)
        except OSError:
            QMessageBox.warning(self, "Error", "Rename failed.")
            return

        widget = self.tabs._stack.widget(index)
        if widget is not None and hasattr(widget, "set_tab_dir"):
            widget.set_tab_dir(new_path)

        meta = load_tab_meta(new_path)
        if meta:
            meta["label"] = new_name
            save_tab_meta(new_path, meta)

        self.tabs.setTabText(index, new_name)
        
    def rename_current_hover_tab(self):

        tabbar = self.tabs.tabBar()
        index = tabbar.hovered_index
        if index < 0:
            index = self.tabs.currentIndex()

        if index < 0:
            return

        if self.tabs.tabText(index) == "+":
            return

        self.rename_tab(index)

    # WindowStaysOnTopHintだと切り替え時にチラつくためwin32guiを使用        
    def toggle_always_on_top(self):
        self.always_on_top = not self.always_on_top

        if IS_WINDOWS:
            hwnd = int(self.winId())

            if self.always_on_top:
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                )
            else:
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_NOTOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                )
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, self.always_on_top)
            self.show()

        # 見た目更新（今までのやつそのまま使える）
        if self.always_on_top:
            self.wrapper.setStyleSheet("""
                #window_frame {
                    border-top: 3px solid #4ecdc4;
                }
            """)
        else:
            self.wrapper.setStyleSheet("")

    def open_help_for_tab(self, index):
        widget = self.tabs.widget(index)
        if widget is None or not hasattr(widget.__class__, "has_help"):
            return
        self.open_help_for_tool(widget.__class__)

    def open_help_for_tool(self, tool_class):
        help_path = tool_class.get_help_path()
        if help_path is None or not help_path.exists():
            QMessageBox.information(self, "Help", "Help is not available.")
            return

        tool_name = tool_class.TOOL_NAME
        title = f"{tool_class.TOOL_DEFAULT_LABEL} Help"
        window = self.help_windows.get(tool_name)

        if window is None:
            window = HelpWindow(title, help_path, self)
            window.destroyed.connect(lambda *_, name=tool_name: self.help_windows.pop(name, None))
            self.help_windows[tool_name] = window
        else:
            window.setWindowTitle(title)
            window.reload()

        window.show()
        window.raise_()
        window.activateWindow()
                 
class WrappedTabButton(QWidget):

    clicked = Signal()
    close_requested = Signal()
    hovered = Signal(bool)
    drag_requested = Signal(object)
    context_requested = Signal(object)

    def __init__(self, text):
        super().__init__()
        self._current = False
        self._hovered = False
        self._drag_start = None
        self.setObjectName("wrapped_tab_button")

        self.setAttribute(Qt.WA_Hover, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 4, 4)
        layout.setSpacing(3)

        self.label = QLabel(text)
        layout.addWidget(self.label)

        self.close_button = CloseTabButton()
        self.close_button.setObjectName("wrapped_tab_close")
        self.close_button.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.close_button)

        self.set_current(False)

    def text(self):
        return self.label.text()

    def set_text(self, text):
        self.label.setText(text)
        self.updateGeometry()

    def set_current(self, current):
        self._current = current
        self._refresh_style()

    def set_closable(self, closable):
        self.close_button.setVisible(closable)
        right_margin = 4 if closable else 10
        self.layout().setContentsMargins(10, 4, right_margin, 4)
        self.updateGeometry()

    def enterEvent(self, event):
        self._hovered = True
        self.hovered.emit(True)
        self._refresh_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.hovered.emit(False)
        self._refresh_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.position().toPoint()
            self.clicked.emit()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start is None:
            return super().mouseMoveEvent(event)

        if not (event.buttons() & Qt.LeftButton):
            return super().mouseMoveEvent(event)

        distance = (event.position().toPoint() - self._drag_start).manhattanLength()
        if distance >= QApplication.startDragDistance():
            self.drag_requested.emit(event.globalPosition().toPoint())

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        self.context_requested.emit(event.globalPos())
        event.accept()

    def _refresh_style(self):
        app = QApplication.instance()
        palette = app.palette() if app is not None else self.style().standardPalette()
        panel = palette.color(QPalette.ColorRole.Window)
        background = palette.color(QPalette.ColorRole.Button)
        border = palette.color(QPalette.ColorRole.Mid)
        accent = palette.color(QPalette.ColorRole.Highlight)
        text = palette.color(QPalette.ColorRole.ButtonText)
        close_text = palette.color(QPalette.ColorRole.Text)
        outer_border = _mix_colors(background, border, 0.65)
        hover_fill = _mix_colors(background, accent, 0.14)
        selected_fill = _mix_colors(panel, accent, 0.22)
        hover_border = _mix_colors(outer_border, accent, 0.32)
        selected_border = _mix_colors(outer_border, accent, 0.48)
        inactive_top = _mix_colors(background, border, 0.22)
        hover_top = _mix_colors(accent, panel, 0.28)
        close_fill = _mix_colors(background, panel, 0.18)
        close_border = _mix_colors(outer_border, border, 0.35)

        fill = selected_fill if self._current else hover_fill if self._hovered else background
        edge = selected_border if self._current else hover_border if self._hovered else outer_border
        top_line = accent if self._current else hover_top if self._hovered else inactive_top
        close_hover_fill = _mix_colors(close_fill, accent, 0.18)
        close_border_hover = _mix_colors(close_border, accent, 0.22)

        self.setStyleSheet(
            f"""
            QWidget#wrapped_tab_button {{
                background: {fill.name()};
                color: {text.name()};
                border-left: 1px solid {edge.name()};
                border-right: 1px solid {edge.name()};
                border-bottom: 1px solid {edge.name()};
                border-top: 3px solid {top_line.name()};
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                color: {text.name()};
            }}
            QWidget#wrapped_tab_button QLabel {{
                border-top: none;
                border-left: none;
                border-right: none;
                border-bottom: none;
            }}
            QToolButton#wrapped_tab_close {{
                background: transparent;
                border: none;
                padding: 0;
            }}
            """
        )
        self.close_button.set_colors(
            QColor("transparent"),
            close_hover_fill,
            close_border_hover if self.close_button._hovered else close_border,
            text if self.close_button._hovered else close_text,
        )


class FixedTabBar(QWidget):

    currentChanged = Signal(int)
    tabCloseRequested = Signal(int)
    tabMoveRequested = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.hovered_index = -1
        self._buttons = []
        self._current_index = -1
        self._tabs_closable = False
        self._movable = False
        self.setObjectName("wrapped_tab_bar")
        self._refresh_pending = False

        self._layout = FlowLayout(self, margin=0, spacing=1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)

    def hasHeightForWidth(self):
        return self.layout().hasHeightForWidth()

    def heightForWidth(self, width):
        return self.layout().heightForWidth(width)

    def minimumSizeHint(self):
        return self.layout().minimumSize()

    def sizeHint(self):
        hint = self.layout().sizeHint()
        width = max(hint.width(), 160)
        height = self.heightForWidth(max(self.width(), width))
        hint.setHeight(max(height, 28))
        hint.setWidth(width)
        return hint

    def changeEvent(self, event):
        if event.type() in (QEvent.PaletteChange, QEvent.ApplicationPaletteChange):
            self._schedule_style_refresh()
        super().changeEvent(event)

    def _schedule_style_refresh(self):
        if self._refresh_pending:
            return
        self._refresh_pending = True
        QTimer.singleShot(0, self._apply_scheduled_refresh)

    def _apply_scheduled_refresh(self):
        self._refresh_pending = False
        for button in self._buttons:
            button._refresh_style()
        self.update()

    def paintEvent(self, event):
        app = QApplication.instance()
        palette = app.palette() if app is not None else self.style().standardPalette()
        panel = palette.color(QPalette.ColorRole.Window)
        border = palette.color(QPalette.ColorRole.Mid)
        groove = _mix_colors(panel, border, 0.2)

        painter = QPainter(self)
        painter.fillRect(self.rect(), panel)
        painter.setPen(QPen(groove))
        painter.drawLine(self.rect().bottomLeft(), self.rect().bottomRight())
        super().paintEvent(event)

    def setMovable(self, movable):
        self._movable = movable

    def addTab(self, text):
        return self.insertTab(len(self._buttons), text)

    def insertTab(self, index, text):
        button = WrappedTabButton(text)
        button.clicked.connect(lambda b=button: self._on_tab_clicked(b))
        button.close_requested.connect(lambda b=button: self._on_close_requested(b))
        button.hovered.connect(lambda entered, b=button: self._on_hovered(b, entered))
        button.drag_requested.connect(lambda point, b=button: self._on_drag_requested(b, point))
        button.context_requested.connect(lambda point, b=button: self._show_context_menu(b, point))

        index = max(0, min(index, len(self._buttons)))
        self._buttons.insert(index, button)
        self._rebuild_layout()
        self._apply_closable_state(index)
        if self._current_index < 0:
            self.setCurrentIndex(0)
        elif index <= self._current_index:
            self._current_index += 1
            self._sync_selection()
        return index

    def removeTab(self, index):
        if not (0 <= index < len(self._buttons)):
            return

        button = self._buttons.pop(index)
        self._layout.removeWidget(button)
        button.deleteLater()

        if not self._buttons:
            self._current_index = -1
        elif index == self._current_index:
            self._current_index = min(index, len(self._buttons) - 1)
        elif index < self._current_index:
            self._current_index -= 1

        if self.hovered_index == index:
            self.hovered_index = -1
        elif index < self.hovered_index:
            self.hovered_index -= 1

        self._sync_selection()
        self.updateGeometry()

    def moveTab(self, from_index, to_index):
        if not (0 <= from_index < len(self._buttons) and 0 <= to_index < len(self._buttons)):
            return
        if from_index == to_index:
            return

        button = self._buttons.pop(from_index)
        self._buttons.insert(to_index, button)

        if self._current_index == from_index:
            self._current_index = to_index
        elif from_index < self._current_index <= to_index:
            self._current_index -= 1
        elif to_index <= self._current_index < from_index:
            self._current_index += 1

        self._rebuild_layout()
        self._sync_selection()

    def count(self):
        return len(self._buttons)

    def tabText(self, index):
        return self._buttons[index].text()

    def setTabText(self, index, text):
        self._buttons[index].set_text(text)
        self.updateGeometry()

    def setTabClosable(self, index, closable):
        self._buttons[index].set_closable(closable)
        self.updateGeometry()

    def setTabsClosable(self, closable):
        self._tabs_closable = closable
        for index in range(len(self._buttons)):
            self._apply_closable_state(index)
        self.updateGeometry()

    def currentIndex(self):
        return self._current_index

    def setCurrentIndex(self, index):
        if not (0 <= index < len(self._buttons)):
            return
        if index == self._current_index:
            self._sync_selection()
            return
        self._current_index = index
        self._sync_selection()
        self.currentChanged.emit(index)

    def tabAt(self, pos):
        for index, button in enumerate(self._buttons):
            if button.geometry().contains(pos):
                return index
        return -1

    def _sync_selection(self):
        for index, button in enumerate(self._buttons):
            button.set_current(index == self._current_index)
        self.updateGeometry()

    def _rebuild_layout(self):
        while self._layout.count():
            self._layout.takeAt(0)
        for button in self._buttons:
            self._layout.addWidget(button)
        self.updateGeometry()

    def _apply_closable_state(self, index):
        closable = self._tabs_closable and self._buttons[index].text() != "+"
        self._buttons[index].set_closable(closable)

    def _on_tab_clicked(self, button):
        index = self._buttons.index(button)
        self.setCurrentIndex(index)

    def _on_close_requested(self, button):
        index = self._buttons.index(button)
        self.tabCloseRequested.emit(index)

    def _on_hovered(self, button, entered):
        if entered:
            self.hovered_index = self._buttons.index(button)
        elif self.hovered_index == self._buttons.index(button):
            self.hovered_index = -1

    def _on_drag_requested(self, button, global_pos):
        if not self._movable:
            return

        from_index = self._buttons.index(button)
        if self.tabText(from_index) == "+":
            return

        local_pos = self.mapFromGlobal(global_pos)
        to_index = self.tabAt(local_pos)
        if to_index < 0 or to_index == from_index or self.tabText(to_index) == "+":
            return

        self.tabMoveRequested.emit(from_index, to_index)

    def _show_context_menu(self, button, global_pos):
        index = self._buttons.index(button)
        menu = QMenu(self)
        window = self.window()

        if self.tabText(index) == "+":
            restore = menu.addAction("閉じたタブを復元")
            action = menu.exec(global_pos)
            if action == restore:
                window.restore_closed_tab()
            return

        help_action = None
        tab_widget = window.tabs.widget(index) if hasattr(window, "tabs") else None
        if tab_widget is not None and tab_widget.__class__.has_help():
            help_action = menu.addAction(f"{tab_widget.__class__.TOOL_DEFAULT_LABEL} Help")
        rename = menu.addAction("Rename")
        close = menu.addAction("Close")
        action = menu.exec(global_pos)

        if action == help_action:
            window.open_help_for_tab(index)
        if action == rename:
            window.rename_tab(index)
        if action == close:
            window.close_tab(index)


class WrappedTabWidget(QWidget):

    tabCloseRequested = Signal(int)

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tab_bar = FixedTabBar()
        self._stack = QStackedWidget()

        layout.addWidget(self._tab_bar)
        layout.addWidget(self._stack, 1)

        self._tab_bar.currentChanged.connect(self._stack.setCurrentIndex)
        self._tab_bar.tabCloseRequested.connect(self.tabCloseRequested.emit)
        self._tab_bar.tabMoveRequested.connect(self._move_tab)

    def tabBar(self):
        return self._tab_bar

    def setTabsClosable(self, closable):
        self._tab_bar.setTabsClosable(closable)

    def addTab(self, widget, label):
        index = self._stack.addWidget(widget)
        self._tab_bar.addTab(label)
        return index

    def insertTab(self, index, widget, label):
        index = self._stack.insertWidget(index, widget)
        self._tab_bar.insertTab(index, label)
        return index

    def removeTab(self, index):
        widget = self._stack.widget(index)
        self._stack.removeWidget(widget)
        self._tab_bar.removeTab(index)
        if widget is not None:
            widget.setParent(None)

    def count(self):
        return self._stack.count()

    def tabText(self, index):
        return self._tab_bar.tabText(index)

    def setTabText(self, index, text):
        self._tab_bar.setTabText(index, text)

    def indexOf(self, widget):
        return self._stack.indexOf(widget)

    def widget(self, index):
        return self._stack.widget(index)

    def setCurrentIndex(self, index):
        self._tab_bar.setCurrentIndex(index)
        self._stack.setCurrentIndex(index)

    def currentIndex(self):
        return self._stack.currentIndex()

    def _move_tab(self, from_index, to_index):
        widget = self._stack.widget(from_index)
        current_index = self._stack.currentIndex()

        self._stack.removeWidget(widget)
        self._stack.insertWidget(to_index, widget)
        self._tab_bar.moveTab(from_index, to_index)

        if current_index == from_index:
            self.setCurrentIndex(to_index)
        elif from_index < current_index <= to_index:
            self.setCurrentIndex(current_index - 1)
        elif to_index <= current_index < from_index:
            self.setCurrentIndex(current_index + 1)
