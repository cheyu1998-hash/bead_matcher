from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .color_chart import ColorChart, get_chart


@dataclass
class InventoryItem:
    """单个色号库存项"""
    code: str
    quantity: int

    def __post_init__(self):
        if self.quantity < 0:
            raise ValueError("库存数量不能为负数")


@dataclass
class Inventory:
    """用户拼豆库存"""
    brand: str
    items: Dict[str, InventoryItem] = field(default_factory=dict)

    def add(self, code: str, quantity: int) -> None:
        """添加/增加某个色号的库存"""
        if quantity <= 0:
            raise ValueError("添加数量必须为正数")
        if code in self.items:
            self.items[code].quantity += quantity
        else:
            self.items[code] = InventoryItem(code, quantity)

    def remove(self, code: str, quantity: int) -> None:
        """消耗某个色号的库存"""
        if quantity <= 0:
            raise ValueError("消耗数量必须为正数")
        if code not in self.items:
            raise KeyError(f"库存中无色号 {code}")
        if self.items[code].quantity < quantity:
            raise ValueError(f"色号 {code} 库存不足，当前 {self.items[code].quantity}，需要 {quantity}")
        self.items[code].quantity -= quantity
        if self.items[code].quantity == 0:
            del self.items[code]

    def set(self, code: str, quantity: int) -> None:
        """直接设置某个色号的库存数量"""
        if quantity < 0:
            raise ValueError("库存数量不能为负数")
        if quantity == 0:
            self.items.pop(code, None)
        else:
            self.items[code] = InventoryItem(code, quantity)

    def get(self, code: str) -> Optional[InventoryItem]:
        return self.items.get(code)

    def get_quantity(self, code: str) -> int:
        item = self.items.get(code)
        return item.quantity if item else 0

    def list_codes(self) -> List[str]:
        return sorted(self.items.keys())

    def total_count(self) -> int:
        return sum(item.quantity for item in self.items.values())

    def to_dict(self) -> dict:
        return {
            "brand": self.brand,
            "items": {code: item.quantity for code, item in self.items.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Inventory":
        inv = cls(brand=data["brand"])
        for code, qty in data.get("items", {}).items():
            inv.set(code, qty)
        return inv

    def validate_against_chart(self) -> List[str]:
        """校验库存色号是否都在当前色卡中存在，返回无效色号列表"""
        chart = get_chart(self.brand)
        if not chart:
            return []
        invalid = []
        for code in self.items:
            if chart.get(code) is None:
                invalid.append(code)
        return invalid

    def __repr__(self) -> str:
        return f"Inventory(brand={self.brand!r}, items={len(self.items)}, total={self.total_count()})"
