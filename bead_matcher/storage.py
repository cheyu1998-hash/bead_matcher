"""库存持久化：SQLite DAO 封装，保持 API 向后兼容。"""

from pathlib import Path
from typing import Optional

from bead_matcher.dao.inventory_dao import InventoryDao
from bead_matcher.db import DEFAULT_DB_PATH, init_db
from bead_matcher.inventory import Inventory

# 模块导入时自动初始化数据库（幂等）
init_db()

# 保留旧常量以兼容外部引用
DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_INVENTORY_FILE = DEFAULT_DATA_DIR / "inventory.json"


def _resolve_db_path(filepath: Optional[Path]) -> Optional[Path]:
    if filepath and str(filepath).endswith(".db"):
        return filepath
    return None


def save_inventory(inventory: Inventory, filepath: Optional[Path] = None) -> Path:
    """保存库存到 SQLite（filepath 传入 .db 路径时用作数据库位置）。"""
    db_path = _resolve_db_path(filepath)
    dao = InventoryDao(db_path=db_path)
    dao.save_inventory(inventory)
    return db_path or DEFAULT_DB_PATH


def load_inventory(filepath: Optional[Path] = None, brand: str = "Mard") -> Optional[Inventory]:
    """从 SQLite 加载指定品牌的库存（filepath 传入 .db 路径时用作数据库位置）。"""
    db_path = _resolve_db_path(filepath)
    dao = InventoryDao(db_path=db_path)
    return dao.load_inventory(brand)


def inventory_exists(filepath: Optional[Path] = None, brand: str = "Mard") -> bool:
    """检查指定品牌库存是否存在（filepath 传入 .db 路径时用作数据库位置）。"""
    db_path = _resolve_db_path(filepath)
    dao = InventoryDao(db_path=db_path)
    return dao.inventory_exists(brand)
