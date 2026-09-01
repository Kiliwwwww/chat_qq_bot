from .help import help_cmd
from .personality import switch_kind_cmd, switch_default_cmd
from .ai_service_cmd import (
    add_ai_service_cmd,
    ai_service_list_cmd,
    switch_ai_service_cmd,
    delete_ai_service_cmd,
)
from .admin import (
    mute_cmd,
    ban_cmd,
    emoji_cmd,
    emoji_cancel_cmd,
    group_emoji_cmd,
    group_emoji_cancel_cmd,
    emoji_all_cmd,
    emoji_all_cancel_cmd,
    setkey_cmd,
    settings_cmd,
    groupsettings_cmd,
    welcome_cmd,
    ad_recall_on_cmd,
    ad_recall_off_cmd,
    ad_keyword_cmd,
    ad_status_cmd,
)
from .kb_cmd import (
    kb_add_cmd,
    kb_del_cmd,
    kb_list_cmd,
    kb_upload_cmd,
)
from .stats_cmd import stats_cmd

__all__ = [
    "help_cmd",
    "switch_kind_cmd",
    "switch_default_cmd",
    "add_ai_service_cmd",
    "ai_service_list_cmd",
    "switch_ai_service_cmd",
    "delete_ai_service_cmd",
    "mute_cmd",
    "ban_cmd",
    "emoji_cmd",
    "emoji_cancel_cmd",
    "group_emoji_cmd",
    "group_emoji_cancel_cmd",
    "emoji_all_cmd",
    "emoji_all_cancel_cmd",
    "setkey_cmd",
    "settings_cmd",
    "groupsettings_cmd",
    "welcome_cmd",
    "ad_recall_on_cmd",
    "ad_recall_off_cmd",
    "ad_keyword_cmd",
    "ad_status_cmd",
    "kb_add_cmd",
    "kb_del_cmd",
    "kb_list_cmd",
    "kb_upload_cmd",
    "stats_cmd",
]
