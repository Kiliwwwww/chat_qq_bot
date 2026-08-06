"""游戏静态数据与常量定义。

所有数值相关的静态配置集中在这里，方便平衡调整。
"""

# ==================== 灵根系统 ====================

# 灵根类型：key 为灵根标识，name 为显示名，attr 为基础属性倍率，desc 为描述
SPIRIT_ROOTS = {
    "金": {"name": "金灵根", "attr": {"attack": 1.2, "defense": 1.2, "hp": 1.0}, "desc": "攻击、防御相关功法"},
    "木": {"name": "木灵根", "attr": {"attack": 0.9, "defense": 1.0, "hp": 1.1}, "desc": "治疗、炼丹方向"},
    "水": {"name": "水灵根", "attr": {"attack": 0.9, "defense": 1.2, "hp": 1.1}, "desc": "控制、防御方向"},
    "火": {"name": "火灵根", "attr": {"attack": 1.3, "defense": 0.9, "hp": 1.0}, "desc": "爆发输出"},
    "土": {"name": "土灵根", "attr": {"attack": 0.9, "defense": 1.3, "hp": 1.3}, "desc": "防御、肉身方向"},
    "雷": {"name": "雷灵根", "attr": {"attack": 1.3, "defense": 1.0, "hp": 0.9}, "desc": "高爆发、高暴击"},
    "魔": {"name": "魔灵根", "attr": {"attack": 1.4, "defense": 1.0, "hp": 0.8}, "desc": "高风险高收益"},
    "空": {"name": "空灵根", "attr": {"attack": 1.0, "defense": 1.0, "hp": 1.0}, "desc": "万法皆通"},
}

# 随机天命时的灵根抽取权重（空灵根概率最低）
SPIRIT_ROOT_WEIGHTS = {
    "金": 16, "木": 14, "水": 14, "火": 14, "土": 14, "雷": 12, "魔": 10, "空": 6,
}

# ==================== 灵根品质系统 ====================

# 品质：修炼效率倍率
QUALITIES = {
    "废品": 0.05,
    "下品": 0.10,
    "中品": 0.30,
    "上品": 0.50,
    "极品": 0.80,
    "仙品": 1.00,
}

# 品质名称顺序（用于排序展示）
QUALITY_ORDER = ["废品", "下品", "中品", "上品", "极品", "仙品"]

# 随机天命时的品质抽取权重
QUALITY_WEIGHTS = {
    "废品": 28, "下品": 26, "中品": 22, "上品": 14, "极品": 8, "仙品": 2,
}

# ==================== 境界系统 ====================

# 境界：index 为境界索引，name 为名称，capacity 为突破到下一境界所需的当前境界修为，breakthrough_base 为基础突破成功率
REALMS = [
    {"index": 0, "name": "炼气", "capacity": 1000, "breakthrough_base": 0.90},
    {"index": 1, "name": "筑基", "capacity": 5000, "breakthrough_base": 0.80},
    {"index": 2, "name": "金丹", "capacity": 20000, "breakthrough_base": 0.70},
    {"index": 3, "name": "元婴", "capacity": 60000, "breakthrough_base": 0.60},
    {"index": 4, "name": "化神", "capacity": 150000, "breakthrough_base": 0.50},
    {"index": 5, "name": "炼虚", "capacity": 400000, "breakthrough_base": 0.45},
    {"index": 6, "name": "合体", "capacity": 1000000, "breakthrough_base": 0.40},
    {"index": 7, "name": "大乘", "capacity": 2500000, "breakthrough_base": 0.35},
    {"index": 8, "name": "渡劫", "capacity": 6000000, "breakthrough_base": 0.30},
    {"index": 9, "name": "飞升", "capacity": None, "breakthrough_base": 0.0},
]

# 境界战力倍率（用于战力计算与抓捕判定）
REALM_POWER_MULT = {i: 2 ** i for i in range(10)}

# 基础修炼速率（修为/小时，乘法修正前）
BASE_CULTIVATION_RATE = 100

# ==================== 功法系统 ====================

# 功法：按属性分类，普通灵根只能学习对应属性功法，空灵根可以学习所有属性
# attr 为加成属性（attack/defense/hp/cultivation），bonus 为加成数值
GONGFAS = {
    "金": [
        {"id": "gengjin_jj", "name": "庚金剑诀", "attr": "attack", "bonus": 0.12, "desc": "金系杀伐剑诀，攻击加成"},
        {"id": "bumie_js", "name": "不灭金身", "attr": "defense", "bonus": 0.12, "desc": "金系防御功法，防御加成"},
    ],
    "木": [
        {"id": "changchun_gong", "name": "长春功", "attr": "hp", "bonus": 0.12, "desc": "木系疗伤功法，气血加成"},
        {"id": "qingmu_zs", "name": "青木再生诀", "attr": "cultivation", "bonus": 0.12, "desc": "木系生机功法，修炼加成"},
    ],
    "水": [
        {"id": "xuanwu_zs", "name": "玄武真水诀", "attr": "defense", "bonus": 0.12, "desc": "水系防御功法，防御加成"},
        {"id": "bingxin_jue", "name": "冰心诀", "attr": "cultivation", "bonus": 0.12, "desc": "水系心法，修炼加成"},
    ],
    "火": [
        {"id": "fentian_jue", "name": "焚天诀", "attr": "attack", "bonus": 0.14, "desc": "火系爆发功法，攻击加成"},
        {"id": "lihuo_jue", "name": "离火焚天诀", "attr": "attack", "bonus": 0.12, "desc": "火系炼器功法，攻击加成"},
    ],
    "土": [
        {"id": "houtu_jue", "name": "厚土诀", "attr": "defense", "bonus": 0.12, "desc": "土系防御功法，防御加成"},
        {"id": "dadi_jgt", "name": "大地金刚体", "attr": "hp", "bonus": 0.14, "desc": "土系肉身功法，气血加成"},
    ],
    "雷": [
        {"id": "jiuxiao_sl", "name": "九霄神雷诀", "attr": "attack", "bonus": 0.16, "desc": "雷系爆发功法，攻击加成"},
        {"id": "tianlei_zf", "name": "天雷正法", "attr": "cultivation", "bonus": 0.12, "desc": "雷系镇邪功法，修炼加成"},
    ],
    "魔": [
        {"id": "shitian_mg", "name": "噬天魔功", "attr": "cultivation", "bonus": 0.20, "desc": "魔系速成功法，修炼加成"},
        {"id": "xuemai_da", "name": "血魔大法", "attr": "attack", "bonus": 0.15, "desc": "魔系血炼功法，攻击加成"},
    ],
}

# 按 id 索引功法
GONGFA_BY_ID = {g["id"]: {**g, "root": root} for root, gongfas in GONGFAS.items() for g in gongfas}

# 按名称索引功法
GONGFA_BY_NAME = {g["name"]: g for g in GONGFA_BY_ID.values()}

# 功法熟练度阶段与倍率
PROFICIENCIES = ["入门", "小成", "大成", "圆满", "极境"]
PROFICIENCY_MULT = [1.0, 1.5, 2.5, 4.0, 6.0]

# 每个熟练度阶段需要的经验值（累计）
PROFICIENCY_EXP = [0, 100, 300, 700, 1500]

# ==================== 修炼地点系统 ====================

# 修炼地点：multiplier 为修炼收益倍率，risk 为挂机失败/遇险概率，desc 为描述
LOCATIONS = {
    "洞府": {"multiplier": 1.0, "risk": 0.00, "desc": "稳定收益的修炼之所"},
    "灵脉": {"multiplier": 1.5, "risk": 0.05, "desc": "灵气充盈，修炼速度大增"},
    "妖兽森林": {"multiplier": 2.5, "risk": 0.25, "desc": "高收益，但可能遭遇妖兽"},
    "秘境": {"multiplier": 4.0, "risk": 0.40, "desc": "高风险高收益的凶险之地"},
}

# 妖兽暴动事件对妖兽森林的额外收益/风险加成
FOREST_EVENT_MULT = 1.5
FOREST_EVENT_RISK_ADD = 0.10

# ==================== 特殊体质系统 ====================

# 特殊体质：rate 为修炼加成，weight 为随机抽取权重
# 炉鼎相关体质：九阴灵体 / 紫金炉体（主人方）/ 玄阴鼎炉（炉鼎方）
PHYSIQUES = [
    {"id": "huanggu_sgt", "name": "荒古圣体", "rate": 0.10, "weight": 30, "desc": "肉身强大，后期成长高"},
    {"id": "tiansheng_jt", "name": "天生剑体", "rate": 0.10, "weight": 25, "desc": "剑法增强，攻击加成"},
    {"id": "tianmo_ti", "name": "天魔体", "rate": 0.15, "weight": 20, "desc": "魔功成长速度增加"},
    {"id": "jiuyin_lt", "name": "九阴灵体", "rate": 0.10, "weight": 15, "desc": "炉鼎反抗之力增强，挣脱成功率提升"},
    {"id": "zijin_luti", "name": "紫金炉体", "rate": 0.10, "weight": 10, "desc": "炉鼎大师，每个炉鼎修炼加速翻倍，且可多抓一个"},
    {"id": "xuanyin_dinglu", "name": "玄阴鼎炉", "rate": 0.10, "weight": 8, "desc": "天生炉鼎之资，被抓后主人受益翻倍，挣脱困难但觉醒更强"},
]

PHYSIQUE_BY_ID = {p["id"]: p for p in PHYSIQUES}

# 按名称索引体质
PHYSIQUE_BY_NAME = {p["name"]: p for p in PHYSIQUES}

# 获得特殊体质的概率（创建角色时）
PHYSIQUE_CHANCE = 0.08

# ==================== 灵宠系统 ====================

# 灵宠类型：rate 为挂机收益加成，weight 为探索抽取权重
PET_TYPES = [
    {"id": "yaoshou", "name": "妖兽", "rate": 0.03, "weight": 70, "desc": "最常见的灵宠，忠诚可靠"},
    {"id": "shenshou", "name": "神兽", "rate": 0.08, "weight": 25, "desc": "稀有神兽，战力超群"},
    {"id": "shangguyz", "name": "上古异种", "rate": 0.15, "weight": 5, "desc": "远古血脉，潜力无穷"},
]

PET_TYPE_BY_ID = {p["id"]: p for p in PET_TYPES}

# 灵宠升级所需经验：等级每提升一级所需 exp = PET_EXP_BASE * level
PET_EXP_BASE = 100

# ==================== 物品系统 ====================

# 物品目录：type 为 material(材料)/pill(丹药)/equip(装备)
# 丹药 effect 字段：
#   progress    服用增加修为
#   fortune     服用增加气运
#   breakthrough 突破时提高成功率
#   pet_exp     喂养灵宠提升经验
ITEMS = {
    "lingcao": {"name": "灵草", "type": "material", "desc": "炼丹基础材料"},
    "yaodan": {"name": "妖丹", "type": "material", "desc": "妖兽体内凝聚的精华"},
    "lingquan": {"name": "灵泉", "type": "material", "desc": "天地灵气凝结的泉水"},
    "xiulian_dan": {"name": "修炼丹", "type": "pill", "desc": "服用后获得修为", "effect": {"progress": 500}},
    "jusan_san": {"name": "聚气散", "type": "pill", "desc": "低阶丹药，服用增加少量修为", "effect": {"progress": 300}},
    "ningshen_dan": {"name": "凝神丹", "type": "pill", "desc": "中阶丹药，服用增加大量修为", "effect": {"progress": 800}},
    "peiyuan_dan": {"name": "培元丹", "type": "pill", "desc": "高阶丹药，服用暴增修为", "effect": {"progress": 2000}},
    "yunlun_dan": {"name": "蕴神丹", "type": "pill", "desc": "稀有丹药，服用增加气运", "effect": {"fortune": 50}},
    "tianji_dan": {"name": "天机丹", "type": "pill", "desc": "传说丹药，服用大幅增加气运", "effect": {"fortune": 200}},
    "pojing_dan": {"name": "破境丹", "type": "pill", "desc": "突破时使用可大幅提高成功率", "effect": {"breakthrough": 0.15}},
    "huiling_dan": {"name": "回灵丹", "type": "pill", "desc": "服用后恢复气血", "effect": {"hp": 100}},
    "jingyuan_dan": {"name": "精元丹", "type": "pill", "desc": "喂养灵宠可提升其经验", "effect": {"pet_exp": 100}},
}

ITEM_BY_NAME = {v["name"]: {"id": k, **v} for k, v in ITEMS.items()}

# 装备品质：mult 为属性倍率，weight 为锻造抽取权重
EQUIPMENT_QUALITIES = [
    {"name": "普通", "mult": 1.0, "weight": 50},
    {"name": "优秀", "mult": 1.5, "weight": 28},
    {"name": "极品", "mult": 2.5, "weight": 14},
    {"name": "灵器", "mult": 4.0, "weight": 6},
    {"name": "仙器", "mult": 8.0, "weight": 2},
]

# 装备类型：key 为装备槽位，name 为名称，stat 为加成的属性
EQUIPMENT_KINDS = {
    "weapon": {"name": "神兵", "stat": "attack"},
    "armor": {"name": "法袍", "stat": "defense"},
    "treasure": {"name": "法宝", "stat": "hp"},
}

# 炼丹消耗与产物
ALCHEMY_RECIPES = {
    "xiulian_dan": {"materials": {"lingcao": 2}, "cost": 20},
    "jusan_san": {"materials": {"lingcao": 2}, "cost": 30},
    "ningshen_dan": {"materials": {"lingcao": 2, "lingquan": 1}, "cost": 80},
    "peiyuan_dan": {"materials": {"lingcao": 3, "lingquan": 1, "yaodan": 1}, "cost": 200},
    "yunlun_dan": {"materials": {"lingquan": 2, "yaodan": 1}, "cost": 150},
    "tianji_dan": {"materials": {"lingquan": 2, "yaodan": 2}, "cost": 400},
    "pojing_dan": {"materials": {"lingcao": 2, "yaodan": 1}, "cost": 60},
    "huiling_dan": {"materials": {"lingcao": 1, "lingquan": 1}, "cost": 20},
    "jingyuan_dan": {"materials": {"yaodan": 2}, "cost": 30},
}

# 炼器消耗
FORGE_COST = {"materials": {"lingcao": 2, "yaodan": 2, "lingquan": 1}, "cost": 100}

# ==================== 世界事件系统 ====================

# 世界事件：id 为事件标识，rate 为修炼速度倍率，breakthrough 为突破成功率加成，forest 为妖兽森林收益倍率
WORLD_EVENTS = {
    "lingqi_chaoxi": {
        "name": "灵气潮汐",
        "rate": 1.5,
        "breakthrough": 0.10,
        "desc": "灵气潮汐涌动，全服修炼速度提升50%，突破成功率提升10%",
    },
    "yaoshou_baodong": {
        "name": "妖兽暴动",
        "forest": FOREST_EVENT_MULT,
        "risk": FOREST_EVENT_RISK_ADD,
        "desc": "妖兽暴动，妖兽森林收益提升50%，但挂机遇险概率增加",
    },
    "shanggu_mijing": {
        "name": "上古秘境开启",
        "desc": "上古秘境开启，全服玩家可进入探索，获得稀有功法、装备、材料",
    },
    "tiandi_yixiang": {
        "name": "天地异象",
        "desc": "天地异象频生，可能触发隐藏任务、特殊NPC、神秘传承",
    },
}

WORLD_EVENT_IDS = list(WORLD_EVENTS.keys())

# 天气类型（仅影响世界状态展示与微小数值）
WEATHERS = ["晴", "阴", "小雨", "大雨", "雷暴", "狂风"]

# ==================== 坊市系统 ====================

# 神秘商人限时商品池
MERCHANT_GOODS = [
    {"item_id": "xiulian_dan", "quantity": 3, "price": 150},
    {"item_id": "pojing_dan", "quantity": 2, "price": 400},
    {"item_id": "huiling_dan", "quantity": 3, "price": 100},
    {"item_id": "jingyuan_dan", "quantity": 3, "price": 200},
    {"item_id": "lingcao", "quantity": 10, "price": 50},
    {"item_id": "lingquan", "quantity": 5, "price": 120},
]

# ==================== 常驻商城系统 ====================

# 常驻商城：长期出售的丹药（价格高于炼丹成本，方便缺材料的玩家直接购买）
SHOP_GOODS = [
    {"item_id": "jusan_san", "price": 100},
    {"item_id": "xiulian_dan", "price": 200},
    {"item_id": "ningshen_dan", "price": 500},
    {"item_id": "peiyuan_dan", "price": 1500},
    {"item_id": "yunlun_dan", "price": 400},
    {"item_id": "tianji_dan", "price": 1500},
    {"item_id": "pojing_dan", "price": 300},
    {"item_id": "jingyuan_dan", "price": 150},
    {"item_id": "huiling_dan", "price": 100},
]

# ==================== 修炼/战斗基础数值 ====================

# 基础属性
BASE_ATTACK = 10
BASE_DEFENSE = 10
BASE_HP = 100

# 闭关时顿悟触发概率基数（受气运加成）
ENLIGHTEN_CHANCE = 0.05

# 顿悟获得修为（受气运影响）
ENLIGHTEN_PROGRESS = 500

# 气运默认值
DEFAULT_FORTUNE = 1000

# 废材流主角气运
TRASH_FORTUNE = 10000

# 炉鼎收益：每个炉鼎提供的修炼加速
FURNACE_RATE_BONUS = 0.10

# 突破失败产生的瓶颈冷却时间（分钟），期间无法再次突破
BOTTLENECK_MINUTES = 30
