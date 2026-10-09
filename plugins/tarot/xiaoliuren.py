"""小六壬传统占卜：六宫推演与确定性排盘。

算法遵循传统「月上起日，日上起时」：
从大安起正月，顺数至所取月份；再从该宫起初一，顺数至所取日；
最后从该宫起子时，顺数至所取时辰，落宫即为本次结果。

为了让结果像塔罗一样稳定可复现，月/日/时三个数由 (QQ号, 日期) 确定性派生：
同一 QQ 同一天结果一致，次日自动变化。
"""

import random

from .calendar_util import lunar_date_text, lunar_day_name, lunar_month_name
from .tarot_deck import seed_to_int

# 六宫顺序（固定，不可打乱）
PALACES = ["大安", "留连", "速喜", "赤口", "小吉", "空亡"]

PALACE_META = {
    "大安": {"wuxing": "木", "direction": "东方", "spirit": "青龙"},
    "留连": {"wuxing": "水", "direction": "北方", "spirit": "玄武"},
    "速喜": {"wuxing": "火", "direction": "南方", "spirit": "朱雀"},
    "赤口": {"wuxing": "金", "direction": "西方", "spirit": "白虎"},
    "小吉": {"wuxing": "木", "direction": "东南", "spirit": "六合"},
    "空亡": {"wuxing": "土", "direction": "中央", "spirit": "勾陈"},
}

SHICHEN_NAMES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]


def draw_xiaoliuren(user_id: int, date_str: str, lunar_month: int, lunar_day: int) -> dict:
    """按真实农历月/日 + 由 (QQ号, 日期) 派生的时辰，确定性地推演一次小六壬。

    Args:
        user_id: 用户 QQ 号
        date_str: 阳历日期字符串（用于派生时辰，保证同人同日一致）
        lunar_month: 真实农历月份 1-12
        lunar_day: 真实农历日 1-30

    Returns:
        {
            "month": 农历月, "day": 农历日, "hour": 1-12,
            "palace": 落宫名, "wuxing": 五行, "direction": 方位, "spirit": 六神,
        }
    """
    rng = random.Random(seed_to_int(f"xiaoliuren:{user_id}:{date_str}"))
    hour = rng.randint(1, 12)

    # 大安起月，月上起日，日上起时（三个数各按 1 起算，故减 3）
    index = (lunar_month + lunar_day + hour - 3) % len(PALACES)
    palace = PALACES[index]

    return {
        "month": lunar_month,
        "day": lunar_day,
        "hour": hour,
        "palace": palace,
        **PALACE_META[palace],
    }


def shichen_name(hour: int) -> str:
    """把 1-12 的时辰序号转换为地支时辰名（1=子）。"""
    return SHICHEN_NAMES[(hour - 1) % len(SHICHEN_NAMES)]


def format_xiaoliuren(result: dict, lunar=None) -> str:
    """把推演结果格式化为可读文本。"""
    if lunar is not None:
        date_part = lunar_date_text(lunar)
    else:
        date_part = f"{lunar_month_name(result['month'])}{lunar_day_name(result['day'])}"
    return (
        f"农历：{date_part}　{shichen_name(result['hour'])}时\n"
        f"落宫：{result['palace']}"
        f"（五行属{result['wuxing']}，方位{result['direction']}，{result['spirit']}）"
    )
