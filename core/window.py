from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QWidget,
    QTabBar,
    QInputDialog,
    QMessageBox,
    QMenu,
    QVBoxLayout,
)
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtCore import QSettings
import win32gui
import win32con
from core.plus_tab import PlusTab
from core.tool_loader import load_tools
from core.paths import TABS_DIR
from core.tab_storage import create_tab_folder
import json
import shutil

class MainWindow(QMainWindow):
    


    def __init__(self):
        super().__init__()
        
        self.always_on_top = False
        QShortcut(QKeySequence("Alt+W"), self, self.toggle_always_on_top)
        QShortcut(QKeySequence("F2"), self, self.rename_current_hover_tab)

        self.tools = load_tools()

        self.settings = QSettings("toolbox", "toolbox")

        self.setWindowTitle("Toolbox")

        self.tabs = QTabWidget()
        self.tabs.setTabBar(FixedTabBar())
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

        self.tabs.tabBar().setTabButton(
            index,
            QTabBar.ButtonPosition.RightSide,
            None
        )

    def close_tab(self, index):

        if self.tabs.tabText(index) == "+":
            return

        tab_name = self.tabs.tabText(index)
        tab_folder = TABS_DIR / tab_name

        if tab_folder.exists() and tab_folder.is_dir():
            shutil.rmtree(tab_folder)

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
            meta_file = folder / "tool.json"

            if not meta_file.exists():
                continue

            data = json.loads(meta_file.read_text())

            data["order"] = i

            meta_file.write_text(json.dumps(data, indent=2))
        
    def open_tool(self, tool_class, replace_widget=None):

        tab_name, folder = create_tab_folder(tool_class)

        widget = tool_class(folder)

        if replace_widget:
            index = self.tabs.indexOf(replace_widget)

            self.tabs.removeTab(index)
            self.tabs.insertTab(index, widget, tab_name)
            self.tabs.setCurrentIndex(index)

        else:
            plus_index = self.tabs.count() - 1

            self.tabs.insertTab(plus_index, widget, tab_name)
            self.tabs.setCurrentIndex(plus_index)
            
    def restore_tabs(self):

        tabs = []

        for folder in TABS_DIR.iterdir():

            meta_file = folder / "tool.json"

            if not meta_file.exists():
                continue

            data = json.loads(meta_file.read_text())

            tabs.append((data.get("order", 0), folder, data))

        tabs.sort(key=lambda x: x[0])

        for _, folder, data in tabs:

            tool_name = data.get("tool")
            tool_class = self.tools.get(tool_name)

            if not tool_class:
                continue

            widget = tool_class(folder)

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

        # 見た目更新（今までのやつそのまま使える）
        if self.always_on_top:
            self.wrapper.setStyleSheet("""
                #window_frame {
                    border-top: 3px solid #4ecdc4;
                }
            """)
        else:
            self.wrapper.setStyleSheet("")
                
class FixedTabBar(QTabBar):
    
    def __init__(self):
        super().__init__()
        self.hovered_index = -1
        self.setMouseTracking(True)

    def mouseMoveEvent(self, event):
        self.hovered_index = self.tabAt(event.pos())
        super().mouseMoveEvent(event)
        
    def mousePressEvent(self, event):

        index = self.tabAt(event.pos())

        if index >= 0 and self.tabText(index) == "+":
            QTabBar.mousePressEvent(self, event)
            return

        super().mousePressEvent(event)
        
    def contextMenuEvent(self, event):

        index = self.tabAt(event.pos())

        if index < 0:
            return

        if self.tabText(index) == "+":
            return

        menu = QMenu(self)

        rename = menu.addAction("Rename")
        close = menu.addAction("Close")

        action = menu.exec(event.globalPos())

        if action == rename:
            self.window().rename_tab(index)

        if action == close:
            self.window().close_tab(index)
            
