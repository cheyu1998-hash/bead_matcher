"""图案 DAO：图案库的 SQLite 数据访问。"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from bead_matcher.db import get_connection, get_db_path
from bead_matcher.pattern import Pattern


def _pattern_to_row(p: Pattern) -> tuple:
    return (
        p.id,
        p.name,
        p.brand,
        p.width,
        p.height,
        json.dumps({f"{c},{r}": code for (c, r), code in p.grid.items()}),
        json.dumps(p.color_usage),
        p.source_image,
        json.dumps(p.tags),
        p.input_mode,
        p.status,
        json.dumps(p.ip_name),
        p.share_key,
        p.created_at,
        datetime.now().isoformat(),
    )


def _row_to_pattern(row) -> Pattern:
    grid = {}
    for key, code in json.loads(row["grid_json"]).items():
        c, r = key.split(",")
        grid[(int(c), int(r))] = code
    # 兼容旧数据：ip_name 可能是 JSON 数组字符串、普通字符串或 null
    raw_ip = row["ip_name"]
    if raw_ip and isinstance(raw_ip, str):
        if raw_ip.startswith("["):
            try:
                ip_name = [str(x) for x in json.loads(raw_ip) if x]
            except Exception:
                ip_name = [raw_ip] if raw_ip else []
        else:
            ip_name = [raw_ip]
    else:
        ip_name = []
    return Pattern(
        id=row["id"],
        name=row["name"],
        brand=row["brand"],
        width=row["width"],
        height=row["height"],
        grid=grid,
        color_usage=json.loads(row["color_usage_json"]),
        source_image=row["source_image"],
        tags=json.loads(row["tags_json"]),
        input_mode=row["input_mode"],
        status=row["status"],
        ip_name=ip_name,
        share_key=row["share_key"] if row["share_key"] else "",
        created_at=row["created_at"],
    )


class PatternDao:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or get_db_path()

    def _conn(self):
        return get_connection(self.db_path)

    def save(self, pattern: Pattern) -> None:
        """插入或更新图案（UPSERT）。"""
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO patterns (id, name, brand, width, height, grid_json,
                    color_usage_json, source_image, tags_json, input_mode, status, ip_name, share_key, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    brand=excluded.brand,
                    width=excluded.width,
                    height=excluded.height,
                    grid_json=excluded.grid_json,
                    color_usage_json=excluded.color_usage_json,
                    source_image=excluded.source_image,
                    tags_json=excluded.tags_json,
                    input_mode=excluded.input_mode,
                    status=excluded.status,
                    ip_name=excluded.ip_name,
                    share_key=excluded.share_key,
                    updated_at=excluded.updated_at
                """,
                _pattern_to_row(pattern),
            )
            conn.commit()
        finally:
            conn.close()

    def get_by_id(self, pattern_id: str) -> Optional[Pattern]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM patterns WHERE id = ?", (pattern_id,)
            ).fetchone()
            return _row_to_pattern(row) if row else None
        finally:
            conn.close()

    def get_by_name(self, name: str) -> Optional[Pattern]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM patterns WHERE name = ?", (name,)
            ).fetchone()
            return _row_to_pattern(row) if row else None
        finally:
            conn.close()

    def list_all(self) -> List[Pattern]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM patterns ORDER BY name"
            ).fetchall()
            return [_row_to_pattern(r) for r in rows]
        finally:
            conn.close()

    def list_by_brand(self, brand: str) -> List[Pattern]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM patterns WHERE brand = ? ORDER BY name",
                (brand,),
            ).fetchall()
            return [_row_to_pattern(r) for r in rows]
        finally:
            conn.close()

    def remove(self, pattern_id: str) -> bool:
        conn = self._conn()
        try:
            cur = conn.execute(
                "DELETE FROM patterns WHERE id = ?", (pattern_id,)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def remove_by_name(self, name: str) -> bool:
        conn = self._conn()
        try:
            cur = conn.execute(
                "DELETE FROM patterns WHERE name = ?", (name,)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def find_matching(
        self, inventory_quantities: dict
    ) -> List[Pattern]:
        """返回库存能完全覆盖的所有图案。"""
        results = []
        for p in self.list_all():
            if p.can_make_with_inventory(inventory_quantities):
                results.append(p)
        return results

    def find_partially_matching(
        self, inventory_quantities: dict
    ) -> List[tuple]:
        """返回所有图案及缺口，按缺口总量从小到大排序。"""
        results = []
        for p in self.list_all():
            shortage = p.estimate_inventory_shortage(inventory_quantities)
            results.append((p, shortage))
        results.sort(key=lambda x: sum(x[1].values()))
        return results

    # ---------- IP 标签管理 ----------

    def list_ip_tags(self) -> List[str]:
        """返回所有已注册的 IP / 来源标签（按字母序）。"""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT name FROM ip_tags ORDER BY name"
            ).fetchall()
            return [r["name"] for r in rows]
        finally:
            conn.close()

    def add_ip_tag(self, name: str) -> bool:
        """注册新标签，重复返回 False。"""
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO ip_tags (name, created_at) VALUES (?, ?)",
                (name.strip(), datetime.now().isoformat()),
            )
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def remove_ip_tag(self, name: str) -> bool:
        """删除标签。"""
        conn = self._conn()
        try:
            cur = conn.execute("DELETE FROM ip_tags WHERE name = ?", (name.strip(),))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
