"""图案数据模型：定义拼豆图案的结构与操作。"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple


def _new_id() -> str:
    return uuid.uuid4().hex


def _parse_ip_name(raw) -> List[str]:
    """兼容旧数据：ip_name 可能是字符串、列表或 null。"""
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    if isinstance(raw, str):
        if raw.startswith("["):
            try:
                import json
                return [str(x) for x in json.loads(raw) if x]
            except Exception:
                pass
        return [raw] if raw else []
    return []


@dataclass
class Pattern:
    """拼豆图案

    Attributes:
        id: UUID 主键
        name: 图案名称
        brand: 品牌（如 Mard / Perler）
        width: 网格宽度（格子数）
        height: 网格高度（格子数）
        grid: 二维格子映射，key 为 (col, row)，value 为色号
        color_usage: 色号用量统计，code -> count（冗余存储，便于查询）
        source_image: 原始图片来源路径
        created_at: 创建时间 ISO 格式
        tags: 标签列表，便于分类检索
    """

    id: str = field(default_factory=_new_id)
    name: str = ""
    brand: str = ""
    width: int = 0
    height: int = 0
    grid: Dict[Tuple[int, int], str] = field(default_factory=dict)
    color_usage: Dict[str, int] = field(default_factory=dict)
    source_image: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)
    input_mode: str = "pixel_convert"  # pixel_convert | chart_import | manual_entry
    status: str = "pending"  # pending | done
    ip_name: List[str] = field(default_factory=list)  # IP/来源标签，如 ["Pokemon", "迪士尼"]
    share_key: str = ""  # 分享 key，格式: user_key + pattern_id

    def __post_init__(self):
        if self.grid and (self.width <= 0 or self.height <= 0):
            raise ValueError("图案有网格数据时宽高必须大于 0")
        if self.grid:
            self._rebuild_usage()

    def _rebuild_usage(self) -> None:
        """根据 grid 重新计算 color_usage"""
        usage: Dict[str, int] = {}
        for code in self.grid.values():
            usage[code] = usage.get(code, 0) + 1
        self.color_usage = usage

    def get_cell(self, col: int, row: int) -> Optional[str]:
        """获取指定格子的色号"""
        return self.grid.get((col, row))

    def set_cell(self, col: int, row: int, code: str) -> None:
        """设置指定格子的色号"""
        if not (0 <= col < self.width and 0 <= row < self.height):
            raise ValueError(f"坐标 ({col}, {row}) 超出范围 {self.width}x{self.height}")
        old = self.grid.get((col, row))
        self.grid[(col, row)] = code
        self.color_usage[code] = self.color_usage.get(code, 0) + 1
        if old is not None:
            self.color_usage[old] -= 1
            if self.color_usage[old] <= 0:
                del self.color_usage[old]

    def total_beads(self) -> int:
        """总粒数"""
        return sum(self.color_usage.values())

    def unique_colors(self) -> List[str]:
        """所需色号列表（去重排序）"""
        return sorted(self.color_usage.keys())

    def estimate_inventory_shortage(self, inventory_quantities: Dict[str, int]) -> Dict[str, int]:
        """根据库存数量计算缺口，返回 code -> 缺少数量"""
        shortage = {}
        for code, need in self.color_usage.items():
            have = inventory_quantities.get(code, 0)
            if have < need:
                shortage[code] = need - have
        return shortage

    def can_make_with_inventory(self, inventory_quantities: Dict[str, int]) -> bool:
        """判断当前库存是否足够制作该图案"""
        for code, need in self.color_usage.items():
            if inventory_quantities.get(code, 0) < need:
                return False
        return True

    def to_dict(self) -> dict:
        """序列化为字典（grid 用字符串 key 便于 JSON 存储）"""
        return {
            "id": self.id,
            "name": self.name,
            "brand": self.brand,
            "width": self.width,
            "height": self.height,
            "grid": {f"{c},{r}": code for (c, r), code in self.grid.items()},
            "color_usage": self.color_usage,
            "source_image": self.source_image,
            "created_at": self.created_at,
            "tags": self.tags,
            "input_mode": self.input_mode,
            "status": self.status,
            "ip_name": list(self.ip_name),
            "share_key": self.share_key,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Pattern":
        """从字典反序列化（兼容旧数据：无 id 时自动生成）"""
        grid = {}
        for key, code in data.get("grid", {}).items():
            c, r = key.split(",")
            grid[(int(c), int(r))] = code
        return cls(
            id=data.get("id") or _new_id(),
            name=data["name"],
            brand=data["brand"],
            width=data["width"],
            height=data["height"],
            grid=grid,
            color_usage=dict(data.get("color_usage", {})),
            source_image=data.get("source_image"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            tags=list(data.get("tags", [])),
            input_mode=data.get("input_mode", "pixel_convert"),
            status=data.get("status", "pending"),
            ip_name=_parse_ip_name(data.get("ip_name")),
            share_key=data.get("share_key", ""),
        )

    def __repr__(self) -> str:
        return (
            f"Pattern(name={self.name!r}, brand={self.brand}, "
            f"size={self.width}x{self.height}, colors={len(self.color_usage)}, "
            f"beads={self.total_beads()})"
        )
