"""坊市系统：神秘商人限时商品 + 玩家交易挂单。"""

import random
import time

from .. import constants
from ..state import config, db, get_cache
from . import world


# ==================== 神秘商人 ====================

def _merchant_seed(group_id: int) -> int:
    """用商人出现时间作为随机种子，保证同一批商品不变"""
    state = db.get_world_state(group_id)
    return int(state.get("merchant_end_time", 0))


def get_merchant_goods(group_id: int) -> list[dict]:
    """获取当前神秘商人的商品（带 seed 确定性）"""
    seed = _merchant_seed(group_id)
    if seed <= 0:
        return []
    rng = random.Random(seed)
    return rng.sample(constants.MERCHANT_GOODS, min(3, len(constants.MERCHANT_GOODS)))


async def buy_merchant_item(group_id: int, user_id: int, good_index: int) -> dict:
    """购买神秘商人商品"""
    if not world.is_merchant_active(group_id):
        return {"ok": False, "text": "神秘商人已离开坊市"}

    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}

    goods = get_merchant_goods(group_id)
    if good_index < 1 or good_index > len(goods):
        return {"ok": False, "text": "商品编号不存在"}

    good = goods[good_index - 1]

    # 同一批商品每名玩家限购一次（Redis 缓存，降级后同实例内存生效）
    cache = get_cache()
    key = f"{group_id}:merchant_bought:{user_id}"
    bought = await cache.hget(key, str(good_index))
    if bought:
        return {"ok": False, "text": "你已经购买过该商品了"}

    total = good["price"] * good["quantity"]
    if player.get("coin", 0) < total:
        return {"ok": False, "text": f"灵石不足，需要 {total} 灵石"}

    db.update_player(group_id, user_id, {"coin": player.get("coin", 0) - total})
    db.add_item(group_id, user_id, good["item_id"], good["quantity"])
    await cache.hset(key, str(good_index), "1")
    await cache.set(f"{key}:ttl", time.time(), expire=config.merchant_interval * 60)

    item_name = constants.ITEMS.get(good["item_id"], {}).get("name", good["item_id"])
    return {"ok": True, "text": f"🛒 购得 {item_name}×{good['quantity']}，花费 {total} 灵石"}


# ==================== 常驻商城 ====================

def format_shop() -> str:
    """格式化常驻商城"""
    lines = ["🏪 【常驻商城】", ""]
    for i, good in enumerate(constants.SHOP_GOODS, start=1):
        item = constants.ITEMS.get(good["item_id"], {})
        lines.append(f"  {i}. {item.get('name', good['item_id'])} - {good['price']} 灵石")
        lines.append(f"     💬 {item.get('desc', '')}")
    lines.append("\n💡 使用「商城购买 <编号>」购买丹药")
    lines.append("💡 材料/丹药/装备可卖给商城换灵石：「商城出售 <物品> <数量>」")
    return "\n".join(lines)


def buy_shop_item(group_id: int, user_id: int, index: int) -> dict:
    """从常驻商城购买丹药"""
    goods = constants.SHOP_GOODS
    if index < 1 or index > len(goods):
        return {"ok": False, "text": f"商品编号不存在（1~{len(goods)}）"}

    good = goods[index - 1]
    item = constants.ITEMS.get(good["item_id"], {})
    price = good["price"]

    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}

    if player.get("coin", 0) < price:
        return {"ok": False, "text": f"灵石不足，购买【{item.get('name', '')}】需要 {price} 灵石"}

    db.update_player(group_id, user_id, {"coin": player.get("coin", 0) - price})
    db.add_item(group_id, user_id, good["item_id"], 1)
    return {"ok": True, "text": f"🛒 购得【{item.get('name', '')}】×1，花费 {price} 灵石！\n💊 发送「服用 {item.get('name', '')}」使用"}


def get_item_buyback_price(item_id: str) -> int:
    """查询物品卖给商城的单价，无法出售返回 0"""
    if item_id in constants.SHOP_BUYBACK:
        return constants.SHOP_BUYBACK[item_id]
    if item_id.startswith("equip:"):
        parts = item_id.split(":")
        if len(parts) == 3:
            return constants.EQUIP_BUYBACK.get(parts[2], 0)
    return 0


def sell_to_shop(group_id: int, user_id: int, item_id: str, quantity: int = 1) -> dict:
    """将物品卖给商城换取灵石"""
    if quantity <= 0:
        return {"ok": False, "text": "数量必须为正数"}

    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色，发送「我要修仙」创建角色"}

    unit_price = get_item_buyback_price(item_id)
    if unit_price <= 0:
        return {"ok": False, "text": "该物品商城不收，无法出售"}

    # 装备每次只能卖一件
    if item_id.startswith("equip:") and quantity != 1:
        return {"ok": False, "text": "装备每次只能出售一件"}

    have = db.get_item_quantity(group_id, user_id, item_id)
    if have < quantity:
        item_name = constants.ITEMS.get(item_id, {}).get("name", item_id)
        return {"ok": False, "text": f"{item_name}数量不足（当前 {have}）"}

    total = unit_price * quantity
    db.remove_item(group_id, user_id, item_id, quantity)
    db.update_player(group_id, user_id, {"coin": player.get("coin", 0) + total})

    item_name = constants.ITEMS.get(item_id, {}).get("name", item_id)
    return {"ok": True, "text": f"💰 出售【{item_name}】×{quantity} 成功，获得 {total} 灵石！"}


# ==================== 玩家交易 ====================

def sell_item(group_id: int, user_id: int, item_id: str, quantity: int, price: int) -> dict:
    """上架物品到坊市"""
    if quantity <= 0 or price <= 0:
        return {"ok": False, "text": "数量与价格必须为正数"}

    have = db.get_item_quantity(group_id, user_id, item_id)
    if have < quantity:
        item_name = constants.ITEMS.get(item_id, {}).get("name", item_id)
        return {"ok": False, "text": f"{item_name}数量不足（当前 {have}）"}

    # 装备类物品按单个上架
    if item_id.startswith("equip:"):
        if quantity != 1:
            return {"ok": False, "text": "装备每次只能上架一件"}

    db.remove_item(group_id, user_id, item_id, quantity)
    order_id = db.create_order(group_id, user_id, item_id, quantity, price)
    if order_id is None:
        db.add_item(group_id, user_id, item_id, quantity)
        return {"ok": False, "text": "上架失败，请稍后再试"}

    item_name = constants.ITEMS.get(item_id, {}).get("name", item_id)
    return {"ok": True, "text": f"📦 上架成功：{item_name}×{quantity}，单价 {price} 灵石（挂单号 {order_id}）"}


def buy_order(group_id: int, user_id: int, order_id: int) -> dict:
    """购买他人挂单"""
    order = db.get_order(order_id, group_id)
    if not order:
        return {"ok": False, "text": "挂单不存在"}

    if order["status"] != "active":
        return {"ok": False, "text": "该挂单已成交"}

    if order["seller_id"] == user_id:
        return {"ok": False, "text": "不能购买自己的挂单"}

    player = db.get_player(group_id, user_id)
    if not player:
        return {"ok": False, "text": "你还没有修仙角色"}

    total = order["price"] * order["quantity"]
    if player.get("coin", 0) < total:
        return {"ok": False, "text": f"灵石不足，需要 {total} 灵石"}

    # 转账并转移物品
    db.update_player(group_id, user_id, {"coin": player.get("coin", 0) - total})
    seller = db.get_player(group_id, order["seller_id"])
    if seller:
        db.update_player(group_id, order["seller_id"], {"coin": seller.get("coin", 0) + total})
    db.add_item(group_id, user_id, order["item_id"], order["quantity"])
    db.update_order(order_id, group_id, {"status": "sold"})

    item_name = constants.ITEMS.get(order["item_id"], {}).get("name", order["item_id"])
    return {"ok": True, "text": f"🛒 购得 {item_name}×{order['quantity']}，花费 {total} 灵石"}


def cancel_order(group_id: int, user_id: int, order_id: int) -> dict:
    """撤销自己的挂单"""
    order = db.get_order(order_id, group_id)
    if not order or order["seller_id"] != user_id:
        return {"ok": False, "text": "只能撤销自己的挂单"}
    if order["status"] != "active":
        return {"ok": False, "text": "该挂单已成交"}

    db.add_item(group_id, user_id, order["item_id"], order["quantity"])
    db.update_order(order_id, group_id, {"status": "cancelled"})
    return {"ok": True, "text": "挂单已撤销，物品已退回背包"}


# ==================== 展示 ====================

def format_market(group_id: int, user_id: int) -> str:
    """格式化坊市展示"""
    lines = ["🏪 【坊市】"]

    # 神秘商人
    if world.is_merchant_active(group_id):
        lines.append("\n🧙 神秘商人（限时）:")
        goods = get_merchant_goods(group_id)
        for i, good in enumerate(goods, start=1):
            item_name = constants.ITEMS.get(good["item_id"], {}).get("name", good["item_id"])
            lines.append(f"  {i}. {item_name}×{good['quantity']} - {good['price'] * good['quantity']} 灵石")
        lines.append("  💡 使用「坊市购商 <编号>」购买")
    else:
        lines.append("\n🧙 神秘商人：未现身")

    # 玩家挂单
    orders = db.get_active_orders(group_id)
    lines.append("\n📜 玩家挂单:")
    if not orders:
        lines.append("  （暂无挂单）")
    else:
        for order in orders[:10]:
            item_name = constants.ITEMS.get(order["item_id"], {}).get("name", order["item_id"])
            lines.append(f"  #{order['id']} {item_name}×{order['quantity']} - {order['price'] * order['quantity']} 灵石")
    lines.append("\n💡 指令：坊市出售 <物品> <数量> <单价> / 坊市购买 <挂单号> / 坊市撤销 <挂单号>")
    return "\n".join(lines)
