from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RARITY_WEIGHTS = {
    "白色": 60.0,
    "绿色": 24.0,
    "蓝色": 10.0,
    "紫色": 4.0,
    "金色": 1.5,
    "红色": 0.5,
}


@dataclass(frozen=True)
class LotteryItem:
    item_name: str
    image_name: str
    rarity: str
    price: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "item_name": self.item_name,
            "image_name": self.image_name,
            "rarity": self.rarity,
            "price": self.price,
        }


class LotteryEngine:
    """复用 lottery.html 中的物品池、稀有度概率与不连续重复规则。"""

    def __init__(self, items_path: Path):
        self.items_path = items_path
        self.items: list[LotteryItem] = []
        self.load_items()

    def load_items(self) -> None:
        import json

        raw_items = json.loads(self.items_path.read_text(encoding="utf-8"))
        items: list[LotteryItem] = []
        for entry in raw_items:
            items.append(
                LotteryItem(
                    item_name=str(entry["item_name"]),
                    image_name=str(entry["image_name"]),
                    rarity=str(entry["rarity"]),
                    price=int(entry["price"]),
                )
            )
        if not items:
            raise ValueError("抽奖物品池为空")
        self.items = items

    def _weighted_rarity(self) -> str:
        entries = list(RARITY_WEIGHTS.items())
        total = sum(weight for _, weight in entries)
        cursor = random.random() * total
        for rarity, weight in entries:
            cursor -= weight
            if cursor <= 0:
                return rarity
        return entries[0][0]

    def pick_result(self, exclude_name: str | None = None) -> LotteryItem:
        for _ in range(40):
            rarity = self._weighted_rarity()
            candidates = [
                item
                for item in self.items
                if item.rarity == rarity and item.item_name != exclude_name
            ]
            if candidates:
                return random.choice(candidates)
        candidates = [item for item in self.items if item.item_name != exclude_name]
        return random.choice(candidates or self.items)
