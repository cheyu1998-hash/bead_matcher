"""图片转换 Tab"""

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from bead_matcher.color_chart import list_brands
from bead_matcher.pattern_converter import convert_image_to_pattern, suggest_grid_size
from bead_matcher.pattern_storage import PatternLibrary
from bead_matcher.thumbnail import generate_thumbnail


class DropLabel(QLabel):
    """支持拖拽文件上传的 QLabel"""

    dropped = pyqtSignal(Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(80)
        self.setText("拖拽图片到此处\n或点击浏览")
        self.setStyleSheet(
            "QLabel { background:#f5f7fa; border:2px dashed #ccc; border-radius:8px; color:#888; font-size:13px; }"
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

    def mousePressEvent(self, event):
        self.parent()._browse()


class ConvertTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_path: Path | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        title = QLabel("图片转拼豆图案")
        title.setObjectName("title")
        layout.addWidget(title)

        # 图片拖拽区域
        drop_group = QGroupBox("选择图片")
        drop_layout = QVBoxLayout(drop_group)
        self.drop_label = DropLabel(self)
        self.drop_label.dropped.connect(self._on_dropped)
        drop_layout.addWidget(self.drop_label)
        layout.addWidget(drop_group)

        # 参数
        param_group = QGroupBox("参数")
        param_layout = QFormLayout(param_group)
        param_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        param_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        param_layout.setSpacing(12)

        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("如 皮卡丘")
        param_layout.addRow("图案名称 *", self.input_name)

        brand_layout = QHBoxLayout()
        self.combo_brand = QComboBox()
        for b in list_brands():
            self.combo_brand.addItem(b)
        self.combo_brand.setFixedWidth(120)
        brand_layout.addWidget(self.combo_brand)
        brand_layout.addStretch()
        param_layout.addRow("品牌", brand_layout)

        size_layout = QHBoxLayout()
        self.spin_w = QSpinBox()
        self.spin_w.setRange(1, 999)
        self.spin_w.setValue(48)
        self.spin_w.setFixedWidth(70)
        size_layout.addWidget(self.spin_w)
        size_layout.addWidget(QLabel("x"))
        self.spin_h = QSpinBox()
        self.spin_h.setRange(1, 999)
        self.spin_h.setValue(48)
        self.spin_h.setFixedWidth(70)
        size_layout.addWidget(self.spin_h)
        btn_suggest = QPushButton("自动建议")
        btn_suggest.setObjectName("secondary")
        btn_suggest.setFixedWidth(80)
        btn_suggest.clicked.connect(self._suggest)
        size_layout.addWidget(btn_suggest)
        size_layout.addStretch()
        param_layout.addRow("尺寸（格子）", size_layout)

        layout.addWidget(param_group)

        # 转换按钮
        btn_convert = QPushButton("开始转换")
        btn_convert.setObjectName("primary")
        btn_convert.setMinimumHeight(40)
        btn_convert.setMaximumWidth(160)
        btn_convert.clicked.connect(self._convert)
        layout.addWidget(btn_convert, alignment=Qt.AlignmentFlag.AlignLeft)

        # 结果
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)

        layout.addStretch()

    def _on_dropped(self, path: Path):
        self.image_path = path
        self.drop_label.setText(f"已选择: {path.name}")
        self.drop_label.setStyleSheet(
            "QLabel { background:#e8f5e9; border:2px solid #4caf50; border-radius:8px; color:#2e7d32; font-size:13px; }"
        )
        self._suggest()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "图片 (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if path:
            self._on_dropped(Path(path))

    def _suggest(self):
        if not self.image_path or not self.image_path.exists():
            return
        try:
            w, h = suggest_grid_size(self.image_path)
            self.spin_w.setValue(w)
            self.spin_h.setValue(h)
        except Exception:
            pass

    def _convert(self):
        if not self.image_path or not self.image_path.exists():
            self.result_label.setText("❌ 请先选择图片")
            self.result_label.setObjectName("error_msg")
            self._refresh_result_style()
            return

        name = self.input_name.text().strip()
        if not name:
            self.result_label.setText("❌ 请输入图案名称")
            self.result_label.setObjectName("error_msg")
            self._refresh_result_style()
            return

        brand = self.combo_brand.currentText()
        w = self.spin_w.value()
        h = self.spin_h.value()

        try:
            pattern = convert_image_to_pattern(
                image_path=self.image_path,
                brand=brand,
                target_width=w,
                target_height=h,
                name=name,
                source_image=str(self.image_path),
            )
            lib = PatternLibrary()
            lib.add(pattern)
            try:
                generate_thumbnail(self.image_path, pattern.id)
            except Exception as e:
                self.result_label.setText(
                    self.result_label.text() + f"\n⚠️ 缩略图生成失败: {e}"
                )
            self.result_label.setText(
                f"✅ 已保存「{pattern.name}」\n"
                f"品牌: {pattern.brand}  尺寸: {pattern.width}x{pattern.height}\n"
                f"总粒数: {pattern.total_beads()}  色号数: {len(pattern.color_usage)}"
            )
            self.result_label.setObjectName("success_msg")
            self._refresh_result_style()
        except Exception as e:
            self.result_label.setText(f"❌ 转换失败: {e}")
            self.result_label.setObjectName("error_msg")
            self._refresh_result_style()

    def _refresh_result_style(self):
        self.result_label.style().unpolish(self.result_label)
        self.result_label.style().polish(self.result_label)
        self.result_label.update()
