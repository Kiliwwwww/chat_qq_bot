"""修仙排行榜指令。"""

from nonebot.adapters.onebot.v11 import Bot, Message
from nonebot.params import CommandArg

from ..services import ranking as rank_svc
from .helpers import require_game, xiuxian_command

ranking_cmd = xiuxian_command("修仙排行榜", aliases={"修仙排行"}, priority=5, block=True)

# 中文别名映射
_CATEGORY_ALIASES = {
    "境界": "realm", "境界榜": "realm",
    "战力": "power", "战力榜": "power",
    "财富": "wealth", "财富榜": "wealth",
    "气运": "fortune", "气运榜": "fortune",
    "炼丹": "alchemy", "炼丹榜": "alchemy",
}


@ranking_cmd.handle()
async def handle_ranking(bot: Bot, event, args: Message = CommandArg()):
    group_id = await require_game(ranking_cmd, event)

    arg = args.extract_plain_text().strip()
    category = _CATEGORY_ALIASES.get(arg, arg or "realm")
    await ranking_cmd.finish(rank_svc.format_ranking(group_id, category))
