from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QWidget,
    QInputDialog,
    QTabBar
)

from tabs.memo.tool import MemoTab
from tabs.clamp.tool import ClampTab
from PySide6.QtCore import QSettings
from core.new_tab import NewTab

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.settings = QSettings("toolbox", "toolbox")

        self.setWindowTitle("Toolbox")

        self.tabs = QTabWidget()
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

    def replace_tab(self, old_widget, tool_name):

        index = self.tabs.indexOf(old_widget)

        if tool_name == "Memo":
            widget = MemoTab()

        elif tool_name == "Clamp":
            widget = ClampTab()

        self.tabs.removeTab(index)
        self.tabs.insertTab(index, widget, tool_name)
        self.tabs.setCurrentIndex(index)

    def close_tab(self, index):

        if self.tabs.tabText(index) == "+":
            return

        self.tabs.removeTab(index)
        
    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)