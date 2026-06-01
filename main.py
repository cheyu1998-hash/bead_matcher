#!/usr/bin/env python3
"""
Bead Matcher - 拼豆库存反向匹配工具

支持两种运行方式：
1. 命令行模式: python main.py init Mard
2. 交互菜单模式: 双击运行（无参数）
"""

import os
import sys
from pathlib import Path


def _pause():
    input("\n按回车键返回菜单...")


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def interactive_menu():
    from bead_matcher.color_chart import get_chart
    from bead_matcher.image_analyzer import analyze_image
    from bead_matcher.inventory import Inventory
    from bead_matcher.storage import load_inventory, save_inventory

    while True:
        _clear()
        print("=" * 42)
        print("    Bead Matcher 拼豆库存管理")
        print("=" * 42)
        print()
        print("  [库存管理]")
        print("    1. 初始化库存")
        print("    2. 添加色号")
        print("    3. 设置色号")
        print("    4. 消耗库存")
        print("    5. 查看当前库存")
        print("    6. 清空库存")
        print()
        print("  [工具]")
        print("    7. 查看色卡")
        print("    8. 分析图片色号")
        print()
        print("  [图案]")
        print("    9. 图片转拼豆图案")
        print()
        print("    0. 退出")
        print("-" * 42)

        choice = input("请选择: ").strip()

        if choice == "1":
            brand = "Mard"
            chart = get_chart(brand)
            inv = Inventory(brand=brand)
            save_inventory(inv)
            print(f"\n已初始化 {brand} 品牌库存（内置色卡 {len(chart.colors)} 色）")
            print("数据保存在 data/bead_matcher.db")
            _pause()

        elif choice == "2":
            inv = load_inventory()
            if not inv:
                print("\n尚未初始化库存，请先选择【1. 初始化库存】")
                _pause()
                continue
            code = input("色号: ").strip()
            qty_str = input("数量: ").strip()
            try:
                qty = int(qty_str)
                inv.add(code, qty)
                save_inventory(inv)
                print(f"\n已添加：色号 {code} +{qty} 粒，当前 {inv.get_quantity(code)} 粒")
            except ValueError as e:
                print(f"\n错误: {e}")
            _pause()

        elif choice == "3":
            inv = load_inventory()
            if not inv:
                print("\n尚未初始化库存，请先选择【1. 初始化库存】")
                _pause()
                continue
            code = input("色号: ").strip()
            qty_str = input("数量（输入0删除）: ").strip()
            try:
                qty = int(qty_str)
                inv.set(code, qty)
                save_inventory(inv)
                action = "设置" if qty > 0 else "清除"
                print(f"\n已{action}：色号 {code} = {qty} 粒")
            except ValueError as e:
                print(f"\n错误: {e}")
            _pause()

        elif choice == "4":
            inv = load_inventory()
            if not inv:
                print("\n尚未初始化库存，请先选择【1. 初始化库存】")
                _pause()
                continue
            code = input("色号: ").strip()
            qty_str = input("消耗数量: ").strip()
            try:
                qty = int(qty_str)
                inv.remove(code, qty)
                save_inventory(inv)
                remaining = inv.get_quantity(code)
                print(f"\n已消耗：色号 {code} -{qty} 粒，剩余 {remaining} 粒")
            except (ValueError, KeyError) as e:
                print(f"\n错误: {e}")
            _pause()

        elif choice == "5":
            inv = load_inventory()
            if not inv:
                print("\n暂无库存数据，请先初始化")
                _pause()
                continue
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
            _pause()

        elif choice == "6":
            confirm = input("\n确定要清空所有库存吗？(yes/no): ").strip().lower()
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
            _pause()

        elif choice == "7":
            brand = "Mard"
            chart = get_chart(brand)
            print(f"\n{brand} 色卡 ({len(chart.colors)} 色)\n")
            print(f"{'色号':<6} {'名称':<16} {'HEX':<8}")
            print("-" * 35)
            for code in chart.list_codes():
                c = chart.get(code)
                print(f"{c.code:<6} {c.name:<16} {c.hex_color or '-':<8}")
            _pause()

        elif choice == "8":
            path_str = input("\n图片路径: ").strip()
            if not path_str:
                continue
            image_path = Path(path_str)
            if not image_path.exists():
                print(f"错误：找不到图片 {image_path}")
                _pause()
                continue

            brand = "Mard"

            mode = input("模式 [auto/ocr/pixel]（默认 auto）: ").strip() or "auto"
            if mode not in ("auto", "ocr", "pixel"):
                print("模式必须是 auto/ocr/pixel 之一")
                _pause()
                continue

            max_colors = 20
            if mode in ("auto", "pixel"):
                colors_str = input("最多识别颜色数（默认 20）: ").strip()
                if colors_str:
                    max_colors = int(colors_str)

            try:
                result = analyze_image(image_path, brand, mode, max_colors)
                print(f"\n图片: {image_path}")
                print(f"品牌: {result.brand}")
                print(f"处理模式: {result.mode.upper()}")

                if result.mode == "ocr":
                    print(f"\n识别到 {result.color_count} 个色号条目\n")
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
                else:
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

                # 库存核对
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
            except Exception as e:
                print(f"\n分析失败: {e}")
            _pause()

        elif choice == "9":
            path_str = input("\n图片路径: ").strip()
            if not path_str:
                continue
            image_path = Path(path_str)
            if not image_path.exists():
                print(f"错误：找不到图片 {image_path}")
                _pause()
                continue

            brand = "Mard"

            name = input("图案名称: ").strip()
            if not name:
                print("图案名称不能为空")
                _pause()
                continue

            w_str = input("网格宽度（留空自动建议）: ").strip()
            h_str = input("网格高度（留空自动建议）: ").strip()

            from bead_matcher.pattern_converter import suggest_grid_size, convert_image_to_pattern
            from bead_matcher.pattern_storage import PatternLibrary

            target_w = int(w_str) if w_str else None
            target_h = int(h_str) if h_str else None

            if target_w is None or target_h is None:
                suggested_w, suggested_h = suggest_grid_size(image_path)
                if target_w is None:
                    target_w = suggested_w
                if target_h is None:
                    target_h = suggested_h
                print(f"\n自动建议网格: {target_w} x {target_h}")
                confirm = input("按回车确认，或输入 no 取消: ").strip().lower()
                if confirm == "no":
                    _pause()
                    continue

            try:
                pattern = convert_image_to_pattern(
                    image_path=image_path,
                    brand=brand,
                    target_width=target_w,
                    target_height=target_h,
                    name=name,
                    source_image=str(image_path),
                )
                lib = PatternLibrary()
                lib.add(pattern)
                print(f"\n已保存图案: {pattern.name}")
                print(f"品牌: {pattern.brand} | 尺寸: {pattern.width}x{pattern.height}")
                print(f"总粒数: {pattern.total_beads()} | 色号数: {len(pattern.color_usage)}")
            except Exception as e:
                print(f"\n转换失败: {e}")
            _pause()

        elif choice == "0":
            print("\n再见！")
            break

        else:
            print("\n无效选项，请重新选择")
            _pause()


if __name__ == "__main__":
    try:
        # Windows 双击运行时修复编码，防止中文乱码/闪退
        if sys.platform == "win32":
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

        # 有命令行参数时走 CLI 模式，无参数时进入交互菜单
        if len(sys.argv) > 1:
            from bead_matcher.cli import main
            main()
        else:
            interactive_menu()
    except Exception as e:
        print(f"\n程序出错: {e}")
        import traceback
        traceback.print_exc()
        input("\n按回车键关闭窗口...")
