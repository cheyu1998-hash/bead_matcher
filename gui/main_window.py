"""Bead Matcher - PyQt6 桌面客户端入口"""

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from gui.styles import MAIN_STYLE
from gui.tabs.convert_tab import ConvertTab
from gui.tabs.history_tab import HistoryTab
from gui.tabs.inventory_tab import InventoryTab
from gui.tabs.match_tab import MatchTab
from gui.tabs.pattern_tab import PatternTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bead Matcher - 拼豆库存管理")
        self.setMinimumSize(1100, 720)
        self.resize(1200, 800)

        # 中心部件
        central = QWidget()
        self.setCentralWidget(central)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        tab_widget = QTabWidget()
        tab_widget.setDocumentMode(True)
        tab_widget.setTabPosition(QTabWidget.TabPosition.North)

        # 添加五个 Tab
        self.tab_inventory = InventoryTab()
        self.tab_pattern = PatternTab()
        self.tab_match = MatchTab()
        self.tab_convert = ConvertTab()
        self.tab_history = HistoryTab()

        tab_widget.addTab(self.tab_inventory, "库存管理")
        tab_widget.addTab(self.tab_pattern, "图案库")
        tab_widget.addTab(self.tab_match, "匹配分析")
        tab_widget.addTab(self.tab_convert, "图片转换")
        tab_widget.addTab(self.tab_history, "历史记录")

        central_layout.addWidget(tab_widget)

        # 应用全局样式
        self.setStyleSheet(MAIN_STYLE)


def main():
    # Windows 高清屏适配
    if sys.platform == "win32":
        from ctypes import windll

        try:
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))

    # 深色标题栏（Windows 11/10 效果）
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
