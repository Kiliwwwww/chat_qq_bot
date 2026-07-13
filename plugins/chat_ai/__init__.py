from nonebot import get_plugin_config

from .config import Config
from .state import init_ai_service
from .commands import (
    help_cmd,
    switch_kind_cmd,
    switch_default_cmd,
    mute_cmd,
    emoji_cmd,
    emoji_cancel_cmd,
    group_emoji_cmd,
    group_emoji_cancel_cmd,
    setkey_cmd,
    settings_cmd,
    groupsettings_cmd,
)
from .handlers import private_msg, group_msg, reset_cmd

# 初始化配置
config = get_plugin_config(Config)

# 导出所有命令和处理器，确保 NoneBot2 能够注册它们
__all__ = [
    "help_cmd",
    "switch_kind_cmd",
    "switch_default_cmd",
    "mute_cmd",
    "emoji_cmd",
    "emoji_cancel_cmd",
    "group_emoji_cmd",
    "group_emoji_cancel_cmd",
    "setkey_cmd",
    "settings_cmd",
    "groupsettings_cmd",
    "private_msg",
    "group_msg",
    "reset_cmd",
]
