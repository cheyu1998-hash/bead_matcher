import argparse
import sys
from pathlib import Path

from .color_chart import get_chart
from .image_analyzer import analyze_image
from .inventory import Inventory
from .pattern_converter import convert_image_to_pattern, suggest_grid_size
from .pattern_storage import PatternLibrary
from .storage import load_inventory, save_inventory


def print_help():
    print("""
拼豆库存管理工具

用法:
  python -m bead_matcher.cli init           初始化库存（固定 Mard）
  python -m bead_matcher.cli add <色号> <数量>  添加库存
  python -m bead_matcher.cli set <色号> <数量>  设置库存
  python -m bead_matcher.cli remove <色号> <数量>  消耗库存
  python -m bead_matcher.cli list              查看当前库存
  python -m bead_matcher.cli chart             查看色卡
  python -m bead_matcher.cli analyze <图片> [--mode auto|ocr|pixel]
                          分析图片所需色号
  python -m bead_matcher.cli clear             清空库存
  python -m bead_matcher.cli convert <图片> <名称> [--brand Mard] [--width N] [--height N]
                          图片转拼豆图案并保存
""")


def cmd_init(_args):
    brand = "Mard"
    chart = get_chart(brand)
    inv = Inventory(brand=brand)
    save_inventory(inv)
    print(f"已初始化 {brand} 品牌库存（内置色卡 {len(chart.colors)} 色）")
    print("数据保存在 data/bead_matcher.db")


def cmd_add(args):
    inv = load_inventory()
    if not inv:
        print("错误：尚未初始化库存，请先运行 init")
        sys.exit(1)
    code, qty = args[0], int(args[1])
    inv.add(code, qty)
    save_inventory(inv)
    print(f"已添加：色号 {code} +{qty} 粒，当前 {inv.get_quantity(code)} 粒")


def cmd_set(args):
    inv = load_inventory()
    if not inv:
        print("错误：尚未初始化库存，请先运行 init")
        sys.exit(1)
    code, qty = args[0], int(args[1])
    inv.set(code, qty)
    save_inventory(inv)
    action = "设置" if qty > 0 else "清除"
    print(f"已{action}：色号 {code} = {qty} 粒")


def cmd_remove(args):
    inv = load_inventory()
    if not inv:
        print("错误：尚未初始化库存，请先运行 init")
        sys.exit(1)
    code, qty = args[0], int(args[1])
    inv.remove(code, qty)
    save_inventory(inv)
    remaining = inv.get_quantity(code)
    print(f"已消耗：色号 {code} -{qty} 粒，剩余 {remaining} 粒")


def cmd_list(_args):
    inv = load_inventory()
    if not inv:
        print("暂无库存数据，请先运行 init")
        return
    chart = get_chart(inv.brand)
    print(f"\n品牌: {inv.brand}")
    print(f"总色号数: {len(inv.items)} | 总粒数: {inv.total_count()}\n")
    print(f"{'色号':<6} {'名称':<16} {'数量':>8}")
    print("-" * 35)
    for code in inv.list_codes():
        color = chart.get(code) if chart else None
        name = color.name if color else "未知色号"
        qty = inv.get_quantity(code)
        print(f"{code:<6} {name:<16} {qty:>8}")

    invalid = inv.validate_against_chart()
    if invalid:
        print(f"\n⚠️  以下色号不在当前色卡中: {', '.join(invalid)}")


def cmd_chart(_args):
    brand = "Mard"
    chart = get_chart(brand)
    print(f"\n{brand} 色卡 ({len(chart.colors)} 色)\n")
    print(f"{'色号':<6} {'名称':<16} {'HEX':<8}")
    print("-" * 35)
    for code in chart.list_codes():
        c = chart.get(code)
        print(f"{c.code:<6} {c.name:<16} {c.hex_color or '-':<8}")


def cmd_analyze(args):
    if not args:
        print("用法: python main.py analyze <图片路径> [--mode auto|ocr|pixel] [--brand Mard] [--colors 20]")
        sys.exit(1)

    image_path = Path(args[0])
    if not image_path.exists():
        print(f"错误：找不到图片 {image_path}")
        sys.exit(1)

    brand = "Mard"
    mode = "auto"
    max_colors = 20
    target_w = None
    target_h = None

    i = 1
    while i < len(args):
        if args[i] == "--brand" and i + 1 < len(args):
            brand = args[i + 1]
            i += 2
        elif args[i] == "--mode" and i + 1 < len(args):
            mode = args[i + 1]
            i += 2
        elif args[i] == "--colors" and i + 1 < len(args):
            max_colors = int(args[i + 1])
            i += 2
        elif args[i] == "--width" and i + 1 < len(args):
            target_w = int(args[i + 1])
            i += 2
        elif args[i] == "--height" and i + 1 < len(args):
            target_h = int(args[i + 1])
            i += 2
        else:
            i += 1

    if mode not in ("auto", "ocr", "pixel"):
        print("错误：--mode 必须是 auto / ocr / pixel 之一")
        sys.exit(1)

    try:
        result = analyze_image(image_path, brand, mode, max_colors, target_w, target_h)
    except Exception as e:
        print(f"分析失败: {e}")
        sys.exit(1)

    print(f"\n图片: {image_path}")
    print(f"品牌: {result.brand}")
    print(f"处理模式: {result.mode.upper()}")

    if result.mode == "ocr":
        _print_ocr_result(result)
    else:
        _print_pixel_result(result)

    # 库存核对（两种模式通用）
    inv = load_inventory()
    if inv and inv.brand == brand:
        print("\n库存核对:")
        if result.mode == "ocr":
            for item in result.ocr_items:
                need = item.quantity or 0
                have = inv.get_quantity(item.code)
                status = "OK" if have >= need else f"缺 {need - have}"
                print(f"  {item.code}: 需 {need:>5} / 有 {have:>5}  [{status}]")
        else:
            for item in result.pixel_items:
                need = item.pixel_count
                have = inv.get_quantity(item.code)
                status = "OK" if have >= need else f"缺 {need - have}"
                print(f"  {item.code}: 需 {need:>5} / 有 {have:>5}  [{status}]")


def _print_ocr_result(result):
    print(f"识别到 {result.color_count} 个色号条目\n")
    print(f"{'色号':<6} {'用量':>8} {'置信度':>8} {'原始文字'}")
    print("-" * 60)

    low_confidence = []
    for item in result.ocr_items:
        conf_str = f"{item.confidence * 100:.0f}%"
        flag = ""
        if item.confidence < 1.0:
            flag = " ⚠️"
            low_confidence.append(item)
        qty_str = str(item.quantity) if item.quantity else "-"
        print(f"{item.code:<6} {qty_str:>8} {conf_str:>8}  {item.raw_text[:30]}{flag}")

    total_qty = sum(item.quantity or 0 for item in result.ocr_items)
    print(f"\n预计总粒数: {total_qty}")

    if low_confidence:
        print(f"\n⚠️  低置信度条目（建议人工核对）:")
        for item in low_confidence:
            print(f"   - {item.code} (置信度 {item.confidence * 100:.0f}%) | {item.raw_text}")


def _print_pixel_result(result):
    print(f"尺寸: {result.width} x {result.height} 像素")
    print(f"识别到 {result.color_count} 种色号\n")
    print(f"{'色号':<6} {'名称':<16} {'用量':>8} {'占比':>6} {'色差':>6}")
    print("-" * 55)

    total = result.total_pixels
    for item in result.pixel_items:
        pct = item.pixel_count / total * 100 if total else 0
        print(f"{item.code:<6} {item.name:<16} {item.pixel_count:>8} {pct:>5.1f}% {item.distance:>6.1f}")

    print(f"\n预计总粒数: {total}")
    codes_str = ", ".join(item.code for item in result.pixel_items)
    print(f"所需色号列表: {codes_str}")


def cmd_clear(_args):
    confirm = input("确定要清空所有库存吗？(yes/no): ").strip().lower()
    if confirm == "yes":
        inv = load_inventory()
        if inv:
            inv.items.clear()
            save_inventory(inv)
            print("库存已清空")
        else:
            print("没有库存可清空")
    else:
        print("操作已取消")


def cmd_convert(args):
    if len(args) < 2:
        print("用法: python main.py convert <图片路径> <图案名称> [--brand Mard] [--width N] [--height N]")
        sys.exit(1)

    image_path = Path(args[0])
    name = args[1]
    if not image_path.exists():
        print(f"错误：找不到图片 {image_path}")
        sys.exit(1)

    brand = "Mard"
    target_w = None
    target_h = None

    i = 2
    while i < len(args):
        if args[i] == "--brand" and i + 1 < len(args):
            brand = args[i + 1]
            i += 2
        elif args[i] == "--width" and i + 1 < len(args):
            target_w = int(args[i + 1])
            i += 2
        elif args[i] == "--height" and i + 1 < len(args):
            target_h = int(args[i + 1])
            i += 2
        else:
            i += 1

    if target_w is None or target_h is None:
        suggested_w, suggested_h = suggest_grid_size(image_path)
        if target_w is None:
            target_w = suggested_w
        if target_h is None:
            target_h = suggested_h
        print(f"未指定尺寸，自动建议网格: {target_w} x {target_h}")

    try:
        pattern = convert_image_to_pattern(
            image_path=image_path,
            brand=brand,
            target_width=target_w,
            target_height=target_h,
            name=name,
            source_image=str(image_path),
        )
    except Exception as e:
        print(f"转换失败: {e}")
        sys.exit(1)

    lib = PatternLibrary()
    lib.add(pattern)

    print(f"\n已保存图案: {pattern.name}")
    print(f"品牌: {pattern.brand}")
    print(f"尺寸: {pattern.width} x {pattern.height}")
    print(f"总粒数: {pattern.total_beads()}")
    print(f"所需色号: {', '.join(pattern.unique_colors())}")
    print(f"输入模式: {pattern.input_mode}")


def main():
    parser = argparse.ArgumentParser(description="拼豆库存管理工具")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="初始化库存")
    sub.add_parser("add", help="添加库存")
    sub.add_parser("set", help="设置库存")
    sub.add_parser("remove", help="消耗库存")
    sub.add_parser("list", help="查看库存")
    sub.add_parser("chart", help="查看色卡")
    sub.add_parser("analyze", help="分析图片色号")
    sub.add_parser("convert", help="图片转拼豆图案")
    sub.add_parser("clear", help="清空库存")

    args, remaining = parser.parse_known_args()

    if not args.command:
        print_help()
        sys.exit(0)

    commands = {
        "init": cmd_init,
        "add": cmd_add,
        "set": cmd_set,
        "remove": cmd_remove,
        "list": cmd_list,
        "chart": cmd_chart,
        "analyze": cmd_analyze,
        "convert": cmd_convert,
        "clear": cmd_clear,
    }

    handler = commands.get(args.command)
    if handler:
        handler(remaining)
    else:
        print_help()


if __name__ == "__main__":
    main()
