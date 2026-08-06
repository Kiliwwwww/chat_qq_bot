"""随机数与气运系统工具。

气运代表"天道对玩家的偏爱程度"：气运高于基准值时，
随机事件结果更倾向正面，低于基准值时更倾向负面。
"""

import random

from ..constants import DEFAULT_FORTUNE


def weighted_choice(items: list[dict], weight_key: str = "weight") -> dict:
    """按 weight 字段加权随机选择一个 item"""
    total = sum(item.get(weight_key, 1) for item in items)
    r = random.uniform(0, total)
    upto = 0
    for item in items:
        upto += item.get(weight_key, 1)
        if r <= upto:
            return item
    return items[-1]


def weighted_choice_dict(data: dict[str, int]) -> str:
    """按 value 为权重的 dict 加权随机选择 key"""
    total = sum(data.values())
    r = random.uniform(0, total)
    upto = 0
    for key, weight in data.items():
        upto += weight
        if r <= upto:
            return key
    return list(data.keys())[-1]


def fortune_factor(fortune: int) -> float:
    """将气运转换为概率修正因子。

    基准气运 1000 时为 0，越高越偏向正面。
    返回的因子用于把事件正面概率向 1 靠拢。
    """
    deviation = (fortune - DEFAULT_FORTUNE) / 100000.0
    return max(-0.15, min(0.15, deviation))


def luck_roll(base_chance: float, fortune: int) -> bool:
    """带气运修正的随机判定：base_chance 为基础概率。

    气运越高，成功概率越高；气运越低，成功概率越低。
    """
    if base_chance <= 0:
        return False
    if base_chance >= 1:
        return True
    chance = min(0.99, max(0.01, base_chance + fortune_factor(fortune)))
    return random.random() < chance


def risk_roll(base_chance: float, fortune: int) -> bool:
    """带气运修正的危险判定：base_chance 为基础危险概率。

    气运越高，危险概率越低（天道庇护）；气运越低，越容易遇险。
    """
    if base_chance <= 0:
        return False
    if base_chance >= 1:
        return True
    chance = min(0.99, max(0.01, base_chance - fortune_factor(fortune)))
    return random.random() < chance


def positive_shift(weights: dict[str, int], fortune: int, positive_keys: list[str]) -> dict[str, int]:
    """根据气运向正面结果倾斜权重。

    weights 为各结果的权重，positive_keys 为正面结果的 key。
    """
    factor = fortune_factor(fortune)
    if factor == 0:
        return weights
    shifted = dict(weights)
    for key in positive_keys:
        if key in shifted:
            shifted[key] = max(0, int(shifted[key] * (1 + factor * 10)))
    return shifted
