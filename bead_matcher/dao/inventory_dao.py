"""库存 DAO：当前库存、快照、事务流水的 SQLite 数据访问。"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from bead_matcher.db import get_connection, get_db_path
from bead_matcher.inventory import Inventory


class InventoryDao:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or get_db_path()

    def _conn(self):
        return get_connection(self.db_path)

    # ---------- 当前库存 ----------

    def save_inventory(self, inv: Inventory) -> None:
        """保存当前库存（按品牌 UPSERT）。"""
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO inventory (brand, items_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(brand) DO UPDATE SET
                    items_json=excluded.items_json,
                    updated_at=excluded.updated_at
                """,
                (
                    inv.brand,
                    json.dumps({code: item.quantity for code, item in inv.items.items()}),
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def load_inventory(self, brand: str = "Mard") -> Optional[Inventory]:
        """加载指定品牌的库存。"""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM inventory WHERE brand = ?", (brand,)
            ).fetchone()
            if not row:
                return None
            items = json.loads(row["items_json"])
            inv = Inventory(brand=row["brand"])
            for code, qty in items.items():
                inv.set(code, qty)
            return inv
        finally:
            conn.close()

    def inventory_exists(self, brand: str = "Mard") -> bool:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT 1 FROM inventory WHERE brand = ?", (brand,)
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def list_inventory_brands(self) -> List[str]:
        """返回所有已创建库存的品牌列表。"""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT brand FROM inventory ORDER BY brand"
            ).fetchall()
            return [r["brand"] for r in rows]
        finally:
            conn.close()

    # ---------- 库存快照 ----------

    def create_snapshot(
        self, inv: Inventory, trigger: str = "manual", note: Optional[str] = None
    ) -> int:
        """创建库存快照，返回快照 id。"""
        conn = self._conn()
        try:
            cur = conn.execute(
                """
                INSERT INTO inventory_snapshots (snapshot_at, brand, items_json, trigger, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(),
                    inv.brand,
                    json.dumps({code: item.quantity for code, item in inv.items.items()}),
                    trigger,
                    note,
                ),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def list_snapshots(self, limit: int = 50) -> List[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """
                SELECT * FROM inventory_snapshots
                ORDER BY snapshot_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "snapshot_at": r["snapshot_at"],
                    "brand": r["brand"],
                    "items": json.loads(r["items_json"]),
                    "trigger": r["trigger"],
                    "note": r["note"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def get_snapshot(self, snapshot_id: int) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM inventory_snapshots WHERE id = ?",
                (snapshot_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "snapshot_at": row["snapshot_at"],
                "brand": row["brand"],
                "items": json.loads(row["items_json"]),
                "trigger": row["trigger"],
                "note": row["note"],
            }
        finally:
            conn.close()

    # ---------- 事务流水 ----------

    def add_transaction(
        self,
        code: str,
        delta: int,
        balance: int,
        tx_type: str,
        ref_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> int:
        """记录一条库存事务，返回事务 id。"""
        conn = self._conn()
        try:
            cur = conn.execute(
                """
                INSERT INTO inventory_transactions (tx_at, code, delta, balance, tx_type, ref_id, note)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(),
                    code,
                    delta,
                    balance,
                    tx_type,
                    ref_id,
                    note,
                ),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def list_transactions(
        self,
        code: Optional[str] = None,
        tx_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM inventory_transactions WHERE 1=1"
            params: List = []
            if code:
                sql += " AND code = ?"
                params.append(code)
            if tx_type:
                sql += " AND tx_type = ?"
                params.append(tx_type)
            sql += " ORDER BY tx_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return [
                {
                    "id": r["id"],
                    "tx_at": r["tx_at"],
                    "code": r["code"],
                    "delta": r["delta"],
                    "balance": r["balance"],
                    "tx_type": r["tx_type"],
                    "ref_id": r["ref_id"],
                    "note": r["note"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    # ---------- 统计查询 ----------

    def get_usage_stats(self, days: int = 30) -> Dict[str, int]:
        """返回最近 N 天内各色号的总消耗量（负 delta 汇总）。"""
        conn = self._conn()
        try:
            from datetime import timedelta

            since = (datetime.now() - timedelta(days=days)).isoformat()
            rows = conn.execute(
                """
                SELECT code, SUM(delta) as total_delta
                FROM inventory_transactions
                WHERE tx_at > ? AND delta < 0
                GROUP BY code
                ORDER BY total_delta ASC
                """,
                (since,),
            ).fetchall()
            return {r["code"]: abs(r["total_delta"]) for r in rows}
        finally:
            conn.close()
