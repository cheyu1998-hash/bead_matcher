"""图案库 Tab"""

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bead_matcher.color_chart import get_chart
from bead_matcher.pattern_storage import PatternLibrary
from bead_matcher.thumbnail import generate_thumbnail, get_thumbnail_path, thumbnail_exists


class DropArea(QLabel):
    """支持文件拖拽的 QLabel"""

    dropped = pyqtSignal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(120)
        self.setText("拖拽图片到此处\n（支持从微信、文件管理器直接拖）")
        self.setStyleSheet(
            "QLabel { background:#f0f2f5; border:2px dashed #ccc; border-radius:8px; color:#888; font-size:14px; }"
        )

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = Path(urls[0].toLocalFile())
            if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".gif"):
                self.dropped.emit(path)
        event.acceptProposedAction()


class PatternTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        title = QLabel("图案库")
        title.setObjectName("title")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        btn_new = QPushButton("+ 手动录入图案")
        btn_new.setObjectName("primary")
        btn_new.clicked.connect(self._show_manual_dialog)
        toolbar.addWidget(btn_new)
        toolbar.addStretch()

        btn_delete = QPushButton("删除选中")
        btn_delete.setObjectName("danger")
        btn_delete.clicked.connect(self._delete_selected)
        toolbar.addWidget(btn_delete)

        btn_refresh = QPushButton("刷新")
        btn_refresh.setObjectName("secondary")
        btn_refresh.clicked.connect(self._refresh)
        toolbar.addWidget(btn_refresh)
        layout.addLayout(toolbar)

        # 搜索与筛选栏
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索图案名称...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._refresh)
        filter_bar.addWidget(self.search_input, stretch=2)

        self.filter_brand = QComboBox()
        self.filter_brand.addItem("全部品牌")
        self.filter_brand.currentTextChanged.connect(self._refresh)
        filter_bar.addWidget(self.filter_brand)

        self.filter_status = QComboBox()
        self.filter_status.addItems(["全部状态", "待制作", "已完成"])
        self.filter_status.currentTextChanged.connect(self._refresh)
        filter_bar.addWidget(self.filter_status)

        self.filter_ip = QComboBox()
        self.filter_ip.addItem("全部来源")
        self.filter_ip.currentTextChanged.connect(self._refresh)
        filter_bar.addWidget(self.filter_ip)

        layout.addLayout(filter_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["缩略图", "名称", "品牌", "尺寸", "粒数", "色号数", "状态", "来源"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(64)
        self.table.cellClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table, stretch=1)

    def _refresh(self):
        lib = PatternLibrary()
        patterns = lib.list_all()

        # 收集所有品牌与 IP 用于筛选下拉框（去重）
        all_brands = sorted({p.brand for p in patterns if p.brand})
        all_ips = sorted({ip for p in patterns for ip in p.ip_name if ip})

        # 保留当前选择
        prev_brand = self.filter_brand.currentText()
        prev_ip = self.filter_ip.currentText()

        # 重建品牌下拉（保留"全部品牌"）
        if self.filter_brand.count() == 1 or set(all_brands) != {
            self.filter_brand.itemText(i) for i in range(1, self.filter_brand.count())
        }:
            self.filter_brand.blockSignals(True)
            self.filter_brand.clear()
            self.filter_brand.addItem("全部品牌")
            self.filter_brand.addItems(all_brands)
            if prev_brand in all_brands:
                self.filter_brand.setCurrentText(prev_brand)
            self.filter_brand.blockSignals(False)

        # 重建 IP 下拉（保留"全部来源"）
        if self.filter_ip.count() == 1 or set(all_ips) != {
            self.filter_ip.itemText(i) for i in range(1, self.filter_ip.count())
        }:
            self.filter_ip.blockSignals(True)
            self.filter_ip.clear()
            self.filter_ip.addItem("全部来源")
            self.filter_ip.addItems(all_ips)
            if prev_ip in all_ips:
                self.filter_ip.setCurrentText(prev_ip)
            self.filter_ip.blockSignals(False)

        # 应用筛选
        search_text = self.search_input.text().strip().lower()
        brand_filter = self.filter_brand.currentText()
        status_filter = self.filter_status.currentText()
        ip_filter = self.filter_ip.currentText()

        filtered = []
        for p in patterns:
            if search_text and search_text not in p.name.lower():
                continue
            if brand_filter != "全部品牌" and p.brand != brand_filter:
                continue
            if status_filter == "待制作" and p.status != "pending":
                continue
            if status_filter == "已完成" and p.status != "done":
                continue
            if ip_filter != "全部来源" and ip_filter not in p.ip_name:
                continue
            filtered.append(p)

        self.table.setRowCount(len(filtered))
        for i, p in enumerate(filtered):
            # 缩略图
            if thumbnail_exists(p.id):
                thumb_label = QLabel()
                pixmap = QPixmap(str(get_thumbnail_path(p.id)))
                thumb_label.setPixmap(
                    pixmap.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )
                thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                thumb_label.setCursor(Qt.CursorShape.PointingHandCursor)
                thumb_label.setToolTip("点击查看大图")
                self.table.setCellWidget(i, 0, thumb_label)
            else:
                self.table.setItem(i, 0, QTableWidgetItem("-"))

            name_text = p.name
            if p.ip_name:
                name_text += "\n" + " ".join(f"[{ip}]" for ip in p.ip_name)
            item_name = QTableWidgetItem(name_text)
            item_name.setData(Qt.ItemDataRole.UserRole, p.id)
            self.table.setItem(i, 1, item_name)

            self.table.setItem(i, 2, QTableWidgetItem(p.brand))
            size_text = f"{p.width}x{p.height}" if p.width > 0 and p.height > 0 else "-"
            self.table.setItem(i, 3, QTableWidgetItem(size_text))
            self.table.setItem(i, 4, QTableWidgetItem(str(p.total_beads())))
            self.table.setItem(i, 5, QTableWidgetItem(str(len(p.color_usage))))
            status_text = "已完成" if p.status == "done" else "待制作"
            self.table.setItem(i, 6, QTableWidgetItem(status_text))
            self.table.setItem(i, 7, QTableWidgetItem(p.input_mode))
        self.table.resizeColumnsToContents()

    def _on_cell_clicked(self, row: int, column: int):
        if column != 0:
            return
        item = self.table.item(row, 1)
        if not item:
            return
        pattern_id = item.data(Qt.ItemDataRole.UserRole)
        name = item.text().split("\n")[0]
        dialog = ImageViewerDialog(pattern_id, name, self)
        dialog.exec()

    def _delete_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(self, "提示", "请先选中要删除的图案")
            return

        row = selected[0].row()
        item = self.table.item(row, 1)
        pattern_id = item.data(Qt.ItemDataRole.UserRole)
        name = item.text().split("\n")[0]

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除图案「{name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        lib = PatternLibrary()
        if lib.remove_by_id(pattern_id):
            self._refresh()
        else:
            QMessageBox.warning(self, "错误", "删除失败")

    def _show_manual_dialog(self):
        dialog = ManualPatternDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh()


class ImageViewerDialog(QDialog):
    """大图查看对话框"""

    def __init__(self, pattern_id: str, pattern_name: str, parent=None):
        super().__init__(parent)
        self.pattern_id = pattern_id
        self.setWindowTitle(f"{pattern_name} - 大图查看")
        self.setMinimumSize(600, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("QLabel { background:#f5f5f5; border-radius:8px; }")
        layout.addWidget(self.image_label, stretch=1)

        # 尝试加载原图，失败则加载缩略图
        from bead_matcher.thumbnail import get_image_path, get_thumbnail_path

        img_path = get_image_path(self.pattern_id)
        if not img_path.exists():
            img_path = get_thumbnail_path(self.pattern_id)

        self._original_pixmap = None
        if img_path.exists():
            self._original_pixmap = QPixmap(str(img_path))
            self._set_pixmap()
        else:
            self.image_label.setText("暂无图片")
            self.image_label.setStyleSheet("QLabel { background:#f5f5f5; border-radius:8px; color:#999; font-size:16px; }")

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _set_pixmap(self):
        """按对话框大小缩放图片，保持比例"""
        if not self._original_pixmap:
            return
        available = self.image_label.size()
        scaled = self._original_pixmap.scaled(
            available.width(),
            available.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._original_pixmap:
            self._set_pixmap()


class ManualPatternDialog(QDialog):
    """手动录入图案对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("手动录入拼豆图案")
        self.setMinimumSize(900, 750)
        self.selected_colors = []  # [(code, quantity), ...] in click order
        self.chart = get_chart("Mard")
        self.known_ips = self._load_known_ips()
        self.selected_ips = []  # 多选
        self.thumbnail_path = None
        self._setup_ui()

    def _load_known_ips(self):
        lib = PatternLibrary()
        return lib.list_ip_tags()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QVBoxLayout(content)
        form.setSpacing(16)

        # 基本信息
        info_group = QGroupBox("基本信息")
        info_layout = QFormLayout(info_group)
        info_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        info_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        info_layout.setSpacing(12)

        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("如 皮卡丘")
        info_layout.addRow("图案名称 *", self.input_name)

        # IP 标签行（多选 + 内联输入）
        self.ip_container = QWidget()
        self.ip_layout = QHBoxLayout(self.ip_container)
        self.ip_layout.setContentsMargins(0, 0, 0, 0)
        self.ip_layout.setSpacing(6)

        # 标签按钮容器（独立，便于局部刷新）
        self._tag_container = QWidget()
        self._tag_layout = QHBoxLayout(self._tag_container)
        self._tag_layout.setContentsMargins(0, 0, 0, 0)
        self._tag_layout.setSpacing(6)
        self.ip_layout.addWidget(self._tag_container)

        # + 按钮
        add_btn = QPushButton("＋")
        add_btn.setFixedSize(28, 28)
        add_btn.setStyleSheet(
            "QPushButton {background:#f0f0f0;color:#666;border-radius:14px;font-size:14px;font-weight:bold;border:1px dashed #ccc;}"
            "QPushButton:hover {background:#e0e0e0;}"
        )
        add_btn.clicked.connect(self._show_ip_input)
        self.ip_layout.addWidget(add_btn)
        self.ip_layout.addStretch()

        # 内联输入框（默认隐藏）
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("输入新标签，回车确认")
        self.ip_input.setFixedWidth(160)
        self.ip_input.setFixedHeight(28)
        self.ip_input.setStyleSheet(
            "QLineEdit {border:1px solid #4f8cff;border-radius:12px;padding:2px 10px;font-size:12px;}"
        )
        self.ip_input.returnPressed.connect(self._confirm_new_ip)
        self.ip_input.hide()
        self.ip_layout.addWidget(self.ip_input)

        self._refresh_ip_tags()
        info_layout.addRow("IP / 来源", self.ip_container)

        # 品牌 + 状态
        bs_widget = QWidget()
        bs_layout = QHBoxLayout(bs_widget)
        bs_layout.setContentsMargins(0, 0, 0, 0)
        bs_layout.setSpacing(8)
        self.combo_brand = QComboBox()
        self.combo_brand.addItem("Mard")
        self.combo_brand.setFixedWidth(120)
        bs_layout.addWidget(self.combo_brand)
        bs_layout.addWidget(QLabel("状态:"))
        self.combo_status = QComboBox()
        self.combo_status.addItems(["待制作", "已完成"])
        self.combo_status.setCurrentIndex(0)
        self.combo_status.setFixedWidth(100)
        bs_layout.addWidget(self.combo_status)
        bs_layout.addStretch()
        info_layout.addRow("品牌 / 状态", bs_widget)

        # 尺寸
        size_widget = QWidget()
        size_layout = QHBoxLayout(size_widget)
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.setSpacing(4)
        self.spin_width = QSpinBox()
        self.spin_width.setRange(1, 999)
        self.spin_width.setValue(50)
        self.spin_width.setFixedWidth(70)
        size_layout.addWidget(self.spin_width)
        size_layout.addWidget(QLabel("x"))
        self.spin_height = QSpinBox()
        self.spin_height.setRange(1, 999)
        self.spin_height.setValue(50)
        self.spin_height.setFixedWidth(70)
        size_layout.addWidget(self.spin_height)
        size_layout.addWidget(QLabel("格子"))
        size_layout.addStretch()
        info_layout.addRow("尺寸", size_widget)

        form.addWidget(info_group)

        # 色号选择
        color_group = QGroupBox("色号选择 *")
        color_layout = QVBoxLayout(color_group)
        color_layout.setSpacing(12)

        # 色块网格
        picker_scroll = QScrollArea()
        picker_scroll.setWidgetResizable(True)
        picker_widget = QWidget()
        picker_grid = QGridLayout(picker_widget)
        picker_grid.setSpacing(6)
        picker_grid.setVerticalSpacing(8)

        self._color_buttons = {}  # code -> QPushButton
        if self.chart:
            prefixes = self.chart.list_prefixes()
            row = 0
            for prefix in prefixes:
                label = QLabel(f"<b>{prefix} 系列</b>")
                picker_grid.addWidget(label, row, 0, Qt.AlignmentFlag.AlignTop)
                colors = self.chart.get_by_prefix(prefix)
                col = 1
                for c in colors:
                    btn = QPushButton(c.code)
                    btn.setToolTip(f"{c.name}")
                    btn.setCheckable(True)
                    btn.setFixedSize(50, 32)
                    text_color = "#fff" if self._is_dark(c.hex_color) else "#333"
                    btn.setStyleSheet(
                        f"QPushButton {{background:{c.hex_color};border-radius:4px;font-size:10px;font-weight:bold;color:{text_color};border:1px solid #ccc;}}"
                        f"QPushButton:checked {{border:2px solid #333;}}"
                    )
                    btn.clicked.connect(lambda checked, code=c.code: self._toggle_color(code, checked))
                    self._color_buttons[c.code] = btn
                    picker_grid.addWidget(btn, row, col)
                    col += 1
                    if col > 16:
                        col = 1
                        row += 1
                row += 1

        picker_scroll.setWidget(picker_widget)
        picker_scroll.setMaximumHeight(320)
        color_layout.addWidget(picker_scroll)

        # 已选色号行（按点击顺序）
        color_layout.addWidget(QLabel("已选色号（按点击顺序，可用 ◀ ▶ 调整）："))
        self.selected_scroll = QScrollArea()
        self.selected_scroll.setWidgetResizable(True)
        self.selected_container = QWidget()
        self.selected_row = QHBoxLayout(self.selected_container)
        self.selected_row.setContentsMargins(8, 8, 8, 8)
        self.selected_row.setSpacing(8)
        self.selected_row.addStretch()
        self.selected_scroll.setWidget(self.selected_container)
        self.selected_scroll.setMinimumHeight(90)
        self.selected_scroll.setMaximumHeight(110)
        self.selected_scroll.setStyleSheet("QScrollArea {background:#f5f7fa;border-radius:8px;}")
        color_layout.addWidget(self.selected_scroll)

        # 数量统一录入表
        self.qty_table = QTableWidget()
        self.qty_table.setColumnCount(4)
        self.qty_table.setHorizontalHeaderLabels(["色号", "名称", "色样", "数量"])
        self.qty_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.qty_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.qty_table.setColumnWidth(2, 40)
        self.qty_table.setMaximumHeight(220)
        self.qty_table.verticalHeader().setVisible(False)
        color_layout.addWidget(self.qty_table)

        form.addWidget(color_group)

        # 缩略图拖拽
        thumb_group = QGroupBox("缩略图（可选）")
        thumb_layout = QVBoxLayout(thumb_group)
        self.thumb_drop = DropArea()
        self.thumb_drop.dropped.connect(self._on_thumb_dropped)
        thumb_layout.addWidget(self.thumb_drop)
        form.addWidget(thumb_group)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # 按钮
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._submit)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _is_dark(self, hex_color: str) -> bool:
        if not hex_color or len(hex_color) < 7:
            return False
        hex_color = hex_color.lstrip("#")
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r * 299 + g * 587 + b * 114) / 1000 < 128
        except ValueError:
            return False

    def _refresh_ip_tags(self):
        # 只刷新标签按钮容器，不重建输入框（避免在信号槽中删除发送者）
        while self._tag_layout.count():
            item = self._tag_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for ip in self.known_ips:
            btn = QPushButton(ip)
            btn.setCheckable(True)
            btn.setChecked(ip in self.selected_ips)
            btn.setFixedHeight(28)
            btn.setStyleSheet(
                "QPushButton {background:#e3f2fd;color:#1565c0;border-radius:12px;padding:2px 12px;font-size:12px;border:1px solid #bbdefb;}"
                "QPushButton:checked {background:#1565c0;color:#fff;}"
            )
            btn.clicked.connect(lambda checked, ip=ip: self._on_ip_toggled(ip, checked))
            self._tag_layout.addWidget(btn)
        self._tag_layout.addStretch()

    def _on_ip_toggled(self, ip: str, checked: bool):
        if checked:
            if ip not in self.selected_ips:
                self.selected_ips.append(ip)
        else:
            if ip in self.selected_ips:
                self.selected_ips.remove(ip)

    def _show_ip_input(self):
        self.ip_input.show()
        self.ip_input.setFocus()

    def _confirm_new_ip(self):
        text = self.ip_input.text().strip()
        if not text:
            self.ip_input.hide()
            return
        if text not in self.known_ips:
            self.known_ips.append(text)
            # 写入数据库
            lib = PatternLibrary()
            lib.add_ip_tag(text)
        if text not in self.selected_ips:
            self.selected_ips.append(text)
        self.ip_input.clear()
        self.ip_input.hide()
        self._refresh_ip_tags()

    def _toggle_color(self, code: str, checked: bool):
        codes = [c for c, q in self.selected_colors]
        if checked and code not in codes:
            self.selected_colors.append((code, 100))
        elif not checked and code in codes:
            self.selected_colors = [(c, q) for c, q in self.selected_colors if c != code]
        self._refresh_selected()

    def _refresh_selected(self):
        # 刷新已选色号行
        while self.selected_row.count() > 1:
            item = self.selected_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.selected_colors:
            lbl = QLabel("点击上方色块添加色号")
            lbl.setStyleSheet("color:#999;font-size:12px;")
            self.selected_row.insertWidget(0, lbl)
        else:
            color_map = self.chart.colors if self.chart else {}
            for idx, (code, qty) in enumerate(self.selected_colors):
                card = self._make_selected_card(idx, code, qty, color_map.get(code))
                self.selected_row.insertWidget(idx, card)

        # 刷新数量表
        self._refresh_qty_table()

    def _make_selected_card(self, idx: int, code: str, qty: int, color):
        card = QWidget()
        card.setFixedSize(86, 72)
        card.setStyleSheet("QWidget {background:#fff;border:1px solid #ddd;border-radius:6px;}")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        top = QHBoxLayout()
        dot = QLabel()
        dot.setFixedSize(16, 16)
        if color and color.hex_color:
            dot.setStyleSheet(f"background:{color.hex_color};border-radius:3px;border:1px solid #ccc;")
        top.addWidget(dot)
        lbl = QLabel(f"<b>{code}</b>")
        lbl.setStyleSheet("font-size:10px;")
        top.addWidget(lbl)
        top.addStretch()
        del_btn = QPushButton("×")
        del_btn.setFixedSize(16, 16)
        del_btn.setStyleSheet("QPushButton {background:transparent;color:#999;font-size:11px;padding:0;} QPushButton:hover {color:#f44;}")
        del_btn.clicked.connect(lambda: self._remove_color(code))
        top.addWidget(del_btn)
        layout.addLayout(top)

        arrows = QHBoxLayout()
        left = QPushButton("◀")
        left.setFixedSize(24, 18)
        left.setEnabled(idx > 0)
        left.setStyleSheet("font-size:9px;padding:0;")
        left.clicked.connect(lambda: self._move_color(idx, -1))
        arrows.addWidget(left)
        right = QPushButton("▶")
        right.setFixedSize(24, 18)
        right.setEnabled(idx < len(self.selected_colors) - 1)
        right.setStyleSheet("font-size:9px;padding:0;")
        right.clicked.connect(lambda: self._move_color(idx, 1))
        arrows.addWidget(right)
        layout.addLayout(arrows)
        return card

    def _remove_color(self, code: str):
        self.selected_colors = [(c, q) for c, q in self.selected_colors if c != code]
        btn = self._color_buttons.get(code)
        if btn:
            btn.setChecked(False)
        self._refresh_selected()

    def _move_color(self, idx: int, delta: int):
        new_idx = idx + delta
        if 0 <= new_idx < len(self.selected_colors):
            self.selected_colors[idx], self.selected_colors[new_idx] = (
                self.selected_colors[new_idx],
                self.selected_colors[idx],
            )
            self._refresh_selected()

    def _refresh_qty_table(self):
        self.qty_table.setRowCount(len(self.selected_colors))
        color_map = self.chart.colors if self.chart else {}
        for i, (code, qty) in enumerate(self.selected_colors):
            c = color_map.get(code)
            self.qty_table.setItem(i, 0, QTableWidgetItem(code))
            self.qty_table.setItem(i, 1, QTableWidgetItem(c.name if c else "未知"))

            dot = QLabel()
            dot.setFixedSize(18, 18)
            if c and c.hex_color:
                dot.setStyleSheet(f"background:{c.hex_color};border-radius:4px;border:1px solid #ccc;")
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.qty_table.setCellWidget(i, 2, dot)

            spin = QSpinBox()
            spin.setRange(1, 99999)
            spin.setValue(qty)
            spin.valueChanged.connect(lambda v, c=code: self._update_qty(c, v))
            self.qty_table.setCellWidget(i, 3, spin)

    def _update_qty(self, code: str, value: int):
        for i, (c, q) in enumerate(self.selected_colors):
            if c == code:
                self.selected_colors[i] = (c, value)
                break

    def _on_thumb_dropped(self, path: Path):
        self.thumbnail_path = path
        self.thumb_drop.setText(f"已接收: {path.name}\n保存时将生成缩略图")
        self.thumb_drop.setStyleSheet(
            "QLabel { background:#e8f5e9; border:2px solid #4caf50; border-radius:8px; color:#2e7d32; font-size:14px; }"
        )

    def _submit(self):
        name = self.input_name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入图案名称")
            return
        if not self.selected_colors:
            QMessageBox.warning(self, "提示", "请至少选择一个色号")
            return

        status_map = {"待制作": "pending", "已完成": "done"}
        brand = self.combo_brand.currentText()
        status = status_map.get(self.combo_status.currentText(), "pending")
        width = self.spin_width.value()
        height = self.spin_height.value()
        color_usage = {code: qty for code, qty in self.selected_colors}

        lib = PatternLibrary()
        pattern = lib.create_manual(
            name=name,
            color_usage=color_usage,
            brand=brand,
            width=width,
            height=height,
            ip_name=list(self.selected_ips) if self.selected_ips else None,
            status=status,
            tags=[],
        )

        if self.thumbnail_path:
            try:
                generate_thumbnail(self.thumbnail_path, pattern.id)
            except Exception as e:
                QMessageBox.warning(self, "缩略图", f"缩略图保存失败: {e}")

        self.accept()
