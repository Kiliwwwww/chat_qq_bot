"""世界时间与事件系统。

每个群独立运行一个"世界"：
- 世界状态持久化在数据库，定期通过 Tick 推进
- 事件（灵气潮汐/妖兽暴动/上古秘境/天地异象）随机触发并持续一段时间
- 神秘商人随机出现，限时出售商品
- 事件变化会主动推送到对应群聊
"""

import random
import time
from typing import Optional

from nonebot import get_bot, logger

from .. import constants
from ..state import config, db

# 各事件触发权重
_EVENT_WEIGHTS = {
    "lingqi_chaoxi": 30,
    "yaoshou_baodong": 25,
    "shanggu_mijing": 20,
    "tiandi_yixiang": 25,
    "tianjiang_lingyu": 25,
    "daoyun_miman": 20,
    "wanshou_caozong": 15,
    "xianyuan_jianglin": 20,
    "mochao_xiongyong": 10,
}


# ==================== 世界状态读取 ====================

def ensure_world(group_id: int) -> dict:
    """确保群世界状态存在并返回"""
    return db.ensure_world_state(group_id)


def get_current_event(group_id: int) -> dict:
    """获取当前生效的世界事件，无事件返回空 dict"""
    state = ensure_world(group_id)
    event_id = state.get("current_event", "")
    if not event_id:
        return {}
    return dict(constants.WORLD_EVENTS.get(event_id, {}))


def is_event_active(group_id: int) -> bool:
    state = ensure_world(group_id)
    event_id = state.get("current_event", "")
    end_time = state.get("event_end_time", 0)
    return bool(event_id) and (not end_time or time.time() < end_time)


def is_secret_realm_open(group_id: int) -> bool:
    """秘境是否开启。

    只要「上古秘境」事件正在持续，无论秘境时间戳数据是否已同步，都视为开启，
    避免出现"事件显示开启但进不去"的情况。
    """
    state = ensure_world(group_id)
    if time.time() < state.get("secret_realm_end_time", 0):
        return True
    event_id = state.get("current_event", "")
    if event_id == "shanggu_mijing":
        return is_event_active(group_id)
    return False


def is_location_open(group_id: int, location: str) -> bool:
    """地点是否开放。

    普通地点（洞府/灵脉/妖兽森林）常开；限时地点需对应的世界事件激活。
    """
    event_id = constants.LOCATION_EVENTS.get(location)
    if not event_id:
        return True
    if location == "秘境":
        return is_secret_realm_open(group_id)
    state = ensure_world(group_id)
    return state.get("current_event") == event_id and is_event_active(group_id)


def location_open_event(location: str) -> str:
    """返回限时地点对应的开启事件名称（常开地点返回空串）"""
    event_id = constants.LOCATION_EVENTS.get(location)
    if not event_id:
        return ""
    return constants.WORLD_EVENTS.get(event_id, {}).get("name", "")


def trigger_event(group_id: int, event_name: str) -> dict:
    """管理员手动触发世界事件。

    event_name 为事件名称或 id；传入「无/结束/清除」可结束当前事件。
    """
    now = time.time()

    # 清除当前事件
    if event_name in ("无", "结束", "清除"):
        db.update_world_state(group_id, {"current_event": "", "event_end_time": 0, "secret_realm_end_time": 0})
        return {"ok": True, "text": "🌄 当前世界事件已清除，天地恢复平静"}

    # 按名称或 id 解析事件
    event_id = None
    for eid, ev in constants.WORLD_EVENTS.items():
        if ev["name"] == event_name or eid == event_name:
            event_id = eid
            break
    if not event_id:
        names = "、".join(ev["name"] for ev in constants.WORLD_EVENTS.values())
        return {"ok": False, "text": f"未找到事件「{event_name}」，可选：{names}"}

    duration = config.trigger_event_duration * 60
    end_time = now + duration
    fields = {"current_event": event_id, "event_end_time": end_time}
    # 上古秘境事件同步开启秘境，其余事件关闭秘境
    fields["secret_realm_end_time"] = end_time if event_id == "shanggu_mijing" else 0
    db.update_world_state(group_id, fields)
    db.log_world_event(group_id, event_id, constants.WORLD_EVENTS[event_id]["name"])

    ev = constants.WORLD_EVENTS[event_id]
    return {
        "ok": True,
        "text": (
            f"🌍 【世界事件】{ev['name']}（持续 {config.trigger_event_duration} 分钟）\n"
            f"{ev['desc']}\n"
            f"⚡ 效果：{format_event_effects(ev)}"
        ),
    }


def is_merchant_active(group_id: int) -> bool:
    """神秘商人是否在场"""
    state = ensure_world(group_id)
    return time.time() < state.get("merchant_end_time", 0)


def get_merchant_goods() -> list[dict]:
    """生成神秘商人的限时商品"""
    goods = random.sample(constants.MERCHANT_GOODS, min(3, len(constants.MERCHANT_GOODS)))
    return goods


# ==================== 世界数值修正 ====================

def cultivation_multiplier(group_id: int) -> float:
    """修炼速度总倍率（世界层面）"""
    state = ensure_world(group_id)
    mult = float(state.get("spirit_concentration", 1.0))
    event = get_current_event(group_id)
    mult *= event.get("rate", 1.0)
    return mult


def breakthrough_bonus(group_id: int) -> float:
    """世界事件对突破成功率的加成"""
    event = get_current_event(group_id)
    return event.get("breakthrough", 0.0)


def forest_multiplier(group_id: int) -> float:
    """妖兽森林在当前世界状态下的收益倍率"""
    event = get_current_event(group_id)
    return event.get("forest", 1.0)


def forest_risk_bonus(group_id: int) -> float:
    """妖兽森林在当前世界状态下的额外风险"""
    event = get_current_event(group_id)
    return event.get("risk", 0.0)


def enlighten_bonus(group_id: int) -> float:
    """世界事件对顿悟概率的加成"""
    event = get_current_event(group_id)
    return event.get("enlighten", 0.0)


def explore_luck_multiplier(group_id: int) -> float:
    """世界事件对探索奇遇的倍率"""
    event = get_current_event(group_id)
    return event.get("explore_luck", 1.0)


# ==================== 世界推进 ====================

def _roll_event() -> str:
    """随机抽取一个世界事件"""
    return random.choices(
        list(_EVENT_WEIGHTS.keys()),
        weights=list(_EVENT_WEIGHTS.values()),
        k=1,
    )[0]


def _roll_weather() -> str:
    return random.choice(constants.WEATHERS)


# 天气对灵气浓度的影响
_WEATHER_SPIRIT = {
    "晴": 1.0, "阴": 1.0, "小雨": 0.95, "大雨": 0.9, "雷暴": 1.2, "狂风": 0.9,
}


def advance_world(group_id: int, now: Optional[float] = None) -> list[dict]:
    """推进一个群的世界状态，返回发生的变化（用于推送消息）。

    返回值：announcements 列表，每项含 type(event/merchant) 与 text。
    """
    now = now or time.time()
    state = ensure_world(group_id)
    announcements = []

    # 1. 当前事件是否结束
    event_id = state.get("current_event", "")
    event_end = state.get("event_end_time", 0)
    event_active = bool(event_id) and now < event_end

    # 2. 天气随机变化（灵气浓度随天气浮动）
    new_weather = state.get("weather", "晴")
    if random.random() < 0.2:
        new_weather = _roll_weather()
    spirit = _WEATHER_SPIRIT.get(new_weather, 1.0)

    # 3. 事件切换
    if event_active:
        # 事件持续中（事件效果在计算时另行应用）
        # 上古秘境事件：秘境开启时间与事件保持同步（修复旧数据/重启导致秘境提前关闭）
        if event_id == "shanggu_mijing":
            realm_end = state.get("secret_realm_end_time", 0)
            if now >= realm_end:
                db.update_world_state(group_id, {"secret_realm_end_time": event_end})
    else:
        # 事件已结束，尝试触发新事件
        if event_id:
            db.update_world_state(group_id, {"current_event": "", "event_end_time": 0})
            event_id = ""
        if random.random() < 0.35:
            new_event = _roll_event()
            duration = config.world_event_duration * 60
            new_end = now + duration
            db.update_world_state(group_id, {
                "current_event": new_event,
                "event_end_time": new_end,
            })
            event_info = constants.WORLD_EVENTS[new_event]
            # 上古秘境事件自动开启秘境（持续整个事件期间）
            if new_event == "shanggu_mijing":
                db.update_world_state(group_id, {
                    "secret_realm_end_time": new_end,
                })
            db.log_world_event(group_id, new_event, event_info["name"])
            announcements.append({
                "type": "event",
                "text": (
                    f"🌍 【世界事件】{event_info['name']}\n"
                    f"{event_info['desc']}\n"
                    f"⚡ 效果：{format_event_effects(event_info)}"
                ),
            })

    # 4. 神秘商人出现/消失
    merchant_end = state.get("merchant_end_time", 0)
    if now >= merchant_end:
        if random.random() < 0.05:
            new_end = now + config.merchant_interval * 60
            db.update_world_state(group_id, {"merchant_end_time": new_end})
            announcements.append({
                "type": "merchant",
                "text": "🏪 【神秘商人】一位云游商人现身坊市，带来了稀有的丹药与材料，快来「坊市」看看！",
            })

    # 5. 世界 Boss 刷新与超时
    from . import boss as boss_svc
    boss_announce = boss_svc.maybe_spawn(group_id)
    if boss_announce:
        announcements.append({"type": "event", "text": boss_announce})
    boss_escape = boss_svc.check_expire(group_id)
    if boss_escape:
        announcements.append({"type": "event", "text": boss_escape})

    # 6. 更新世界状态
    db.update_world_state(group_id, {
        "weather": new_weather,
        "spirit_concentration": round(spirit, 2),
        "last_tick_time": now,
    })

    return announcements


async def world_tick() -> None:
    """世界 Tick 任务：推进所有活跃群的世界状态并推送事件。"""
    try:
        group_ids = db.get_all_player_groups()
        if not group_ids:
            return
        bot = None
        try:
            bot = get_bot()
        except Exception:
            bot = None
        for group_id in group_ids:
            try:
                # 已关闭修仙功能的群跳过世界推进
                if not db.is_game_enabled(group_id):
                    continue
                announcements = advance_world(group_id)
                if not announcements:
                    continue
                if bot is None:
                    logger.info(f"群 {group_id} 世界事件生成（无可用 Bot 推送）: {[a['type'] for a in announcements]}")
                    continue
                for item in announcements:
                    if item["type"] in ("event", "merchant"):
                        await bot.send_group_msg(group_id=group_id, message=item["text"])
                        logger.info(f"群 {group_id} 世界事件推送: {item['text'][:30]}")
            except Exception as e:
                logger.warning(f"群 {group_id} 世界推进失败: {e}")
    except Exception as e:
        logger.error(f"世界 Tick 执行失败: {e}")


def start_world_scheduler() -> None:
    """注册世界 Tick 定时任务（应用启动时调用）"""
    try:
        from nonebot import require
        require("nonebot_plugin_apscheduler")
        from nonebot_plugin_apscheduler import scheduler

        scheduler.add_job(
            world_tick,
            "interval",
            seconds=config.world_tick_interval,
            id="xiuxian_world_tick",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=30,
        )
        logger.info(f"修仙世界 Tick 任务已注册，间隔 {config.world_tick_interval} 秒")
    except Exception as e:
        logger.error(f"注册世界 Tick 任务失败: {e}")


def format_event_effects(event: dict) -> str:
    """将世界事件的数值效果格式化为详细描述"""
    if not event:
        return "暂无特殊效果"
    parts = []
    if event.get("rate"):
        parts.append(f"修炼速度 ×{event['rate']}")
    if event.get("breakthrough"):
        parts.append(f"突破成功率 +{int(event['breakthrough'] * 100)}%")
    if event.get("forest"):
        parts.append(f"妖兽森林收益 ×{event['forest']}")
    if event.get("risk"):
        parts.append(f"妖兽森林遇险率 +{int(event['risk'] * 100)}%")
    if event.get("enlighten"):
        parts.append(f"顿悟概率 +{int(event['enlighten'] * 100)}%")
    if event.get("explore_luck"):
        parts.append(f"探索奇遇 ×{event['explore_luck']}")
    if event.get("opens_secret_realm"):
        parts.append("开启秘境供探索")
    return "，".join(parts) if parts else "暂无特殊效果"


def format_world_status(group_id: int) -> str:
    """格式化世界状态展示文本"""
    state = ensure_world(group_id)
    lines = [
        "🌍 【修仙世界】",
        f"⛅ 天气：{state.get('weather', '晴')}",
        f"💧 灵气浓度：{state.get('spirit_concentration', 1.0)}",
    ]
    event_id = state.get("current_event", "")
    if event_id and is_event_active(group_id):
        event = constants.WORLD_EVENTS[event_id]
        remaining = int((state["event_end_time"] - time.time()) / 60)
        lines.append(f"✨ 当前事件：{event['name']}（剩余 {max(remaining, 0)} 分钟）")
        lines.append(f"   ⚡ 效果：{format_event_effects(event)}")
    else:
        lines.append("✨ 当前事件：暂无（天地平静）")
    lines.append(f"🏪 神秘商人：{'在场' if is_merchant_active(group_id) else '未现身'}")
    lines.append(f"🗺️ 秘境：{'已开启' if is_secret_realm_open(group_id) else '未开启'}")
    # 当前开放的限时地点
    open_locations = [
        loc for loc in constants.LOCATIONS
        if loc in constants.LOCATION_EVENTS and is_location_open(group_id, loc)
    ]
    if open_locations:
        lines.append("🗺️ 限时地图开放：" + "、".join(open_locations))
    return "\n".join(lines)
