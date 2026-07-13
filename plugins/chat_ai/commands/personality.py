from nonebot import on_command, get_plugin_config
from nonebot.adapters.onebot.v11 import MessageEvent

from ..config import Config
from .. import state
from ..state import db

switch_kind_cmd = on_command("邻家大姐姐人格", priority=5, block=True)
switch_default_cmd = on_command("雌小鬼人格", priority=5, block=True)


@switch_kind_cmd.handle()
async def handle_switch_kind(event: MessageEvent):
    """切换到邻家大姐姐人格"""
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await switch_kind_cmd.finish("权限不足，仅管理员可使用此命令")

    state.current_prompt_mode = "kind"
    db.set_setting("prompt_mode", "kind")
    state.ai_service = None  # 重置AI服务，下次使用时会重新初始化
    await switch_kind_cmd.finish("已切换到邻家大姐姐人格")


@switch_default_cmd.handle()
async def handle_switch_default(event: MessageEvent):
    """切换回默认人格（雌小鬼）"""
    # 管理员权限校验
    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await switch_default_cmd.finish("权限不足，仅管理员可使用此命令")

    state.current_prompt_mode = "default"
    db.set_setting("prompt_mode", "default")
    state.ai_service = None  # 重置AI服务，下次使用时会重新初始化
    await switch_default_cmd.finish("已切换回默认人格")
