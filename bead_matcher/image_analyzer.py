"""图片色号分析器：支持 OCR 文字识别 和 像素颜色匹配 两种模式。"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from .color_chart import ColorChart, get_chart


def _configure_tesseract():
    """配置 pytesseract 路径（Windows 需要显式指定）"""
    import os
    import sys

    if sys.platform == "win32":
        tesseract_exe = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        if tesseract_exe.exists():
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = str(tesseract_exe)
            except ImportError:
                pass
        # 使用项目目录下的 tessdata（包含 chi_sim + eng）
        project_tessdata = Path(__file__).parent.parent / "tessdata"
        if project_tessdata.exists():
            os.environ["TESSDATA_PREFIX"] = str(project_tessdata)


@dataclass
class OcrItem:
    """OCR 识别出的色号条目"""
    code: str
    quantity: Optional[int] = None
    confidence: float = 1.0
    raw_text: str = ""


@dataclass
class PixelItem:
    """像素分析识别出的色号条目"""
    code: str
    name: str
    hex_color: str
    pixel_count: int
    distance: float


@dataclass
class AnalysisResult:
    """图片分析结果"""
    brand: str
    mode: str  # "ocr" | "pixel"
    width: int = 0
    height: int = 0
    ocr_items: List[OcrItem] = field(default_factory=list)
    pixel_items: List[PixelItem] = field(default_factory=list)

    @property
    def total_pixels(self) -> int:
        if self.mode == "pixel":
            return sum(item.pixel_count for item in self.pixel_items)
        total_qty = sum(item.quantity or 0 for item in self.ocr_items)
        return total_qty if total_qty > 0 else len(self.ocr_items)

    @property
    def color_count(self) -> int:
        if self.mode == "pixel":
            return len(self.pixel_items)
        return len(self.ocr_items)


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_distance(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
    return ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2) ** 0.5


def _find_nearest_color(r: int, g: int, b: int, chart: ColorChart) -> Tuple[str, str, str, float]:
    best_code, best_name, best_hex, best_dist = None, None, None, float("inf")
    target = (r, g, b)
    for code, bead_color in chart.colors.items():
        if not bead_color.hex_color:
            continue
        rgb = _hex_to_rgb(bead_color.hex_color)
        dist = _rgb_distance(target, rgb)
        if dist < best_dist:
            best_dist = dist
            best_code = code
            best_name = bead_color.name
            best_hex = bead_color.hex_color
    return best_code, best_name, best_hex, best_dist


def _normalize_mard_code(code: str) -> str:
    """统一 Mard 色号格式，如 A1 -> A01, ZG1 -> ZG1"""
    m = re.match(r'^([A-Za-z]+)(\d+)$', code)
    if not m:
        return code.upper()
    prefix, num = m.groups()
    prefix = prefix.upper()
    num = int(num)
    if len(prefix) == 1:
        return f"{prefix}{num:02d}"
    return f"{prefix}{num}"


def _correct_ocr_code(code: str, valid_codes: set) -> str:
    """
    纠正 OCR 常见误识别。如果纠正后在色卡中存在，返回纠正后的色号。
    """
    if code in valid_codes:
        return code

    # 常见 OCR 误识别映射（基于字体相似性）
    corrections = {
        "B02": "D02", "B08": "D08", "B10": "D10", "B11": "D11",
        "B17": "D17", "B19": "D19", "B22": "D22", "B23": "D23",
        "L06": "E16", "L16": "E16", "L17": "E17", "L20": "E20",
        "L22": "E22", "L24": "E24",
        "H02": "H2", "H03": "H3", "H04": "H4", "H05": "H5",
        "H07": "H7", "H08": "H8",
        "A07": "D17",  # 上下文推断
        "I07": "D17",  # 上下文推断
        "I28": "E16",  # 上下文推断
        "Z03": "D23",  # 上下文推断
        "O01": "D11",  # 上下文推断
        "001": "D11",  # 上下文推断
    }

    if code in corrections:
        corrected = corrections[code]
        if corrected in valid_codes:
            return corrected

    return code


def detect_image_type(image_path: Path) -> str:
    """
    自动检测图纸类型。
    若系统装有 pytesseract 且能识别到色号文字，返回 'ocr'，否则 'pixel'。
    """
    try:
        import pytesseract
        from PIL import Image

        _configure_tesseract()

        img = Image.open(image_path)
        scale = 2
        img_large = img.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)
        text = pytesseract.image_to_string(img_large, lang="chi_sim+eng")

        # 检测是否包含色号模式
        if re.search(r'[A-Z]+\d{1,2}', text) or re.search(r'\b\d{2,3}\b', text):
            return "ocr"
    except ImportError:
        pass
    except Exception:
        pass
    return "pixel"


def _analyze_by_pixels(
    image_path: Path,
    brand: str,
    max_colors: int = 20,
    target_width: Optional[int] = None,
    target_height: Optional[int] = None,
) -> AnalysisResult:
    """像素颜色匹配模式"""
    from PIL import Image

    chart = get_chart(brand)
    if not chart:
        available = ", ".join(["Perler", "Mard"])
        raise ValueError(f"未知品牌: {brand}，可用: {available}")

    img = Image.open(image_path).convert("RGB")
    orig_w, orig_h = img.size

    if target_width and target_height:
        img = img.resize((target_width, target_height), Image.Resampling.NEAREST)
    elif target_width:
        ratio = target_width / orig_w
        target_height = int(orig_h * ratio)
        img = img.resize((target_width, target_height), Image.Resampling.NEAREST)
    elif target_height:
        ratio = target_height / orig_h
        target_width = int(orig_w * ratio)
        img = img.resize((target_width, target_height), Image.Resampling.NEAREST)

    w, h = img.size
    quantized = img.quantize(colors=max_colors, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()
    color_counts = quantized.getcolors()

    palette_rgb = []
    for i in range(max_colors):
        idx = i * 3
        if idx + 2 < len(palette):
            palette_rgb.append((palette[idx], palette[idx + 1], palette[idx + 2]))
        else:
            palette_rgb.append((0, 0, 0))

    matches = []
    for count, palette_idx in color_counts:
        if palette_idx < len(palette_rgb):
            r, g, b = palette_rgb[palette_idx]
            code, name, hex_color, dist = _find_nearest_color(r, g, b, chart)
            matches.append((code, name, hex_color, count, dist))

    merged: dict = {}
    for code, name, hex_color, count, dist in matches:
        if code not in merged:
            merged[code] = [name, hex_color, count, dist]
        else:
            merged[code][2] += count
            merged[code][3] = min(merged[code][3], dist)

    items = [(code, info[0], info[1], info[2], info[3]) for code, info in merged.items()]
    # 按用量降序、色差升序排列（用量多的优先，同用量时匹配精度高的优先）
    sorted_items = sorted(items, key=lambda x: (-x[3], x[4]))

    result = AnalysisResult(brand=brand, mode="pixel", width=w, height=h)
    result.pixel_items = [PixelItem(*item) for item in sorted_items]
    return result


def _analyze_by_ocr(image_path: Path, brand: str) -> AnalysisResult:
    """OCR 文字识别模式：提取图纸上的色号清单"""
    try:
        import pytesseract
        from PIL import Image
        _configure_tesseract()
    except ImportError:
        raise ImportError(
            "OCR 模式需要 pytesseract，请运行: pip install pytesseract\n"
            "同时需要安装 Tesseract-OCR 引擎:\n"
            "  Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
            "  macOS: brew install tesseract tesseract-lang\n"
            "  Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-chi-sim"
        )

    chart = get_chart(brand)
    valid_codes = set(chart.colors.keys()) if chart else set()

    img = Image.open(image_path).convert("RGB")
    # 预处理：放大 + 灰度 + autocontrast + 二值化，去除彩色背景干扰
    scale = 8
    from PIL import ImageOps
    img_gray = img.convert("L")
    img_gray = ImageOps.autocontrast(img_gray)
    img_large = img_gray.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)
    threshold = 150
    img_bw = img_large.point(lambda x: 0 if x < threshold else 255, mode="1")
    # OCR 配置：psm 6 = 假设是统一文本块，更适合表格/清单
    custom_config = r"--oem 3 --psm 6"
    text = pytesseract.image_to_string(img_bw, lang="chi_sim+eng", config=custom_config)

    items: List[OcrItem] = []

    # 正则：匹配 "D2 (349)" / "D2(349)" / "D2 349" 等多种格式
    pair_pattern = re.compile(r"([A-Za-z]\d{1,2})\s*\(?\s*(\d+)\s*\)?")

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # 一行中可能包含多个色号-用量对，全部提取
        found_pairs = pair_pattern.findall(line)
        if not found_pairs:
            # 回退：如果只找到色号没用量，也记录下来
            m = re.search(r"([A-Za-z]+\d{1,2})", line)
            if m:
                raw_code = m.group(1).upper()
                code = _normalize_mard_code(raw_code)
                is_valid = code in valid_codes
                items.append(OcrItem(
                    code=code,
                    quantity=None,
                    confidence=1.0 if is_valid else 0.5,
                    raw_text=line,
                ))
            continue

        for raw_code, qty_str in found_pairs:
            code = _normalize_mard_code(raw_code.upper())
            code = _correct_ocr_code(code, valid_codes)
            qty = int(qty_str)
            is_valid = code in valid_codes
            items.append(OcrItem(
                code=code,
                quantity=qty,
                confidence=1.0 if is_valid else 0.5,
                raw_text=line,
            ))

    # 合并同一色号的多行识别结果
    merged: dict = {}
    for item in items:
        if item.code not in merged:
            merged[item.code] = item
        else:
            existing = merged[item.code]
            if item.quantity and (existing.quantity is None or item.quantity > existing.quantity):
                existing.quantity = item.quantity
            existing.confidence = max(existing.confidence, item.confidence)
            existing.raw_text += " | " + item.raw_text

    result = AnalysisResult(brand=brand, mode="ocr", width=img.width, height=img.height)
    result.ocr_items = list(merged.values())
    return result


def analyze_image(
    image_path: Path,
    brand: str,
    mode: str = "auto",
    max_colors: int = 20,
    target_width: Optional[int] = None,
    target_height: Optional[int] = None,
) -> AnalysisResult:
    """
    分析拼豆图案图片，自动或手动选择 OCR / Pixel 模式。

    Args:
        image_path: 图片文件路径
        brand: 品牌名称
        mode: "auto" 自动检测, "ocr" 强制文字识别, "pixel" 强制像素匹配
        max_colors: 像素模式下最多识别主色数
        target_width: 目标网格宽度（像素模式）
        target_height: 目标网格高度（像素模式）
    """
    if mode == "auto":
        detected = detect_image_type(image_path)
        mode = detected

    if mode == "ocr":
        return _analyze_by_ocr(image_path, brand)
    else:
        return _analyze_by_pixels(image_path, brand, max_colors, target_width, target_height)
