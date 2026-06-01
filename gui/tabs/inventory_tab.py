"""库存管理 Tab — 支持初始化向导与补货向导"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bead_matcher.color_chart import get_chart
from bead_matcher.dao.inventory_dao import InventoryDao
from bead_matcher.inventory import Inventory
from bead_matcher.inventory_service import undo_last_operation
from bead_matcher.storage import load_inventory, save_inventory


class InventoryTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.chart = get_chart("Mard")
        self._init_state()
        self._setup_ui()
        self._refresh_normal()

    def _init_state(self):
        self.init_selected_prefixes = []
        self.init_current_prefix_index = 0
        self.init_quantities = {}
        self.restock_selected_codes = []
        self.restock_quantities = {}

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()

        self.page_normal = QWidget()
        self._build_normal_page()

        self.page_init_prefix = QWidget()
        self._build_init_prefix_page()

        self.page_init_series = QWidget()
        self._build_init_series_page()

        self.page_restock_select = QWidget()
        self._build_restock_select_page()

        self.page_restock_confirm = QWidget()
        self._build_restock_confirm_page()

        self.stack.addWidget(self.page_normal)          # 0
        self.stack.addWidget(self.page_init_prefix)     # 1
        self.stack.addWidget(self.page_init_series)     # 2
        self.stack.addWidget(self.page_restock_select)  # 3
        self.stack.addWidget(self.page_restock_confirm) # 4

        layout.addWidget(self.stack)

    # ---------- 通用工具方法 ----------

    def _make_stat_card(self, label: str, value: str) -> QWidget:
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background: white;
                border-radius: 12px;
            }
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(8)

        lbl = QLabel(label)
        lbl.setStyleSheet("font-size:13px;color:#888;background:transparent;")
        val = QLabel(value)
        val.setStyleSheet("font-size:28px;font-weight:700;color:#1a1d23;background:transparent;")

        lay.addWidget(lbl)
        lay.addWidget(val)
        card.value_label = val
        return card

    def _make_color_dot(self, hex_color: str, size: int = 20) -> QLabel:
        dot = QLabel()
        dot.setFixedSize(size, size)
        hex_color = hex_color or "#ccc"
        dot.setStyleSheet(
            f"background-color: {hex_color}; border-radius: {size//2}px; border: 1px solid #ccc;"
        )
        return dot

    def _switch_page(self, index: int):
        self.stack.setCurrentIndex(index)

    # ---------- 正常管理页 (Page 0) ----------

    def _build_normal_page(self):
        layout = QVBoxLayout(self.page_normal)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        title = QLabel("库存管理")
        title.setObjectName("title")
        layout.addWidget(title)

        # 统计栏
        stats = QHBoxLayout()
        stats.setSpacing(16)
        self.stat_brand_val = self._make_stat_card("品牌", "-")
        self.stat_colors_val = self._make_stat_card("总色号", "0")
        self.stat_total_val = self._make_stat_card("总粒数", "0")
        stats.addWidget(self.stat_brand_val)
        stats.addWidget(self.stat_colors_val)
        stats.addWidget(self.stat_total_val)
        stats.addStretch()
        layout.addLayout(stats)

        # 操作区
        op_group = QGroupBox("操作")
        op_layout = QHBoxLayout(op_group)
        op_layout.setSpacing(16)
        op_layout.setContentsMargins(20, 24, 20, 20)

        self.input_code = QLineEdit()
        self.input_code.setPlaceholderText("色号，如 A01")
        self.input_code.setFixedWidth(140)

        self.input_qty = QSpinBox()
        self.input_qty.setRange(0, 999999)
        self.input_qty.setValue(100)
        self.input_qty.setFixedWidth(120)

        btn_add = QPushButton("添加")
        btn_add.setObjectName("primary")
        btn_add.clicked.connect(self._add_stock)

        btn_set = QPushButton("设置")
        btn_set.setObjectName("secondary")
        btn_set.clicked.connect(self._set_stock)

        btn_remove = QPushButton("消耗")
        btn_remove.setObjectName("danger")
        btn_remove.clicked.connect(self._remove_stock)

        btn_undo = QPushButton("撤销上次")
        btn_undo.setObjectName("secondary")
        btn_undo.clicked.connect(self._undo)

        # 新增按钮
        btn_init = QPushButton("初始化库存")
        btn_init.setObjectName("danger")
        btn_init.clicked.connect(self._start_init)

        btn_restock = QPushButton("补货录入")
        btn_restock.setObjectName("primary")
        btn_restock.clicked.connect(self._start_restock)

        btn_clear = QPushButton("清空库存")
        btn_clear.setObjectName("danger")
        btn_clear.clicked.connect(self._clear_stock)

        op_layout.addWidget(QLabel("色号:"))
        op_layout.addWidget(self.input_code)
        op_layout.addWidget(QLabel("数量:"))
        op_layout.addWidget(self.input_qty)
        op_layout.addWidget(btn_add)
        op_layout.addWidget(btn_set)
        op_layout.addWidget(btn_remove)
        op_layout.addWidget(btn_undo)
        op_layout.addStretch()
        op_layout.addWidget(btn_init)
        op_layout.addWidget(btn_restock)
        op_layout.addWidget(btn_clear)

        layout.addWidget(op_group)

        # 库存表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["色号", "名称", "HEX", "数量"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=1)

    def _refresh_normal(self):
        inv = load_inventory()
        if not inv:
            self.stat_brand_val.value_label.setText("未初始化")
            self.stat_colors_val.value_label.setText("0")
            self.stat_total_val.value_label.setText("0")
            self.table.setRowCount(0)
            return

        chart = get_chart(inv.brand)
        self.stat_brand_val.value_label.setText(inv.brand)
        self.stat_colors_val.value_label.setText(str(len(inv.items)))
        self.stat_total_val.value_label.setText(str(inv.total_count()))

        self.table.setRowCount(len(inv.items))
        for i, code in enumerate(inv.list_codes()):
            color = chart.get(code) if chart else None
            self.table.setItem(i, 0, QTableWidgetItem(code))
            self.table.setItem(i, 1, QTableWidgetItem(color.name if color else "未知"))
            self.table.setItem(i, 2, QTableWidgetItem(color.hex_color if color else "-"))
            qty_item = QTableWidgetItem(str(inv.get_quantity(code)))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(i, 3, qty_item)

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def _add_stock(self):
        self._do_op("add")

    def _set_stock(self):
        self._do_op("set")

    def _remove_stock(self):
        self._do_op("remove")

    def _do_op(self, op: str):
        inv = load_inventory()
        if not inv:
            QMessageBox.warning(self, "未初始化", "尚未初始化库存，请先初始化")
            return
        code = self.input_code.text().strip()
        qty = self.input_qty.value()
        if not code:
            return
        try:
            if op == "add":
                inv.add(code, qty)
            elif op == "set":
                inv.set(code, qty)
            elif op == "remove":
                inv.remove(code, qty)
            save_inventory(inv)

            dao = InventoryDao()
            new_balance = inv.get_quantity(code)
            if op == "add":
                dao.add_transaction(code, qty, new_balance, "add", note="GUI 添加")
            elif op == "remove":
                dao.add_transaction(code, -qty, new_balance, "remove", note="GUI 消耗")
            elif op == "set":
                dao.add_transaction(code, new_balance, new_balance, "set", note="GUI 设置")

            self._refresh_normal()
        except Exception as e:
            QMessageBox.warning(self, "操作失败", str(e))

    def _undo(self):
        result = undo_last_operation()
        if result["ok"]:
            QMessageBox.information(
                self, "撤销成功", f"已撤销对 {', '.join(result['undone'])} 的操作"
            )
            self._refresh_normal()
        else:
            QMessageBox.warning(self, "撤销失败", result["error"])

    def _clear_stock(self):
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有库存吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        inv = load_inventory()
        if inv:
            inv.items.clear()
            save_inventory(inv)
            self._refresh_normal()

    # ---------- 初始化流程 ----------

    def _start_init(self):
        reply = QMessageBox.warning(
            self,
            "初始化库存",
            "初始化将清空现有库存数据，且不可恢复。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._init_state()
        self._refresh_init_prefix()
        self._switch_page(1)

    def _build_init_prefix_page(self):
        layout = QVBoxLayout(self.page_init_prefix)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        title = QLabel("初始化库存 — 选择系列")
        title.setObjectName("title")
        layout.addWidget(title)

        desc = QLabel("请勾选本次需要录入的色系系列，未勾选的系列将不会入库。")
        desc.setStyleSheet("font-size:14px;color:#666;")
        layout.addWidget(desc)

        # 系列卡片区域
        scroll = QWidget()
        grid_layout = QHBoxLayout(scroll)
        grid_layout.setSpacing(12)
        self.prefix_checkboxes = {}
        for prefix in self.chart.list_prefixes():
            cb = QCheckBox(
                f"{prefix}  {self.chart.get_prefix_name(prefix)}  ({len(self.chart.get_by_prefix(prefix))}色)"
            )
            self.prefix_checkboxes[prefix] = cb
            grid_layout.addWidget(cb)
        grid_layout.addStretch()
        layout.addWidget(scroll)

        # 全选/取消全选
        select_all_layout = QHBoxLayout()
        btn_all = QPushButton("全选")
        btn_all.clicked.connect(self._select_all_prefixes)
        btn_none = QPushButton("取消全选")
        btn_none.clicked.connect(self._select_none_prefixes)
        select_all_layout.addWidget(btn_all)
        select_all_layout.addWidget(btn_none)
        select_all_layout.addStretch()
        layout.addLayout(select_all_layout)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(lambda: self._switch_page(0))
        btn_next = QPushButton("开始录入")
        btn_next.setObjectName("primary")
        btn_next.clicked.connect(self._on_prefix_selected)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_next)
        layout.addLayout(btn_layout)
        layout.addStretch()

    def _select_all_prefixes(self):
        for cb in self.prefix_checkboxes.values():
            cb.setChecked(True)

    def _select_none_prefixes(self):
        for cb in self.prefix_checkboxes.values():
            cb.setChecked(False)

    def _refresh_init_prefix(self):
        for cb in self.prefix_checkboxes.values():
            cb.setChecked(False)

    def _on_prefix_selected(self):
        selected = [p for p, cb in self.prefix_checkboxes.items() if cb.isChecked()]
        if not selected:
            QMessageBox.information(self, "提示", "请至少选择一个系列")
            return
        self.init_selected_prefixes = selected
        self.init_current_prefix_index = 0
        self.init_quantities = {}
        self._load_init_series_page()
        self._switch_page(2)

    def _build_init_series_page(self):
        layout = QVBoxLayout(self.page_init_series)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        self.series_title = QLabel()
        self.series_title.setObjectName("title")
        layout.addWidget(self.series_title)

        # 批量操作栏
        batch_layout = QHBoxLayout()
        batch_layout.addWidget(QLabel("批量设置："))
        self.batch_combo = QComboBox()
        self.batch_combo.addItems(["100", "200", "500", "1000", "2000", "5000", "10000"])
        self.batch_combo.setCurrentText("1000")
        self.batch_combo.setFixedWidth(100)
        batch_layout.addWidget(self.batch_combo)
        btn_apply = QPushButton("应用到全部")
        btn_apply.clicked.connect(self._apply_batch_qty)
        batch_layout.addWidget(btn_apply)
        batch_layout.addStretch()
        layout.addLayout(batch_layout)

        # 色号表格
        self.init_series_table = QTableWidget()
        self.init_series_table.setColumnCount(5)
        self.init_series_table.setHorizontalHeaderLabels(["色块", "色号", "名称", "HEX", "数量"])
        self.init_series_table.verticalHeader().setVisible(False)
        self.init_series_table.horizontalHeader().setStretchLastSection(True)
        self.init_series_table.setAlternatingRowColors(True)
        layout.addWidget(self.init_series_table, stretch=1)

        # 导航按钮
        nav = QHBoxLayout()
        self.btn_series_prev = QPushButton("上一步")
        self.btn_series_prev.clicked.connect(self._series_prev)
        self.btn_series_skip = QPushButton("跳过此系列")
        self.btn_series_skip.clicked.connect(self._series_skip)
        self.btn_series_next = QPushButton("下一步")
        self.btn_series_next.setObjectName("primary")
        self.btn_series_next.clicked.connect(self._series_next)
        self.btn_series_done = QPushButton("完成入库")
        self.btn_series_done.setObjectName("primary")
        self.btn_series_done.clicked.connect(self._series_done)
        nav.addWidget(self.btn_series_prev)
        nav.addWidget(self.btn_series_skip)
        nav.addStretch()
        nav.addWidget(self.btn_series_next)
        nav.addWidget(self.btn_series_done)
        layout.addLayout(nav)

    def _load_init_series_page(self):
        prefix = self.init_selected_prefixes[self.init_current_prefix_index]
        colors = self.chart.get_by_prefix(prefix)
        name = self.chart.get_prefix_name(prefix)

        self.series_title.setText(
            f"系列 {prefix} — {name} ({len(colors)}色)  "
            f"({self.init_current_prefix_index + 1}/{len(self.init_selected_prefixes)})"
        )

        self.init_series_table.setRowCount(len(colors))
        self._series_spinboxes = []
        for i, c in enumerate(colors):
            self.init_series_table.setCellWidget(i, 0, self._make_color_dot(c.hex_color))
            self.init_series_table.setItem(i, 1, QTableWidgetItem(c.code))
            self.init_series_table.setItem(i, 2, QTableWidgetItem(c.name))
            self.init_series_table.setItem(i, 3, QTableWidgetItem(c.hex_color or "-"))

            spin = QSpinBox()
            spin.setRange(0, 999999)
            saved_qty = self.init_quantities.get(c.code, 0)
            spin.setValue(saved_qty)
            self.init_series_table.setCellWidget(i, 4, spin)
            self._series_spinboxes.append((c.code, spin))

        self.init_series_table.resizeColumnsToContents()
        self.init_series_table.horizontalHeader().setStretchLastSection(True)

        # 导航按钮状态
        is_first = self.init_current_prefix_index == 0
        is_last = self.init_current_prefix_index == len(self.init_selected_prefixes) - 1
        self.btn_series_prev.setVisible(not is_first)
        self.btn_series_next.setVisible(not is_last)
        self.btn_series_done.setVisible(is_last)

    def _apply_batch_qty(self):
        qty = int(self.batch_combo.currentText())
        for code, spin in self._series_spinboxes:
            spin.setValue(qty)

    def _save_current_series_quantities(self):
        for code, spin in self._series_spinboxes:
            self.init_quantities[code] = spin.value()

    def _series_prev(self):
        self._save_current_series_quantities()
        self.init_current_prefix_index -= 1
        self._load_init_series_page()

    def _series_skip(self):
        for code, spin in self._series_spinboxes:
            spin.setValue(0)
        self._save_current_series_quantities()
        if self.init_current_prefix_index >= len(self.init_selected_prefixes) - 1:
            self._series_done()
            return
        self.init_current_prefix_index += 1
        self._load_init_series_page()

    def _series_next(self):
        self._save_current_series_quantities()
        if self.init_current_prefix_index >= len(self.init_selected_prefixes) - 1:
            self._series_done()
            return
        self.init_current_prefix_index += 1
        self._load_init_series_page()

    def _series_done(self):
        self._save_current_series_quantities()
        inv = Inventory(brand="Mard")
        for code, qty in self.init_quantities.items():
            if qty > 0:
                inv.set(code, qty)
        save_inventory(inv)

        dao = InventoryDao()
        for code, qty in self.init_quantities.items():
            if qty > 0:
                dao.add_transaction(code, qty, qty, "init", note="初始化库存")

        QMessageBox.information(
            self, "完成",
            f"库存初始化完成，共录入 {len(inv.items)} 个色号，{inv.total_count()} 粒"
        )
        self._refresh_normal()
        self._switch_page(0)

    # ---------- 补货流程 ----------

    def _start_restock(self):
        inv = load_inventory()
        if not inv:
            QMessageBox.warning(self, "未初始化", "尚未初始化库存，请先初始化")
            return
        self._init_state()
        self.restock_selected_codes = []
        self.restock_quantities = {}
        self._load_restock_select()
        self._switch_page(3)

    def _build_restock_select_page(self):
        layout = QVBoxLayout(self.page_restock_select)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        title = QLabel("补货录入 — 选择色号")
        title.setObjectName("title")
        layout.addWidget(title)

        # 搜索
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索:"))
        self.restock_search = QLineEdit()
        self.restock_search.setPlaceholderText("输入色号或名称过滤...")
        self.restock_search.textChanged.connect(self._filter_restock)
        search_layout.addWidget(self.restock_search)
        btn_all = QPushButton("全选可见")
        btn_all.clicked.connect(self._select_all_restock)
        btn_none = QPushButton("取消全选")
        btn_none.clicked.connect(self._select_none_restock)
        search_layout.addWidget(btn_all)
        search_layout.addWidget(btn_none)
        layout.addLayout(search_layout)

        # 色号表格
        self.restock_table = QTableWidget()
        self.restock_table.setColumnCount(5)
        self.restock_table.setHorizontalHeaderLabels(["", "色块", "色号", "名称", "HEX"])
        self.restock_table.verticalHeader().setVisible(False)
        self.restock_table.horizontalHeader().setStretchLastSection(True)
        self.restock_table.setAlternatingRowColors(True)
        layout.addWidget(self.restock_table, stretch=1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(lambda: self._switch_page(0))
        btn_next = QPushButton("下一步")
        btn_next.setObjectName("primary")
        btn_next.clicked.connect(self._on_restock_select_next)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_next)
        layout.addLayout(btn_layout)

    def _load_restock_select(self):
        colors = sorted(self.chart.colors.values(), key=lambda c: c.code)
        self.restock_table.setRowCount(len(colors))
        self._restock_checks = []
        for i, c in enumerate(colors):
            cb = QCheckBox()
            self.restock_table.setCellWidget(i, 0, cb)
            self.restock_table.setCellWidget(i, 1, self._make_color_dot(c.hex_color))
            self.restock_table.setItem(i, 2, QTableWidgetItem(c.code))
            self.restock_table.setItem(i, 3, QTableWidgetItem(c.name))
            self.restock_table.setItem(i, 4, QTableWidgetItem(c.hex_color or "-"))
            self._restock_checks.append((c.code, cb))

        self.restock_table.resizeColumnsToContents()
        self.restock_table.horizontalHeader().setStretchLastSection(True)

    def _filter_restock(self, text: str):
        text = text.lower()
        for i, (code, cb) in enumerate(self._restock_checks):
            color = self.chart.get(code)
            name = color.name if color else ""
            match = text in code.lower() or text in name.lower()
            self.restock_table.setRowHidden(i, not match)

    def _select_all_restock(self):
        for i, (code, cb) in enumerate(self._restock_checks):
            if not self.restock_table.isRowHidden(i):
                cb.setChecked(True)

    def _select_none_restock(self):
        for _, cb in self._restock_checks:
            cb.setChecked(False)

    def _on_restock_select_next(self):
        selected = [code for code, cb in self._restock_checks if cb.isChecked()]
        if not selected:
            QMessageBox.information(self, "提示", "请至少选择一个色号")
            return
        self.restock_selected_codes = selected
        self.restock_quantities = {code: 1000 for code in selected}
        self._load_restock_confirm()
        self._switch_page(4)

    def _build_restock_confirm_page(self):
        layout = QVBoxLayout(self.page_restock_confirm)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)

        title = QLabel("补货录入 — 确认数量")
        title.setObjectName("title")
        layout.addWidget(title)

        desc = QLabel("默认每个色号 1000 粒，可在下方修改具体数量。")
        desc.setStyleSheet("font-size:14px;color:#666;")
        layout.addWidget(desc)

        self.restock_confirm_table = QTableWidget()
        self.restock_confirm_table.setColumnCount(5)
        self.restock_confirm_table.setHorizontalHeaderLabels(["色块", "色号", "名称", "HEX", "数量"])
        self.restock_confirm_table.verticalHeader().setVisible(False)
        self.restock_confirm_table.horizontalHeader().setStretchLastSection(True)
        self.restock_confirm_table.setAlternatingRowColors(True)
        layout.addWidget(self.restock_confirm_table, stretch=1)

        btn_layout = QHBoxLayout()
        btn_back = QPushButton("返回修改")
        btn_back.clicked.connect(self._on_restock_confirm_back)
        btn_confirm = QPushButton("确认入库")
        btn_confirm.setObjectName("primary")
        btn_confirm.clicked.connect(self._on_restock_confirm)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_back)
        btn_layout.addWidget(btn_confirm)
        layout.addLayout(btn_layout)

    def _load_restock_confirm(self):
        self.restock_confirm_table.setRowCount(len(self.restock_selected_codes))
        self._restock_confirm_spins = []
        for i, code in enumerate(sorted(self.restock_selected_codes)):
            color = self.chart.get(code)
            self.restock_confirm_table.setCellWidget(
                i, 0, self._make_color_dot(color.hex_color if color else None)
            )
            self.restock_confirm_table.setItem(i, 1, QTableWidgetItem(code))
            self.restock_confirm_table.setItem(i, 2, QTableWidgetItem(color.name if color else "未知"))
            self.restock_confirm_table.setItem(i, 3, QTableWidgetItem(color.hex_color if color else "-"))

            spin = QSpinBox()
            spin.setRange(0, 999999)
            spin.setValue(self.restock_quantities.get(code, 1000))
            self.restock_confirm_table.setCellWidget(i, 4, spin)
            self._restock_confirm_spins.append((code, spin))

        self.restock_confirm_table.resizeColumnsToContents()
        self.restock_confirm_table.horizontalHeader().setStretchLastSection(True)

    def _on_restock_confirm_back(self):
        for code, spin in self._restock_confirm_spins:
            self.restock_quantities[code] = spin.value()
        self._switch_page(3)

    def _on_restock_confirm(self):
        for code, spin in self._restock_confirm_spins:
            self.restock_quantities[code] = spin.value()

        inv = load_inventory()
        if not inv:
            QMessageBox.warning(self, "错误", "库存未初始化")
            return

        added_count = 0
        for code, qty in self.restock_quantities.items():
            if qty > 0:
                inv.add(code, qty)
                added_count += 1

        save_inventory(inv)

        dao = InventoryDao()
        for code, qty in self.restock_quantities.items():
            if qty > 0:
                balance = inv.get_quantity(code)
                dao.add_transaction(code, qty, balance, "add", note="补货录入")

        QMessageBox.information(self, "完成", f"补货完成，共添加 {added_count} 个色号")
        self._refresh_normal()
        self._switch_page(0)
