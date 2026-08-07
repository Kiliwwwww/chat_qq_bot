"""赠送物品指令。"""

from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.params import CommandArg

from ..services import inventory as inv_svc
from .helpers import require_game, xiuxian_command, reply_finish

gift_cmd = xiuxian_command("赠送", aliases={"送礼", "送"}, priority=5, block=True)


def _extract_at_target(args: Message) -> int:
    """从消息中提取被 @ 的用户 QQ 号"""
    for seg in args:
        if seg.type == "at":
            try:
                return int(seg.data.get("qq", 0))
            except (ValueError, TypeError):
                return 0
    return 0


def _extract_text_parts(args: Message) -> list[str]:
    """提取消息中纯文本片段（忽略 @ 段），按空格分词返回"""
    parts: list[str] = []
    for seg in args:
        if seg.type == "text" and seg.data.get("text"):
            parts.extend(seg.data["text"].strip().split())
    return parts


@gift_cmd.handle()
async def handle_gift(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    group_id = await require_game(gift_cmd, event)

    target_id = _extract_at_target(args)
    if not target_id:
        await reply_finish(gift_cmd, event, "请 @ 一个玩家作为赠送对象，如：赠送 @某某 洗髓丹")

    parts = _extract_text_parts(args)
    if not parts:
        await reply_finish(gift_cmd, event, "请指定要赠送的物品，如：赠送 @某某 洗髓丹")
    name = parts[0]
    quantity = 1
    if len(parts) > 1:
        try:
            quantity = int(parts[1])
        except ValueError:
            await reply_finish(gift_cmd, event, "数量必须是数字，如：赠送 @某某 洗髓丹 3")
    if quantity <= 0:
        await reply_finish(gift_cmd, event, "数量必须为正数")

    result = inv_svc.gift_item(group_id, event.user_id, target_id, name, quantity)
    await reply_finish(gift_cmd, event, result["text"])
