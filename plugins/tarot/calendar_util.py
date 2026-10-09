"""日期工具：阳历（公历）与农历（阴历）文本格式化。

塔罗等西方占卜使用阳历，小六壬等传统术数使用农历，均通过本模块统一生成
「今天是……」的上下文，交由 AI 在解读时结合。

依赖纯 Python 库 lunardate（支持 1900-2099）。
"""

from datetime import datetime

from lunardate import LunarDate

WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

TIANGAN = "甲乙丙丁戊己庚辛壬癸"
DIZHI = "子丑寅卯辰巳午未申酉戌亥"
ZODIAC = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]

LUNAR_MONTHS = ["正", "二", "三", "四", "五", "六", "七", "八", "九", "十", "冬", "腊"]
_DIGITS = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]


def solar_date_text(dt: datetime) -> str:
    """阳历日期文本，如「2026年10月8日 星期四」。"""
    return f"{dt.year}年{dt.month}月{dt.day}日 {WEEKDAYS[dt.weekday()]}"


def lunar_day_name(day: int) -> str:
    """农历日名称，如 初八 / 十五 / 廿八 / 三十。"""
    if day <= 10:
        return "初" + _DIGITS[day]
    if day < 20:
        return "十" + _DIGITS[day - 10]
    if day == 20:
        return "二十"
    if day < 30:
        return "廿" + _DIGITS[day - 20]
    return "三十"


def lunar_month_name(month: int, is_leap: bool = False) -> str:
    """农历月名称，如 正月 / 闰六月 / 腊月。"""
    return ("闰" if is_leap else "") + LUNAR_MONTHS[month - 1] + "月"


def lunar_year_name(year: int) -> str:
    """农历年名称，如「丙午年（马年）」。"""
    ganzhi = TIANGAN[(year - 4) % 10] + DIZHI[(year - 4) % 12]
    animal = ZODIAC[(year - 4) % 12]
    return f"{ganzhi}年（{animal}年）"


def lunar_date_text(lunar: LunarDate) -> str:
    """农历完整日期文本，如「丙午年（马年）八月廿八」。"""
    return (
        f"{lunar_year_name(lunar.year)} "
        f"{lunar_month_name(lunar.month, lunar.is_leap_month)}"
        f"{lunar_day_name(lunar.day)}"
    )


def to_lunar(dt: datetime) -> LunarDate | None:
    """把阳历日期转换为农历，超出支持范围时返回 None。"""
    try:
        return LunarDate.from_solar_date(dt.year, dt.month, dt.day)
    except Exception:
        return None
