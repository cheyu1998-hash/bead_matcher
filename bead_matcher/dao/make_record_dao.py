"""制作记录 DAO：拼豆制作历史的 SQLite 数据访问。"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from bead_matcher.db import get_connection, get_db_path


class MakeRecordDao:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or get_db_path()

    def _conn(self):
        return get_connection(self.db_path)

    def create(
        self,
        pattern_id: str,
        consumed: dict,
        status: str = "done",
        note: Optional[str] = None,
    ) -> int:
        """创建制作记录，返回记录 id。"""
        conn = self._conn()
        try:
            cur = conn.execute(
                """
                INSERT INTO make_records (pattern_id, made_at, consumed_json, status, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    pattern_id,
                    datetime.now().isoformat(),
                    json.dumps(consumed),
                    status,
                    note,
                ),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get(self, record_id: int) -> Optional[dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM make_records WHERE id = ?", (record_id,)
            ).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "pattern_id": row["pattern_id"],
                "made_at": row["made_at"],
                "consumed": json.loads(row["consumed_json"]),
                "status": row["status"],
                "note": row["note"],
            }
        finally:
            conn.close()

    def list_all(self, limit: int = 100) -> List[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM make_records ORDER BY made_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "pattern_id": r["pattern_id"],
                    "made_at": r["made_at"],
                    "consumed": json.loads(r["consumed_json"]),
                    "status": r["status"],
                    "note": r["note"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def list_by_pattern(self, pattern_id: str) -> List[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM make_records WHERE pattern_id = ? ORDER BY made_at DESC",
                (pattern_id,),
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "pattern_id": r["pattern_id"],
                    "made_at": r["made_at"],
                    "consumed": json.loads(r["consumed_json"]),
                    "status": r["status"],
                    "note": r["note"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def update_status(self, record_id: int, status: str) -> bool:
        conn = self._conn()
        try:
            cur = conn.execute(
                "UPDATE make_records SET status = ? WHERE id = ?",
                (status, record_id),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
