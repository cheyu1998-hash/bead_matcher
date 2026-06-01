"""历史记录 Tab：展示制作历史和库存事务流水。"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bead_matcher.dao.inventory_dao import InventoryDao
from bead_matcher.dao.make_record_dao import MakeRecordDao
from bead_matcher.pattern_storage import PatternLibrary


class HistoryTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        title = QLabel("历史记录")
        title.setObjectName("title")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        toolbar.addStretch()
        btn_refresh = QPushButton("刷新")
        btn_refresh.setObjectName("secondary")
        btn_refresh.clicked.connect(self._refresh)
        toolbar.addWidget(btn_refresh)
        layout.addLayout(toolbar)

        # 制作历史
        make_group = QGroupBox("制作历史")
        make_layout = QVBoxLayout(make_group)
        self.make_table = QTableWidget()
        self.make_table.setColumnCount(5)
        self.make_table.setHorizontalHeaderLabels(["时间", "图案", "消耗", "状态", "备注"])
        self.make_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.make_table.verticalHeader().setVisible(False)
        self.make_table.horizontalHeader().setStretchLastSection(True)
        self.make_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.make_table.setAlternatingRowColors(True)
        make_layout.addWidget(self.make_table)
        layout.addWidget(make_group)

        # 事务流水
        tx_group = QGroupBox("库存事务流水")
        tx_layout = QVBoxLayout(tx_group)
        self.tx_table = QTableWidget()
        self.tx_table.setColumnCount(6)
        self.tx_table.setHorizontalHeaderLabels(["时间", "色号", "变动", "余额", "类型", "备注"])
        self.tx_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tx_table.verticalHeader().setVisible(False)
        self.tx_table.horizontalHeader().setStretchLastSection(True)
        self.tx_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tx_table.setAlternatingRowColors(True)
        tx_layout.addWidget(self.tx_table)
        layout.addWidget(tx_group)

    def _refresh(self):
        self._refresh_make_records()
        self._refresh_transactions()

    def _refresh_make_records(self):
        make_dao = MakeRecordDao()
        lib = PatternLibrary()
        records = make_dao.list_all(limit=100)

        self.make_table.setRowCount(len(records))
        for i, r in enumerate(records):
            pattern = lib.get_by_id(r["pattern_id"])
            pattern_name = pattern.name if pattern else "未知"
            consumed_str = ", ".join(f"{c}×{q}" for c, q in r["consumed"].items())

            self.make_table.setItem(i, 0, QTableWidgetItem(r["made_at"][:19].replace("T", " ")))
            self.make_table.setItem(i, 1, QTableWidgetItem(pattern_name))
            self.make_table.setItem(i, 2, QTableWidgetItem(consumed_str))
            self.make_table.setItem(i, 3, QTableWidgetItem(r["status"]))
            self.make_table.setItem(i, 4, QTableWidgetItem(r["note"] or ""))
        self.make_table.resizeColumnsToContents()

    def _refresh_transactions(self):
        inv_dao = InventoryDao()
        txs = inv_dao.list_transactions(limit=100)

        self.tx_table.setRowCount(len(txs))
        for i, t in enumerate(txs):
            delta_item = QTableWidgetItem(f"{t['delta']:+d}")
            if t["delta"] > 0:
                delta_item.setForeground(Qt.GlobalColor.darkGreen)
            elif t["delta"] < 0:
                delta_item.setForeground(Qt.GlobalColor.darkRed)

            self.tx_table.setItem(i, 0, QTableWidgetItem(t["tx_at"][:19].replace("T", " ")))
            self.tx_table.setItem(i, 1, QTableWidgetItem(t["code"]))
            self.tx_table.setItem(i, 2, delta_item)
            self.tx_table.setItem(i, 3, QTableWidgetItem(str(t["balance"])))
            self.tx_table.setItem(i, 4, QTableWidgetItem(t["tx_type"]))
            self.tx_table.setItem(i, 5, QTableWidgetItem(t["note"] or ""))
        self.tx_table.resizeColumnsToContents()
