"""命令层导出：导入所有指令模块，确保 NoneBot 注册。"""

from .player_cmd import (
    xiuxian_cmd,
    random_fate_cmd,
    trash_fate_cmd,
    status_cmd,
    help_cmd,
    change_physique_cmd,
    rebirth_cmd,
    suicide_cmd,
)
from .admin_cmd import game_on_cmd, game_off_cmd
from .cultivation_cmd import (
    biguan_cmd,
    chuguan_cmd,
    tupo_cmd,
    tansuo_cmd,
    gongfa_cmd,
    learn_gongfa_cmd,
    catalog_cmd,
    upgrade_gongfa_cmd,
)
from .world_cmd import world_cmd, trigger_event_cmd, summon_merchant_cmd
from .alchemy_cmd import (
    lian_dan_cmd,
    lian_qi_cmd,
    inventory_cmd,
    equip_cmd,
    unequip_cmd,
)
from .gift_cmd import gift_cmd
from .pet_cmd import pet_cmd, feed_cmd, pet_shop_cmd, pet_shop_buy_cmd
from .plant_cmd import plant_cmd, harvest_cmd, field_cmd
from .pill_cmd import use_pill_cmd, shop_cmd, shop_buy_cmd, shop_sell_cmd
from .market_cmd import (
    market_cmd,
    market_sell_cmd,
    market_buy_cmd,
    market_buy_merchant_cmd,
    market_buy_breakthrough_cmd,
    market_cancel_cmd,
)
from .furnace_cmd import capture_cmd, furnace_cmd, escape_cmd, release_cmd, xiuxiu_cmd
from .combat_cmd import signup_cmd, battle_status_cmd, pk_cmd
from .duel_cmd import duel_challenge_cmd, duel_accept_cmd
from .boss_cmd import boss_attack_cmd, boss_status_cmd, boss_spawn_cmd
from .invasion_cmd import invasion_attack_cmd, invasion_status_cmd
from .ranking_cmd import ranking_cmd

__all__ = [
    "xiuxian_cmd",
    "random_fate_cmd",
    "trash_fate_cmd",
    "status_cmd",
    "help_cmd",
    "change_physique_cmd",
    "rebirth_cmd",
    "suicide_cmd",
    "game_on_cmd",
    "game_off_cmd",
    "biguan_cmd",
    "chuguan_cmd",
    "tupo_cmd",
    "tansuo_cmd",
    "gongfa_cmd",
    "learn_gongfa_cmd",
    "catalog_cmd",
    "upgrade_gongfa_cmd",
    "world_cmd",
    "trigger_event_cmd",
    "summon_merchant_cmd",
    "lian_dan_cmd",
    "lian_qi_cmd",
    "inventory_cmd",
    "equip_cmd",
    "unequip_cmd",
    "gift_cmd",
    "pet_cmd",
    "feed_cmd",
    "pet_shop_cmd",
    "pet_shop_buy_cmd",
    "plant_cmd",
    "harvest_cmd",
    "field_cmd",
    "use_pill_cmd",
    "shop_cmd",
    "shop_buy_cmd",
    "shop_sell_cmd",
    "market_cmd",
    "market_sell_cmd",
    "market_buy_cmd",
    "market_buy_merchant_cmd",
    "market_buy_breakthrough_cmd",
    "market_cancel_cmd",
    "capture_cmd",
    "furnace_cmd",
    "escape_cmd",
    "release_cmd",
    "xiuxiu_cmd",
    "signup_cmd",
    "battle_status_cmd",
    "pk_cmd",
    "duel_challenge_cmd",
    "duel_accept_cmd",
    "boss_attack_cmd",
    "boss_status_cmd",
    "boss_spawn_cmd",
    "invasion_attack_cmd",
    "invasion_status_cmd",
    "ranking_cmd",
]
