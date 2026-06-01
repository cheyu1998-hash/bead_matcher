"""匹配分析 Tab"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bead_matcher.inventory_service import make_pattern
from bead_matcher.pattern_storage import PatternLibrary
from bead_matcher.storage import load_inventory


class MatchTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        title = QLabel("匹配分析")
        title.setObjectName("title")
        layout.addWidget(title)

        # 选择图案
        selector = QHBoxLayout()
        selector.addWidget(QLabel("选择图案:"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(200)
        self._load_patterns()
        selector.addWidget(self.combo)

        btn_check = QPushButton("分析库存")
        btn_check.setObjectName("primary")
        btn_check.clicked.connect(self._analyze)
        selector.addWidget(btn_check)

        btn_auto = QPushButton("自动匹配全部")
        btn_auto.setObjectName("secondary")
        btn_auto.clicked.connect(self._auto_match)
        selector.addWidget(btn_auto)
        selector.addStretch()
        layout.addLayout(selector)

        # 结果区
        result_row = QHBoxLayout()
        self.result_label = QLabel("请选择图案后点击分析")
        self.result_label.setObjectName("subtitle")
        result_row.addWidget(self.result_label)
        result_row.addStretch()

        self.btn_make = QPushButton("🛠️ 制作")
        self.btn_make.setObjectName("primary")
        self.btn_make.setVisible(False)
        self.btn_make.clicked.connect(self._make)
        result_row.addWidget(self.btn_make)
        layout.addLayout(result_row)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["色号", "需要", "库存", "缺口"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=1)

    def _load_patterns(self):
        lib = PatternLibrary()
        self.combo.clear()
        for p in lib.list_all():
            display = f"{p.name} ({p.width}×{p.height})"
            self.combo.addItem(display, p.id)

    def _analyze(self):
        inv = load_inventory()
        if not inv:
            self.result_label.setText("请先初始化库存")
            return

        pattern_id = self.combo.currentData()
        if not pattern_id:
            return

        lib = PatternLibrary()
        p = lib.get_by_id(pattern_id)
        if not p:
            return

        shortage = p.estimate_inventory_shortage(
            {code: inv.get_quantity(code) for code in inv.list_codes()}
        )
        can_make = p.can_make_with_inventory(
            {code: inv.get_quantity(code) for code in inv.list_codes()}
        )

        if can_make:
            self.result_label.setText(f"✅ 库存足够制作「{p.name}」")
            self.btn_make.setVisible(True)
            self._current_pattern_id = pattern_id
        else:
            missing = sum(shortage.values())
            self.result_label.setText(f"⚠️ 「{p.name}」缺 {missing} 粒，详见下表")
            self.btn_make.setVisible(False)
            self._current_pattern_id = None

        # 显示全部色号对比
        self.table.setHorizontalHeaderLabels(["色号", "需要", "库存", "缺口"])
        all_codes = sorted(p.color_usage.keys())
        self.table.setRowCount(len(all_codes))
        for i, code in enumerate(all_codes):
            need = p.color_usage[code]
            have = inv.get_quantity(code)
            miss = shortage.get(code, 0)
            self.table.setItem(i, 0, QTableWidgetItem(code))
            self.table.setItem(i, 1, QTableWidgetItem(str(need)))
            self.table.setItem(i, 2, QTableWidgetItem(str(have)))
            self.table.setItem(i, 3, QTableWidgetItem(str(miss) if miss else "OK"))
        self.table.resizeColumnsToContents()

    def _make(self):
        pattern_id = getattr(self, "_current_pattern_id", None)
        if not pattern_id:
            return

        lib = PatternLibrary()
        p = lib.get_by_id(pattern_id)
        if not p:
            return

        reply = QMessageBox.question(
            self,
            "确认制作",
            f"确定要制作「{p.name}」吗？\n将消耗 {p.total_beads()} 粒拼豆。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        result = make_pattern(p)
        if result["ok"]:
            QMessageBox.information(
                self,
                "制作成功",
                f"✅ 已制作「{p.name}」\n消耗: {', '.join(f'{c}×{q}' for c, q in result['consumed'].items())}",
            )
            self.btn_make.setVisible(False)
            self._current_pattern_id = None
            # 触发库存刷新信号（后续可扩展）
        else:
            QMessageBox.warning(self, "制作失败", result["error"])

    def _auto_match(self):
        inv = load_inventory()
        if not inv:
            self.result_label.setText("请先初始化库存")
            return

        lib = PatternLibrary()
        inventory_qty = {code: inv.get_quantity(code) for code in inv.list_codes()}
        matches = lib.find_matching_patterns(inventory_qty)

        self.btn_make.setVisible(False)
        self._current_pattern_id = None

        if not matches:
            self.result_label.setText("当前库存无法完全覆盖任何图案")
            self.table.setRowCount(0)
            return

        self.result_label.setText(f"✅ 当前库存能制作 {len(matches)} 个图案")
        self.table.setHorizontalHeaderLabels(["图案名称", "总粒数", "色号数", "状态"])
        self.table.setRowCount(len(matches))
        for i, p in enumerate(matches):
            item_name = QTableWidgetItem(p.name)
            item_name.setData(Qt.ItemDataRole.UserRole, p.id)
            self.table.setItem(i, 0, item_name)
            self.table.setItem(i, 1, QTableWidgetItem(f"{p.total_beads()} 粒"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{len(p.color_usage)} 色"))
            self.table.setItem(i, 3, QTableWidgetItem("可制作"))
        self.table.resizeColumnsToContents()
