"""图片转拼豆图案：将任意图片转换为带完整 grid 的 Pattern。"""

from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from .color_chart import get_chart
from .image_analyzer import _find_nearest_color, _hex_to_rgb, _rgb_distance
from .pattern import Pattern


def convert_image_to_pattern(
    image_path: Path,
    brand: str,
    target_width: int,
    target_height: int,
    name: str,
    source_image: Optional[str] = None,
) -> Pattern:
    """
    将图片转换为拼豆图案（完整 grid）。

    流程：
      1. 打开图片，缩放到 target_width x target_height（NEAREST 保持硬边缘）
      2. 每个像素匹配到品牌最近色号
      3. 生成 Pattern（含完整 grid + color_usage）

    Args:
        image_path: 图片文件路径
        brand: 品牌名称（如 Mard / Perler）
        target_width: 目标网格宽度（格子数）
        target_height: 目标网格高度（格子数）
        name: 图案名称
        source_image: 记录原始图片来源路径

    Returns:
        Pattern 对象，input_mode="pixel_convert"
    """
    chart = get_chart(brand)
    if not chart:
        from .color_chart import list_brands
        available = ", ".join(list_brands())
        raise ValueError(f"未知品牌: {brand}，可用: {available}")

    img = Image.open(image_path).convert("RGB")
    img = img.resize((target_width, target_height), Image.Resampling.NEAREST)

    grid: dict = {}
    for row in range(target_height):
        for col in range(target_width):
            r, g, b = img.getpixel((col, row))
            code, _name, _hex_color, _dist = _find_nearest_color(r, g, b, chart)
            grid[(col, row)] = code

    # 构造 Pattern：先空 grid，再通过 set_cell 同步 color_usage
    # 但批量 set_cell 太慢，直接构造再 rebuild
    pattern = Pattern(
        name=name,
        brand=brand,
        width=target_width,
        height=target_height,
        grid=grid,
        source_image=source_image or str(image_path),
        input_mode="pixel_convert",
    )
    return pattern


def suggest_grid_size(image_path: Path) -> Tuple[int, int]:
    """
    根据图片尺寸和常见拼豆网格比例，给出建议的网格尺寸。

    常见拼豆图案尺寸：48x48、64x64、96x96、58x58 等。
    策略：把图片长边缩放到最常见的 48~96 之间，短边等比。
    """
    with Image.open(image_path) as img:
        w, h = img.size
    long = max(w, h)

    # 常见拼豆网格长边
    candidates = [32, 48, 64, 80, 96, 128]
    # 找最接近的候选
    best = min(candidates, key=lambda x: abs(x - long / 10))  # 粗略估算：约 10px/格

    ratio = best / long
    target_w = max(1, round(w * ratio))
    target_h = max(1, round(h * ratio))
    return target_w, target_h


def postprocess_grid_colors(grid, color_usage, chart, max_colors=20, threshold=0.0):
    """颜色后处理：限制最大颜色数并合并相似颜色。

    Args:
        grid: 原始网格 {(col, row): code}
        color_usage: 色号用量统计
        chart: 品牌色卡
        max_colors: 最大保留颜色数（默认20）
        threshold: RGB 色差合并阈值（默认0，表示不合并）

    Returns:
        处理后的新 grid
    """
    if not grid:
        return grid

    unique_codes = list(color_usage.keys())
    if len(unique_codes) <= max_colors and threshold <= 0:
        return grid

    # 构建色号 RGB 映射
    code_rgb = {}
    for code in unique_codes:
        bead = chart.colors.get(code)
        if bead and bead.hex_color:
            code_rgb[code] = _hex_to_rgb(bead.hex_color)
        else:
            code_rgb[code] = (128, 128, 128)

    def dist(c1, c2):
        if c1 == c2:
            return float("inf")
        return _rgb_distance(code_rgb[c1], code_rgb[c2])

    # 按用量从少到多排序（用量少的优先被合并）
    sorted_codes = sorted(unique_codes, key=lambda c: color_usage.get(c, 0))

    merge_map = {}
    current_codes = set(unique_codes)

    for code in sorted_codes:
        if code not in current_codes:
            continue

        candidates = [(other, dist(code, other)) for other in current_codes if other != code]
        if not candidates:
            continue

        within_threshold = [(c, d) for c, d in candidates if d < threshold]

        if within_threshold:
            # threshold 内：合并到用量最多的（保留主流颜色）
            target = max(within_threshold, key=lambda x: color_usage.get(x[0], 0))[0]
        elif len(current_codes) > max_colors:
            # 超过 max_colors：强制合并到最近的色号
            target = min(candidates, key=lambda x: x[1])[0]
        else:
            continue

        merge_map[code] = target
        current_codes.remove(code)

    new_grid = {pos: merge_map.get(code, code) for pos, code in grid.items()}
    return new_grid
