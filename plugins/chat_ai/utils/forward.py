"""合并转发（聊天记录）消息解析"""

from nonebot import get_bot, logger

MAX_NODES = 30
MAX_DEPTH = 3
MAX_TEXT_LEN = 3000

# 提示词：告诉 AI 转发聊天记录的格式含义
FORWARD_FORMAT_HINT = (
    "\n\n## 消息格式说明\n"
    "当消息里出现 [转发的聊天记录 | 转发者: xxx] 到 [聊天记录结束] 之间的内容时，"
    "表示用户 xxx 转发来了一段聊天记录（可能是群聊或私聊的历史对话），"
    "这段内容不是当前对话，是 xxx 转发给别人看的。\n"
    "格式为每行一条：「序号. 昵称: 内容」，即那场聊天里每个人的发言。\n"
    "「[内嵌转发的聊天记录]」表示那场聊天里还有人转发了另一段记录，缩进行是内层内容。\n"
    "看到聊天记录后，可以结合内容吐槽、接话、评价，就像你亲眼看到了那段聊天一样。"
)


def _segments_to_text(content) -> str:
    """把消息段（字符串 / dict / 数组）拍平成纯文本"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        content = [content]
    parts: list[str] = []
    for seg in content or []:
        if isinstance(seg, str):
            parts.append(seg)
            continue
        if not isinstance(seg, dict):
            continue
        seg_type = seg.get("type", "") or ""
        data = seg.get("data", {}) or {}
        if seg_type == "text":
            parts.append(str(data.get("text", "")))
        elif seg_type == "image":
            parts.append("[图片]")
        elif seg_type == "face":
            parts.append("[表情]")
        elif seg_type == "at":
            parts.append(f"@{data.get('qq', '')}")
        elif seg_type == "video":
            parts.append("[视频]")
        elif seg_type == "record":
            parts.append("[语音]")
        elif seg_type == "forward":
            parts.append("[内嵌转发的聊天记录]")
        elif seg_type in ("json", "xml"):
            parts.append("[卡片消息]")
        elif seg_type == "node":
            inner = _segments_to_text(data.get("content"))
            name = data.get("nickname") or data.get("name") or ""
            parts.append(f"{name}: {inner}" if name else inner)
        else:
            parts.append(f"[{seg_type or '未知消息'}]")
    return "".join(parts).strip()


def _node_name(node: dict) -> str:
    """从节点里取发送者昵称"""
    sender = node.get("sender") or {}
    if isinstance(sender, dict):
        name = sender.get("nickname") or sender.get("card") or sender.get("user_id")
        if name:
            return str(name)
    return str(node.get("nickname") or node.get("name") or "未知用户")


def _node_content(node: dict):
    """从节点里取消息内容"""
    if "content" in node:
        return node.get("content")
    data = node.get("data") or {}
    return data.get("content")


def _node_forward_ids(content) -> list[str]:
    """提取消息内容里嵌套的合并转发 ID"""
    if isinstance(content, dict):
        content = [content]
    ids: list[str] = []
    for seg in content or []:
        if not isinstance(seg, dict):
            continue
        if seg.get("type") == "forward":
            data = seg.get("data", {}) or {}
            fid = str(data.get("id") or data.get("message_id") or "").strip()
            if fid and fid not in ids:
                ids.append(fid)
    return ids


async def _fetch_forward_nodes(message_id: str) -> list[dict]:
    """调用 get_forward_msg 拉取合并转发节点"""
    bot = get_bot()
    try:
        result = await bot.call_api("get_forward_msg", message_id=message_id)
    except Exception as e:
        logger.warning(f"获取合并转发消息失败: {e}")
        return []

    if isinstance(result, dict):
        # 兼容 {"messages": [...]} 与 {"data": {"messages": [...]}} 两种返回
        nodes = result.get("messages")
        if nodes is None:
            nodes = (result.get("data") or {}).get("messages")
        return nodes if isinstance(nodes, list) else []
    return []


async def extract_forward_text(
    message,
    forwarder: str = "",
    max_nodes: int = MAX_NODES,
) -> str:
    """
    提取消息中的合并转发（聊天记录）内容，返回 AI 易读的结构化文本块。

    输出格式：
        [转发的聊天记录 | 转发者: 张三]
        1. 张三: 今天天气不错
        2. 李四: 出去玩啊
        3. 王五: [内嵌转发的聊天记录]
          3.1 赵六: 内层消息1
        [聊天记录结束]

    支持嵌套转发（最多 MAX_DEPTH 层），超出长度截断。

    Args:
        message: OneBot 消息（event.get_message() 的结果）
        forwarder: 转发者昵称（发这条消息的人）

    Returns:
        结构化聊天记录文本块，无合并转发时返回空字符串
    """
    body: list[str] = []
    total = 0

    async def walk(message_id: str, depth: int, prefix: str):
        nonlocal total
        if depth > MAX_DEPTH or len(body) >= max_nodes or total >= MAX_TEXT_LEN:
            return
        nodes = await _fetch_forward_nodes(message_id)
        indent = "  " * (depth - 1)
        for i, node in enumerate(nodes, 1):
            if len(body) >= max_nodes or total >= MAX_TEXT_LEN:
                body.append(f"{indent}……（聊天记录过长，已截断）")
                return
            if not isinstance(node, dict):
                continue
            label = f"{prefix}{i}"
            content = _node_content(node)
            name = _node_name(node)
            # 嵌套合并转发：递归展开
            nested_ids = _node_forward_ids(content)
            if nested_ids:
                entry = f"{indent}{label}. {name}: [内嵌转发的聊天记录]"
                body.append(entry)
                total += len(entry)
                for nid in nested_ids:
                    await walk(nid, depth + 1, prefix=f"{label}.")
                continue
            text = _segments_to_text(content)
            if not text:
                continue
            entry = f"{indent}{label}. {name}: {text}"
            body.append(entry)
            total += len(entry)

    # 顶层：消息里的 forward 段（用 id 拉取）或内嵌节点
    for seg in message:
        seg_type = getattr(seg, "type", "") or ""
        data = getattr(seg, "data", {}) or {}
        if seg_type != "forward":
            continue
        fid = str(data.get("id") or data.get("message_id") or "").strip()
        if fid:
            await walk(fid, 1, prefix="")
        else:
            # 部分实现直接内嵌节点内容
            inline = data.get("messages") or data.get("content") or []
            if isinstance(inline, list):
                for j, node in enumerate(inline, 1):
                    if not isinstance(node, dict):
                        continue
                    text = _segments_to_text(_node_content(node))
                    if text:
                        entry = f"{j}. {_node_name(node)}: {text}"
                        body.append(entry)
                        total += len(entry)

    if not body:
        return ""

    who = f" | 转发者: {forwarder}" if forwarder else ""
    header = f"[转发的聊天记录{who} | 格式: 序号. 昵称: 内容]"
    return header + "\n" + "\n".join(body[:max_nodes])[:MAX_TEXT_LEN] + "\n[聊天记录结束]"
