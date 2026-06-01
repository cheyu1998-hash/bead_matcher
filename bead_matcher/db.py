"""SQLite 数据库连接管理和 Schema 初始化。"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "bead_matcher.db"


SQL_SCHEMA = """
-- 品牌色卡
CREATE TABLE IF NOT EXISTS charts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    brand       TEXT NOT NULL UNIQUE,
    colors_json TEXT NOT NULL
);

-- 图案库
CREATE TABLE IF NOT EXISTS patterns (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    brand           TEXT NOT NULL,
    width           INTEGER NOT NULL,
    height          INTEGER NOT NULL,
    grid_json       TEXT NOT NULL,
    color_usage_json TEXT NOT NULL,
    source_image    TEXT,
    tags_json       TEXT DEFAULT '[]',
    input_mode      TEXT DEFAULT 'pixel_convert',
    status          TEXT DEFAULT 'pending',
    ip_name         TEXT,
    share_key       TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_patterns_brand ON patterns(brand);
CREATE INDEX IF NOT EXISTS idx_patterns_name  ON patterns(name);

-- IP / 来源标签库（独立管理，图案 ip_name 仍以 JSON 冗余存储）
CREATE TABLE IF NOT EXISTS ip_tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL
);

-- 当前库存（按品牌分库存）
CREATE TABLE IF NOT EXISTS inventory (
    brand       TEXT PRIMARY KEY,
    items_json  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- 库存快照（历史记录）
CREATE TABLE IF NOT EXISTS inventory_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_at TEXT NOT NULL,
    brand       TEXT NOT NULL,
    items_json  TEXT NOT NULL,
    trigger     TEXT,
    note        TEXT
);

-- 制作记录
CREATE TABLE IF NOT EXISTS make_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_id      TEXT NOT NULL REFERENCES patterns(id),
    made_at         TEXT NOT NULL,
    consumed_json   TEXT NOT NULL,
    status          TEXT DEFAULT 'done',
    note            TEXT
);

-- 库存事务流水（审计/撤销）
CREATE TABLE IF NOT EXISTS inventory_transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_at       TEXT NOT NULL,
    code        TEXT NOT NULL,
    delta       INTEGER NOT NULL,
    balance     INTEGER NOT NULL,
    tx_type     TEXT NOT NULL,
    ref_id      INTEGER,
    note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_tx_code ON inventory_transactions(code);
CREATE INDEX IF NOT EXISTS idx_tx_time ON inventory_transactions(tx_at);
"""


def get_db_path() -> Path:
    return DEFAULT_DB_PATH


def _migrate_inventory_table(conn: sqlite3.Connection) -> None:
    """将旧版单条库存表迁移为多品牌库存表（brand 为 PK）。"""
    cur = conn.execute("PRAGMA table_info(inventory)")
    cols = {row["name"] for row in cur.fetchall()}
    if not cols:
        return  # 表不存在，新 schema 已自动创建
    if "id" not in cols:
        return  # 已经是新结构

    # 旧表存在：重命名旧表，创建新表，迁移数据
    conn.execute("ALTER TABLE inventory RENAME TO inventory_old")
    conn.executescript("""
        CREATE TABLE inventory (
            brand       TEXT PRIMARY KEY,
            items_json  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );
    """)
    row = conn.execute("SELECT brand, items_json, updated_at FROM inventory_old WHERE id = 1").fetchone()
    if row:
        conn.execute(
            "INSERT INTO inventory (brand, items_json, updated_at) VALUES (?, ?, ?)",
            (row["brand"], row["items_json"], row["updated_at"]),
        )
    conn.execute("DROP TABLE inventory_old")
    conn.commit()


def _migrate_patterns_table(conn: sqlite3.Connection) -> None:
    """为旧版 patterns 表添加缺失列及索引（若不存在）。"""
    cur = conn.execute("PRAGMA table_info(patterns)")
    cols = {row["name"] for row in cur.fetchall()}
    if not cols:
        return
    if "status" not in cols:
        conn.execute("ALTER TABLE patterns ADD COLUMN status TEXT DEFAULT 'pending'")
        conn.commit()
    if "ip_name" not in cols:
        conn.execute("ALTER TABLE patterns ADD COLUMN ip_name TEXT")
        conn.commit()
    if "share_key" not in cols:
        conn.execute("ALTER TABLE patterns ADD COLUMN share_key TEXT")
        conn.commit()
    # 确保 share_key 索引存在
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_patterns_share_key ON patterns(share_key)"
    )
    conn.commit()


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """获取数据库连接，自动创建表。"""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SQL_SCHEMA)
    conn.commit()
    _migrate_inventory_table(conn)
    _migrate_patterns_table(conn)
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """初始化数据库：创建所有表和索引。"""
    conn = get_connection(db_path)
    try:
        conn.executescript(SQL_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _json_loads(text: str) -> Any:
    return json.loads(text)


def row_to_dict(row: sqlite3.Row) -> dict:
    """将 sqlite3.Row 转为普通字典。"""
    return {key: row[key] for key in row.keys()}
