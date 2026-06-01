"""图案库持久化：SQLite DAO 封装，保持 API 向后兼容。"""

from pathlib import Path
from typing import Dict, List, Optional

from bead_matcher.dao.pattern_dao import PatternDao
from bead_matcher.db import init_db
from bead_matcher.pattern import Pattern

# 模块导入时自动初始化数据库（幂等）
init_db()

# 保留旧常量以兼容外部引用
DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_PATTERN_FILE = DEFAULT_DATA_DIR / "patterns.json"


class PatternLibrary:
    """图案库，管理所有已保存的图案。"""

    def __init__(self, filepath: Optional[Path] = None) -> None:
        db_path = filepath if filepath and str(filepath).endswith(".db") else None
        self._dao = PatternDao(db_path=db_path)

    def _load(self) -> None:
        """已废弃：SQLite 架构下无需手动加载。"""
        pass

    def save(self) -> None:
        """已废弃：SQLite 架构下每次操作已实时写入。"""
        pass

    def add(self, pattern: Pattern) -> None:
        """添加图案，同名不覆盖（因为主键是 id）。
        如果希望按名称去重，需先 remove_by_name 再 add。"""
        self._dao.save(pattern)

    def create_manual(
        self,
        name: str,
        color_usage: dict,
        brand: str = "Mard",
        width: int = 0,
        height: int = 0,
        ip_name: Optional[List[str]] = None,
        status: str = "pending",
        tags: list = None,
    ) -> Pattern:
        """创建手动录入的图案（无需网格，只需色号用量）。"""
        pattern = Pattern(
            name=name,
            brand=brand,
            width=width,
            height=height,
            grid={},
            color_usage=dict(color_usage),
            input_mode="manual_entry",
            status=status,
            ip_name=ip_name,
            tags=tags or [],
        )
        self._dao.save(pattern)
        return pattern

    def get(self, name: str) -> Optional[Pattern]:
        """按名称获取图案（返回第一个匹配）。"""
        return self._dao.get_by_name(name)

    def get_by_id(self, pattern_id: str) -> Optional[Pattern]:
        """按 id 获取图案。"""
        return self._dao.get_by_id(pattern_id)

    def remove(self, name: str) -> bool:
        """按名称删除图案（删除第一个匹配）。"""
        return self._dao.remove_by_name(name)

    def remove_by_id(self, pattern_id: str) -> bool:
        """按 id 删除图案。"""
        return self._dao.remove(pattern_id)

    def list_all(self) -> List[Pattern]:
        """列出所有图案。"""
        return self._dao.list_all()

    def list_names(self) -> List[str]:
        """列出所有图案名称（按字母序）。"""
        return [p.name for p in self._dao.list_all()]

    def list_by_brand(self, brand: str) -> List[Pattern]:
        """按品牌筛选图案。"""
        return self._dao.list_by_brand(brand)

    def find_matching_patterns(
        self, inventory_quantities: Dict[str, int]
    ) -> List[Pattern]:
        """反向匹配：找出库存能完全覆盖的图案。"""
        return self._dao.find_matching(inventory_quantities)

    def find_partially_matching_patterns(
        self, inventory_quantities: Dict[str, int]
    ) -> List[tuple]:
        """部分匹配：找出所有图案，按缺口数量排序。"""
        return self._dao.find_partially_matching(inventory_quantities)

    def __len__(self) -> int:
        return len(self._dao.list_all())

    def __repr__(self) -> str:
        return f"PatternLibrary(patterns={len(self)})"

    # ---------- IP 标签管理 ----------

    def list_ip_tags(self) -> List[str]:
        """返回所有已注册的 IP / 来源标签。"""
        return self._dao.list_ip_tags()

    def add_ip_tag(self, name: str) -> bool:
        """注册新标签。"""
        return self._dao.add_ip_tag(name)

    def remove_ip_tag(self, name: str) -> bool:
        """删除标签。"""
        return self._dao.remove_ip_tag(name)
