#!/usr/bin/env python3
"""
数据迁移脚本：将旧的 JSON 数据导入 SQLite 数据库。

用法:
    python migrate_to_sqlite.py
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

from bead_matcher.db import init_db
from bead_matcher.dao.inventory_dao import InventoryDao
from bead_matcher.dao.pattern_dao import PatternDao
from bead_matcher.inventory import Inventory
from bead_matcher.pattern import Pattern


def migrate_inventory(data_dir: Path) -> None:
    inv_path = data_dir / "inventory.json"
    if not inv_path.exists():
        print("未找到 inventory.json，跳过库存迁移")
        return

    with open(inv_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    inv = Inventory.from_dict(data)
    dao = InventoryDao()
    dao.save_inventory(inv)
    print(f"✅ 已迁移库存: 品牌={inv.brand}, 色号数={len(inv.items)}, 总粒数={inv.total_count()}")


def migrate_patterns(data_dir: Path) -> None:
    patterns_path = data_dir / "patterns.json"
    if not patterns_path.exists():
        print("未找到 patterns.json，跳过图案库迁移")
        return

    with open(patterns_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    dao = PatternDao()
    count = 0
    for item in data.get("patterns", []):
        try:
            pattern = Pattern.from_dict(item)
            dao.save(pattern)
            count += 1
        except Exception as e:
            print(f"⚠️  跳过无效图案 {item.get('name', '?')}: {e}")

    print(f"✅ 已迁移 {count} 个图案")


def backup_old_files(data_dir: Path) -> None:
    backup_dir = data_dir / "backup" / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)

    for filename in ("inventory.json", "patterns.json"):
        src = data_dir / filename
        if src.exists():
            dst = backup_dir / filename
            shutil.copy2(src, dst)
            print(f"📦 已备份 {filename} -> {dst}")


def main():
    data_dir = Path(__file__).parent / "data"
    print(f"数据目录: {data_dir}")
    print("初始化 SQLite 数据库...")
    init_db()

    print("\n迁移库存...")
    migrate_inventory(data_dir)

    print("\n迁移图案库...")
    migrate_patterns(data_dir)

    print("\n备份旧文件...")
    backup_old_files(data_dir)

    print("\n🎉 迁移完成！")
    print(f"数据库位置: {data_dir / 'bead_matcher.db'}")


if __name__ == "__main__":
    main()
