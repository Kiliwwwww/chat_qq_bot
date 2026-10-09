"""塔罗牌数据与确定性抽牌逻辑。

抽牌结果只由 (QQ号, 日期) 决定：
同一个 QQ 在同一天内无论调用多少次，抽到的三张牌及其正/逆位都完全一致，
第二天会自动换一组新牌，符合「今日运势」的语义。
"""

import hashlib
import random

MAJOR_ARCANA = [
    "愚者",
    "魔术师",
    "女祭司",
    "皇后",
    "皇帝",
    "教皇",
    "恋人",
    "战车",
    "力量",
    "隐士",
    "命运之轮",
    "正义",
    "倒吊人",
    "死神",
    "节制",
    "恶魔",
    "高塔",
    "星星",
    "月亮",
    "太阳",
    "审判",
    "世界",
]

SUITS = ["权杖", "圣杯", "宝剑", "星币"]
RANKS = [
    "一",
    "二",
    "三",
    "四",
    "五",
    "六",
    "七",
    "八",
    "九",
    "十",
    "侍从",
    "骑士",
    "王后",
    "国王",
]

MINOR_ARCANA = [f"{suit}{rank}" for suit in SUITS for rank in RANKS]

FULL_DECK = MAJOR_ARCANA + MINOR_ARCANA

# 三个位置：现状 / 挑战 / 指引
POSITIONS = ["现状牌", "挑战牌", "指引牌"]


def seed_to_int(seed_text: str) -> int:
    """把种子字符串稳定地转换成整数，跨进程/跨运行保持一致。"""
    digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
    return int.from_bytes(digest, "big")


def draw_cards(user_id: int, date_str: str, count: int = 3) -> list[dict]:
    """根据 QQ 号和日期确定性地抽取 count 张不重复的塔罗牌。

    Args:
        user_id: 用户 QQ 号
        date_str: 日期字符串，如 "20261008"
        count: 抽牌数量，默认 3 张

    Returns:
        [{"name": 牌名, "reversed": 是否逆位}, ...]
    """
    rng = random.Random(seed_to_int(f"{user_id}:{date_str}"))
    indices = rng.sample(range(len(FULL_DECK)), count)
    return [
        {"name": FULL_DECK[index], "reversed": rng.random() < 0.5}
        for index in indices
    ]


def format_card(card: dict, position: str | None = None) -> str:
    """把抽出的牌格式化为「牌名（正位/逆位）」文本。"""
    orientation = "逆位" if card["reversed"] else "正位"
    if position:
        return f"{position}：{card['name']}（{orientation}）"
    return f"{card['name']}（{orientation}）"
