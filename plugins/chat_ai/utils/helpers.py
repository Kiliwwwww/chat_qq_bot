from datetime import datetime

from ..state import db, group_recent_messages, group_last_repeated


def get_time_period() -> str:
    """根据当前时间返回时间段（清晨/上午/中午/下午/晚上/深夜）"""
    hour = datetime.now().hour
    if 5 <= hour < 8:
        return "清晨"
    if 8 <= hour < 11:
        return "上午"
    if 11 <= hour < 13:
        return "中午"
    if 13 <= hour < 18:
        return "下午"
    if 18 <= hour < 23:
        return "晚上"
    return "深夜"


def get_time_hint() -> str:
    """生成当前时间提示，拼接到系统提示词中让 AI 感知时间"""
    now = datetime.now()
    period = get_time_period()
    return (
        f"\n\n## 当前时间提示\n"
        f"现在是 {now.year}年{now.month}月{now.day}日 {now.strftime('%H:%M')}，{period}。"
        f"请自然地按时间段调整措辞：清晨可以说\"早啊\"，中午可以问吃饭，"
        f"晚上可以说\"晚上好\"，深夜(凌晨)说话要轻一点、短一点、像还没睡的样子。"
    )


def clean_history_images(messages: list[dict]) -> list[dict]:
    """清理历史记录中的图片，只保留最近3条消息的图片"""
    if not messages:
        return messages

    # 创建副本，避免修改原始数据
    cleaned = []
    for i, msg in enumerate(messages):
        # 只处理用户消息
        if msg["role"] == "user" and isinstance(msg["content"], list):
            # 最近3条消息保留图片，历史消息只保留文本
            if i >= len(messages) - 6:
                cleaned.append(msg)  # 最近6条消息完整保留
            else:
                # 历史消息只保留文本部分
                text_parts = [item for item in msg["content"] if item.get("type") == "text"]
                if text_parts:
                    cleaned.append({"role": "user", "content": text_parts})
                else:
                    # 如果没有文本部分，添加一个默认描述
                    cleaned.append({"role": "user", "content": "[图片消息]"})
        else:
            cleaned.append(msg)
    return cleaned


def get_keywords_prompt() -> str:
    """获取提示词列表"""
    keywords = db.get_all_keywords()
    if not keywords:
        return ""
    kw_lines = "\n".join([f"- {kw['content']}" for kw in keywords])
    return f"\n\n## 用户自定义提示词:\n{kw_lines}"


def check_repeater(group_id: int, user_id: int, message: str) -> bool:
    """检测是否在复读，机器人跟读返回True"""
    if not message or len(message) > 100:  # 忽略空消息和过长消息
        return False

    if group_id not in group_recent_messages:
        group_recent_messages[group_id] = []

    recent = group_recent_messages[group_id]

    # 检查机器人是否已经复读过这条消息
    if group_id in group_last_repeated and group_last_repeated[group_id] == message:
        return False

    # 检查最近2条消息是否相同（连续复读），且来自不同用户
    if len(recent) >= 2:
        last1 = recent[-1]  # (user_id, message)
        last2 = recent[-2]  # (user_id, message)
        # 最近两条消息内容相同，且当前消息也相同，且来自不同用户
        if last1[1] == message and last2[1] == message and last1[0] != last2[0]:
            return True

    return False


def update_recent_messages(group_id: int, user_id: int, message: str):
    """更新群最近消息记录"""
    if not message or len(message) > 100:
        return

    if group_id not in group_recent_messages:
        group_recent_messages[group_id] = []

    recent = group_recent_messages[group_id]
    recent.append((user_id, message))

    # 只保留最近10条消息
    if len(recent) > 10:
        group_recent_messages[group_id] = recent[-10:]
