from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QWidget,
    QTabBar
)

from PySide6.QtCore import QSettings
from core.new_tab import NewTab
from core.tool_loader import load_tools
from core.paths import TABS_DIR
from core.tab_storage import create_tab_folder
import json

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        
        self.tools = load_tools()

        self.settings = QSettings("toolbox", "toolbox")

        self.setWindowTitle("Toolbox")

        self.tabs = QTabWidget()
        self.tabs.setTabBar(FixedTabBar())
        self.tabs.tabBar().setMovable(True)
        self.tabs.setTabsClosable(True)
        
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.tabBarClicked.connect(self.handle_tab_click)

        self.setCentralWidget(self.tabs)

        self.add_plus_tab()
        
        # 前回のサイズを復元
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(400, 800)
        
        self.restore_tabs()

    def add_plus_tab(self):

        plus_tab = QWidget()

        index = self.tabs.addTab(plus_tab, "+")

        self.tabs.tabBar().setTabButton(
            index,
            QTabBar.ButtonPosition.RightSide,
            None
        )


    def handle_tab_click(self, index):

        if self.tabs.tabText(index) != "+":
            return

        self.open_new_tab()

    def open_new_tab(self):

        plus_index = self.tabs.count() - 1

        widget = NewTab(self)

        self.tabs.insertTab(plus_index, widget, "New")
        self.tabs.setCurrentIndex(plus_index)

    def close_tab(self, index):

        if self.tabs.tabText(index) == "+":
            return

        self.tabs.removeTab(index)
        
    def closeEvent(self, event):

        self.settings.setValue("geometry", self.saveGeometry())

        super().closeEvent(event)
        
    def open_tool(self, tool_class, replace_widget=None):

        tab_name, folder = create_tab_folder(tool_class)

        widget = tool_class(folder)   # ← folder渡す

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

        for folder in TABS_DIR.iterdir():

            meta_file = folder / "tool.json"

            if not meta_file.exists():
                continue

            data = json.loads(meta_file.read_text())

            tool_name = data.get("tool")

            tool_class = self.tools.get(tool_name)

            if not tool_class:
                continue

            widget = tool_class(folder)

            plus_index = self.tabs.count() - 1

            self.tabs.insertTab(plus_index, widget, folder.name)
                
class FixedTabBar(QTabBar):

    def mousePressEvent(self, event):

        index = self.tabAt(event.pos())

        if index >= 0 and self.tabText(index) == "+":
            QTabBar.mousePressEvent(self, event)
            return

        super().mousePressEvent(event)