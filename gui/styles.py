"""PyQt6 现代风格 QSS"""

MAIN_STYLE = """
/* ---------- 全局 ---------- */
QWidget {
    font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
    font-size: 14px;
    color: #333333;
}

/* ---------- 主窗口 ---------- */
QMainWindow {
    background: #f5f7fa;
}

/* ---------- TabWidget ---------- */
QTabWidget::pane {
    border: none;
    background: #f5f7fa;
    top: -1px;
}

QTabBar::tab {
    background: transparent;
    color: #888888;
    padding: 14px 32px;
    border: none;
    border-bottom: 3px solid transparent;
    font-weight: 500;
    font-size: 14px;
    min-width: 100px;
}

QTabBar::tab:hover {
    color: #555555;
    background: rgba(79, 140, 255, 0.06);
}

QTabBar::tab:selected {
    color: #4f8cff;
    border-bottom: 3px solid #4f8cff;
    background: transparent;
}

QTabBar::tab:!selected {
    margin-top: 2px;
}

/* ---------- 按钮 ---------- */
QPushButton {
    padding: 10px 24px;
    border-radius: 8px;
    border: none;
    font-weight: 500;
    font-size: 13px;
    min-height: 36px;
}

QPushButton#primary {
    background: #4f8cff;
    color: white;
}

QPushButton#primary:hover {
    background: #3a78f0;
}

QPushButton#primary:pressed {
    background: #2a68e0;
}

QPushButton#danger {
    background: #ff4d4f;
    color: white;
}

QPushButton#danger:hover {
    background: #e04345;
}

QPushButton#secondary {
    background: #e8eaf0;
    color: #555555;
}

QPushButton#secondary:hover {
    background: #dde0e8;
}

/* ---------- 输入框 ---------- */
QLineEdit, QSpinBox, QComboBox {
    padding: 10px 14px;
    border: 1px solid #d9d9d9;
    border-radius: 8px;
    background: white;
    font-size: 13px;
    min-height: 40px;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #4f8cff;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox QAbstractItemView {
    border: 1px solid #d9d9d9;
    border-radius: 8px;
    background: white;
    selection-background-color: #4f8cff;
    padding: 4px;
}

/* ---------- 表格 ---------- */
QTableWidget {
    border: 1px solid #e8e8e8;
    border-radius: 10px;
    background: white;
    gridline-color: #f0f0f0;
    outline: none;
}

QTableWidget::item {
    padding: 12px 14px;
    border-bottom: 1px solid #f5f5f5;
}

QTableWidget::item:selected {
    background: #e8f0fe;
    color: #333;
}

QHeaderView::section {
    background: #fafbfc;
    color: #666;
    padding: 12px 14px;
    border: none;
    border-bottom: 2px solid #e8e8e8;
    font-weight: 600;
    font-size: 12px;
}

QHeaderView::section:horizontal {
    border-right: 1px solid #f0f0f0;
}

/* ---------- 分组框 ---------- */
QGroupBox {
    font-weight: 600;
    color: #444;
    border: 1px solid #e8e8e8;
    border-radius: 12px;
    margin-top: 16px;
    background: white;
    padding: 20px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 4px 10px;
    color: #555;
    background: white;
    border-radius: 4px;
}

/* ---------- 标签 ---------- */
QLabel#title {
    font-size: 22px;
    font-weight: 700;
    color: #1a1d23;
    padding-bottom: 8px;
}

QLabel#subtitle {
    font-size: 13px;
    color: #888;
}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    border-radius: 3px;
}

QScrollBar::handle:vertical {
    background: #c0c4cc;
    border-radius: 3px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #a0a4ac;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* ---------- 消息框 ---------- */
QLabel#success_msg {
    color: #2e7d32;
    background: #e6f7e6;
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 13px;
}

QLabel#error_msg {
    color: #c62828;
    background: #ffebee;
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 13px;
}
"""
