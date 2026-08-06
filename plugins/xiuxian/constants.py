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
    "风": {"name": "风灵根", "attr": {"attack": 1.25, "defense": 0.9, "hp": 1.0}, "desc": "身法灵动，攻速加成"},
    "冰": {"name": "冰灵根", "attr": {"attack": 1.1, "defense": 1.1, "hp": 1.0}, "desc": "极寒之力，控制防御"},
    "暗": {"name": "暗灵根", "attr": {"attack": 1.25, "defense": 1.0, "hp": 0.85}, "desc": "隐匿暗杀，高爆发"},
    "光": {"name": "光灵根", "attr": {"attack": 1.0, "defense": 1.05, "hp": 1.15}, "desc": "圣光之力，辅助恢复"},
}

# 随机天命时的灵根抽取权重（空灵根概率最低）
SPIRIT_ROOT_WEIGHTS = {
    "金": 16, "木": 14, "水": 14, "火": 14, "土": 14, "雷": 12, "魔": 10, "空": 6, "风": 12, "冰": 10, "暗": 8, "光": 6,
}

# ==================== 灵根品质系统 ====================

# 品质：修炼效率倍率
QUALITIES = {
    "废品": 0.20,
    "下品": 0.50,
    "中品": 0.80,
    "上品": 1.00,
    "极品": 1.50,
    "仙品": 2.00,
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
BASE_CULTIVATION_RATE = 1000

# ==================== 功法系统 ====================

# 功法：按属性分类，普通灵根只能学习对应属性功法，空灵根可以学习所有属性
# attr 为加成属性（attack/defense/hp/cultivation），bonus 为加成数值
GONGFAS = {
    "金": [
        {"id": "gengjin_jj", "name": "庚金剑诀", "attr": "attack", "bonus": 0.12, "desc": "金系杀伐剑诀，攻击加成"},
        {"id": "bumie_js", "name": "不灭金身", "attr": "defense", "bonus": 0.12, "desc": "金系防御功法，防御加成"},
        {"id": "taiji_jjj", "name": "太乙金精诀", "attr": "attack", "bonus": 0.14, "desc": "金系炼体功法，攻击加成"},
    ],
    "木": [
        {"id": "changchun_gong", "name": "长春功", "attr": "hp", "bonus": 0.12, "desc": "木系疗伤功法，气血加成"},
        {"id": "qingmu_zs", "name": "青木再生诀", "attr": "cultivation", "bonus": 0.12, "desc": "木系生机功法，修炼加成"},
        {"id": "jiuzhuan_hc", "name": "九转回春术", "attr": "hp", "bonus": 0.14, "desc": "木系回春功法，气血大幅加成"},
    ],
    "水": [
        {"id": "xuanwu_zs", "name": "玄武真水诀", "attr": "defense", "bonus": 0.12, "desc": "水系防御功法，防御加成"},
        {"id": "bingxin_jue", "name": "冰心诀", "attr": "cultivation", "bonus": 0.12, "desc": "水系心法，修炼加成"},
        {"id": "tianhe_zhishui", "name": "天河真水诀", "attr": "attack", "bonus": 0.12, "desc": "水系攻伐功法，攻击加成"},
    ],
    "火": [
        {"id": "fentian_jue", "name": "焚天诀", "attr": "attack", "bonus": 0.14, "desc": "火系爆发功法，攻击加成"},
        {"id": "lihuo_jue", "name": "离火焚天诀", "attr": "attack", "bonus": 0.12, "desc": "火系炼器功法，攻击加成"},
        {"id": "sanmei_zhenhuo", "name": "三昧真火诀", "attr": "cultivation", "bonus": 0.14, "desc": "火系真火功法，修炼加成"},
    ],
    "土": [
        {"id": "houtu_jue", "name": "厚土诀", "attr": "defense", "bonus": 0.12, "desc": "土系防御功法，防御加成"},
        {"id": "dadi_jgt", "name": "大地金刚体", "attr": "hp", "bonus": 0.14, "desc": "土系肉身功法，气血加成"},
        {"id": "houtu_zhong", "name": "厚土重岳诀", "attr": "attack", "bonus": 0.12, "desc": "土系重岳功法，攻击加成"},
    ],
    "雷": [
        {"id": "jiuxiao_sl", "name": "九霄神雷诀", "attr": "attack", "bonus": 0.16, "desc": "雷系爆发功法，攻击加成"},
        {"id": "tianlei_zf", "name": "天雷正法", "attr": "cultivation", "bonus": 0.12, "desc": "雷系镇邪功法，修炼加成"},
        {"id": "wulei_zhenfa", "name": "五雷正法", "attr": "defense", "bonus": 0.12, "desc": "雷系护体功法，防御加成"},
    ],
    "魔": [
        {"id": "shitian_mg", "name": "噬天魔功", "attr": "cultivation", "bonus": 0.20, "desc": "魔系速成功法，修炼加成"},
        {"id": "xuemai_da", "name": "血魔大法", "attr": "attack", "bonus": 0.15, "desc": "魔系血炼功法，攻击加成"},
        {"id": "modao_zhuzhou", "name": "魔道咒印", "attr": "defense", "bonus": 0.12, "desc": "魔系咒印功法，防御加成"},
    ],
    "风": [
        {"id": "fenglun_jj", "name": "风轮剑诀", "attr": "attack", "bonus": 0.14, "desc": "风系灵动剑法，攻击加成"},
        {"id": "yufeng_shu", "name": "御风术", "attr": "cultivation", "bonus": 0.12, "desc": "风系身法功法，修炼加成"},
    ],
    "冰": [
        {"id": "hanbing_jue", "name": "寒冰诀", "attr": "attack", "bonus": 0.12, "desc": "冰系寒冰功法，攻击加成"},
        {"id": "xuanyin_bt", "name": "玄冰罩体", "attr": "defense", "bonus": 0.14, "desc": "冰系护体功法，防御加成"},
    ],
    "暗": [
        {"id": "yinsha_dun", "name": "隐煞遁法", "attr": "attack", "bonus": 0.16, "desc": "暗系隐匿功法，攻击加成"},
        {"id": "mingyan_gong", "name": "冥炎功", "attr": "cultivation", "bonus": 0.14, "desc": "暗系冥火功法，修炼加成"},
    ],
    "光": [
        {"id": "shengguang_jue", "name": "圣光诀", "attr": "hp", "bonus": 0.14, "desc": "光系圣光功法，气血加成"},
        {"id": "guangyao_hufa", "name": "光耀护法", "attr": "defense", "bonus": 0.12, "desc": "光系护体功法，防御加成"},
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
    "灵药谷": {"multiplier": 2.0, "risk": 0.15, "desc": "灵药遍地，炼丹玩家最爱"},
    "万妖山": {"multiplier": 2.8, "risk": 0.30, "desc": "群妖汇聚，妖丹材料丰富"},
    "星辰殿": {"multiplier": 3.0, "risk": 0.25, "desc": "星辉洒落，观星悟道之地"},
    "远古战场": {"multiplier": 3.2, "risk": 0.35, "desc": "上古战场遗迹，神兵传承无数"},
    "幽冥深渊": {"multiplier": 3.8, "risk": 0.45, "desc": "深不见底的凶险深渊，收益惊人"},
}

# 妖兽暴动事件对妖兽森林的额外收益/风险加成
FOREST_EVENT_MULT = 1.5
FOREST_EVENT_RISK_ADD = 0.10

# 限时开放地点 → 对应世界事件（不在映射中的地点常开，如洞府/灵脉/妖兽森林）
LOCATION_EVENTS = {
    "秘境": "shanggu_mijing",
    "灵药谷": "tianjiang_lingyu",
    "万妖山": "wanshou_caozong",
    "星辰殿": "tiandi_yixiang",
    "远古战场": "daoyun_miman",
    "幽冥深渊": "mochao_xiongyong",
}

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
    {"id": "tongtian_ti", "name": "通天神体", "rate": 0.20, "weight": 12, "desc": "天地亲和，修炼速度大增"},
    {"id": "hundun_ti", "name": "混沌体", "rate": 0.10, "weight": 8, "desc": "混沌初开之体，全属性大幅提升"},
    {"id": "jianxin_tm", "name": "剑心通明", "rate": 0.10, "weight": 10, "desc": "剑道通神，攻击大幅提升"},
    {"id": "jiuqiao_lt", "name": "九窍玲珑心", "rate": 0.10, "weight": 12, "desc": "七窍玲珑，炼丹炼器天赋异禀"},
    {"id": "wanling_st", "name": "万灵圣体", "rate": 0.10, "weight": 10, "desc": "万灵亲和，灵宠收益翻倍"},
    {"id": "yinyang_wx", "name": "阴阳五行体", "rate": 0.12, "weight": 10, "desc": "阴阳调和五行，修炼均衡加成"},
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
#   attack/defense/hp  服用增加对应属性
#   upgrade_quality  服用灵根品质提升一级
#   breakthrough 突破时提高成功率
#   pet_exp     喂养灵宠提升经验
ITEMS = {
    "lingcao": {"name": "灵草", "type": "material", "desc": "炼丹基础材料"},
    "yaodan": {"name": "妖丹", "type": "material", "desc": "妖兽体内凝聚的精华"},
    "lingquan": {"name": "灵泉", "type": "material", "desc": "天地灵气凝结的泉水"},
    "xuantie": {"name": "玄铁", "type": "material", "desc": "炼器常用材料"},
    "zijinsha": {"name": "紫金砂", "type": "material", "desc": "高阶炼器材料，锻造必备"},
    "shoupi": {"name": "兽皮", "type": "material", "desc": "妖兽皮毛，炼器材料"},
    "longxiancao": {"name": "龙涎草", "type": "material", "desc": "高阶炼丹材料"},
    "xingchenshi": {"name": "星辰石", "type": "material", "desc": "天外陨铁，稀有炼器材料"},
    "qiannian_ls": {"name": "千年灵参", "type": "material", "desc": "稀有炼丹材料"},
    "xiulian_dan": {"name": "修炼丹", "type": "pill", "desc": "服用后获得修为", "effect": {"progress": 500}},
    "jusan_san": {"name": "聚气散", "type": "pill", "desc": "低阶丹药，性价比最高的基础修为丹", "effect": {"progress": 400}},
    "ningshen_dan": {"name": "凝神丹", "type": "pill", "desc": "中阶丹药，服用增加大量修为", "effect": {"progress": 800}},
    "peiyuan_dan": {"name": "培元丹", "type": "pill", "desc": "高阶丹药，服用暴增修为", "effect": {"progress": 2000}},
    "wudao_dan": {"name": "悟道丹", "type": "pill", "desc": "传说丹药，服用修为暴涨", "effect": {"progress": 5000}},
    "yunlun_dan": {"name": "蕴神丹", "type": "pill", "desc": "稀有丹药，服用增加气运", "effect": {"fortune": 120}},
    "tianji_dan": {"name": "天机丹", "type": "pill", "desc": "传说丹药，服用大幅增加气运", "effect": {"fortune": 200}},
    "dali_wan": {"name": "大力丸", "type": "pill", "desc": "服用后力量大增，攻击永久+20", "effect": {"attack": 20}},
    "jingang_dan": {"name": "金刚丹", "type": "pill", "desc": "服用后铜皮铁骨，防御永久+20", "effect": {"defense": 20}},
    "qixue_dan": {"name": "气血丹", "type": "pill", "desc": "服用后气血充盈，气血上限+200", "effect": {"hp": 200}},
    "xisui_dan": {"name": "洗髓丹", "type": "pill", "desc": "服用后洗髓伐骨，灵根品质提升一级", "effect": {"upgrade_quality": True}},
    "tianling_dan": {"name": "天灵丹", "type": "pill", "desc": "天道灵韵凝聚，服用后灵根品质提升一级", "effect": {"upgrade_quality": True}},
    "pojing_dan": {"name": "破境丹", "type": "pill", "desc": "突破时使用可大幅提高成功率", "effect": {"breakthrough": 0.15}},
    "huiling_dan": {"name": "回灵丹", "type": "pill", "desc": "服用后恢复气血", "effect": {"heal": 100}},
    "dahuan_dan": {"name": "大还丹", "type": "pill", "desc": "服用后气血全满", "effect": {"heal_full": True}},
    "niepan_dan": {"name": "涅槃丹", "type": "pill", "desc": "归西状态下服用立即复活", "effect": {"revive": True}},
    "kuangbao_dan": {"name": "狂暴丹", "type": "pill", "desc": "下次PK战力+50%，但PK后额外扣自己血量", "effect": {"pk_boost": 0.5, "hp_cost": 150}},
    "jingyuan_dan": {"name": "精元丹", "type": "pill", "desc": "喂养灵宠可提升其经验", "effect": {"pet_exp": 100}},
    "ningpo_dan": {"name": "凝魄丹", "type": "pill", "desc": "喂养灵宠可获得大量经验", "effect": {"pet_exp": 500}},
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
    "ring": {"name": "戒指", "stat": "attack"},
    "boots": {"name": "战靴", "stat": "defense"},
}

# 炼丹消耗与产物
ALCHEMY_RECIPES = {
    "xiulian_dan": {"materials": {"lingcao": 2}, "cost": 20},
    "jusan_san": {"materials": {"lingcao": 2}, "cost": 30},
    "ningshen_dan": {"materials": {"lingcao": 2, "lingquan": 1}, "cost": 80},
    "peiyuan_dan": {"materials": {"lingcao": 3, "lingquan": 1, "yaodan": 1}, "cost": 200},
    "wudao_dan": {"materials": {"lingcao": 3, "lingquan": 2, "qiannian_ls": 1}, "cost": 500},
    "yunlun_dan": {"materials": {"lingquan": 2, "yaodan": 1}, "cost": 150},
    "tianji_dan": {"materials": {"lingquan": 2, "yaodan": 2}, "cost": 400},
    "dali_wan": {"materials": {"lingcao": 2, "yaodan": 1}, "cost": 40},
    "jingang_dan": {"materials": {"lingcao": 2, "xuantie": 1}, "cost": 40},
    "qixue_dan": {"materials": {"lingcao": 1, "lingquan": 1, "shoupi": 1}, "cost": 40},
    "xisui_dan": {"materials": {"lingcao": 3, "longxiancao": 2, "yaodan": 2}, "cost": 800},
    "pojing_dan": {"materials": {"lingcao": 2, "yaodan": 1}, "cost": 60},
    "huiling_dan": {"materials": {"lingcao": 1, "lingquan": 1}, "cost": 20},
    "dahuan_dan": {"materials": {"lingcao": 2, "lingquan": 2}, "cost": 100},
    "niepan_dan": {"materials": {"longxiancao": 1, "xingchenshi": 1}, "cost": 200},
    "kuangbao_dan": {"materials": {"lingcao": 2, "xuantie": 2, "yaodan": 1}, "cost": 150},
    "jingyuan_dan": {"materials": {"yaodan": 2}, "cost": 30},
    "ningpo_dan": {"materials": {"yaodan": 2, "xingchenshi": 1}, "cost": 80},
}

# 炼器消耗
FORGE_COST = {"materials": {"lingcao": 2, "yaodan": 2, "lingquan": 1, "xuantie": 1, "zijinsha": 1}, "cost": 100}

# ==================== 世界事件系统 ====================

# 世界事件：id 为事件标识，rate 为修炼速度倍率，breakthrough 为突破成功率加成，
# forest 为妖兽森林收益倍率，risk 为妖兽森林额外风险，enlighten 为顿悟概率加成，explore_luck 为探索奇遇倍率
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
        "opens_secret_realm": True,
        "desc": "上古秘境开启，全服玩家可进入探索，获得稀有功法、装备、材料",
    },
    "tiandi_yixiang": {
        "name": "天地异象",
        "explore_luck": 1.5,
        "desc": "天地异象频生，星辰殿开启，可能触发隐藏任务、特殊NPC、神秘传承",
    },
    "tianjiang_lingyu": {
        "name": "天降灵雨",
        "rate": 1.3,
        "desc": "灵雨滋润大地，全服修炼速度提升30%，灵药谷灵药疯长",
    },
    "daoyun_miman": {
        "name": "道韵弥漫",
        "rate": 1.1,
        "breakthrough": 0.05,
        "enlighten": 0.05,
        "desc": "道韵弥漫天地，修炼提升10%，突破成功率提升5%，远古战场浮现",
    },
    "wanshou_caozong": {
        "name": "万兽朝宗",
        "forest": 1.8,
        "desc": "万兽朝宗，妖兽森林收益提升80%，万妖山群妖汇聚",
    },
    "xianyuan_jianglin": {
        "name": "仙缘降临",
        "explore_luck": 2.0,
        "desc": "仙缘遍地，探索更容易触发奇遇与稀有奖励",
    },
    "mochao_xiongyong": {
        "name": "魔潮汹涌",
        "forest": 2.0,
        "risk": 0.15,
        "desc": "魔潮汹涌，妖兽森林收益翻倍但遇险概率大增，幽冥深渊开启",
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
    {"item_id": "zijinsha", "price": 250},
    {"item_id": "jusan_san", "price": 100},
    {"item_id": "xiulian_dan", "price": 200},
    {"item_id": "ningshen_dan", "price": 500},
    {"item_id": "peiyuan_dan", "price": 1500},
    {"item_id": "wudao_dan", "price": 3000},
    {"item_id": "yunlun_dan", "price": 400},
    {"item_id": "tianji_dan", "price": 1500},
    {"item_id": "dali_wan", "price": 300},
    {"item_id": "jingang_dan", "price": 300},
    {"item_id": "qixue_dan", "price": 300},
    {"item_id": "xisui_dan", "price": 5000},
    {"item_id": "pojing_dan", "price": 300},
    {"item_id": "jingyuan_dan", "price": 150},
    {"item_id": "ningpo_dan", "price": 400},
    {"item_id": "huiling_dan", "price": 100},
    {"item_id": "dahuan_dan", "price": 500},
    {"item_id": "niepan_dan", "price": 1000},
    {"item_id": "kuangbao_dan", "price": 800},
]

# 商城回购价格（玩家将材料/丹药卖给商城换灵石）
# 平衡规则：回购价约为商城售价的 60%，避免低买高卖刷灵石
SHOP_BUYBACK = {
    "lingcao": 50,
    "yaodan": 100,
    "lingquan": 120,
    "xuantie": 200,
    "zijinsha": 250,
    "shoupi": 150,
    "longxiancao": 300,
    "xingchenshi": 400,
    "qiannian_ls": 500,
    "jusan_san": 60,
    "xiulian_dan": 120,
    "ningshen_dan": 300,
    "peiyuan_dan": 900,
    "wudao_dan": 1800,
    "yunlun_dan": 240,
    "tianji_dan": 900,
    "dali_wan": 180,
    "jingang_dan": 180,
    "qixue_dan": 180,
    "xisui_dan": 3000,
    "tianling_dan": 3000,
    "pojing_dan": 180,
    "huiling_dan": 60,
    "jingyuan_dan": 90,
    "ningpo_dan": 240,
    "dahuan_dan": 300,
    "niepan_dan": 600,
    "kuangbao_dan": 480,
}

# 装备按品质回购（武器/法袍/法宝/戒指/战靴统一价格）
EQUIP_BUYBACK = {"普通": 150, "优秀": 400, "极品": 1000, "灵器": 2500, "仙器": 6000}

# ==================== 修炼/战斗基础数值 ====================

# 基础属性
BASE_ATTACK = 10
BASE_DEFENSE = 10
BASE_HP = 100

# 闭关灵石收益：每小时灵石 = COIN_PER_HOUR_BASE + 修炼速率 * COIN_PER_RATE
COIN_PER_HOUR_BASE = 5
COIN_PER_RATE = 0.1

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

# 双修修为收益：当前境界容量的百分比
XIUXIU_PROGRESS_RATE = 0.05

# 丹药效果递减：同种修为丹药每次服用效果下降的步长，最低降至
PILL_DIMINISH_STEP = 0.125
PILL_DIMINISH_MIN = 0.5

# 突破失败产生的瓶颈冷却时间（分钟），期间无法再次突破
BOTTLENECK_MINUTES = 30

# ==================== 探索奇遇系统 ====================

# 探索时触发奇遇的基础概率
ENCOUNTER_CHANCE = 0.25

# 探索奇遇池：每次探索可能随机触发其一
# success: items(材料/丹药) / progress(修为) / coins(灵石) / pet(灵宠) / equip(装备) / gongfa_exp(功法熟练度)
# fail: damage(血量比例) / lose_coins(丢失灵石)
ENCOUNTERS = [
    {
        "name": "山涧仙泉",
        "weight": 15,
        "desc": "你在山涧中发现一汪冒着灵气的仙泉，波光粼粼，沁人心脾",
        "success_chance": 0.70,
        "success": {"items": {"lingquan": 3}, "progress": 300, "text": "你捧起泉水痛饮，灵气涌入四肢百骸，修为精进！"},
        "fail": {"damage": 0.15, "text": "泉水暗藏瘴毒，你饮下后头晕目眩，中毒受伤！"},
    },
    {
        "name": "神秘洞府",
        "weight": 12,
        "desc": "你发现一处前人留下的神秘洞府，石门半掩，内有宝光闪烁",
        "success_chance": 0.65,
        "success": {"equip": True, "coins": 100, "text": "你在洞府深处寻得一件神兵与灵石，满载而归！"},
        "fail": {"damage": 0.15, "lose_coins": 80, "text": "洞府年久失修轰然崩塌，你被落石砸伤，还丢了灵石！"},
    },
    {
        "name": "云游道人",
        "weight": 12,
        "desc": "一位仙风道骨的云游道人在你面前停下，含笑打量着你",
        "success_chance": 0.75,
        "success": {"gongfa_exp": 60, "progress": 500, "text": "道人见你资质不凡，口传玄妙口诀，你功法精进、修为大涨！"},
        "fail": {"lose_coins": 100, "text": "道人摇头叹息「缘分未到」，飘然而去，你还丢了灵石！"},
    },
    {
        "name": "灵兽幼崽",
        "weight": 10,
        "desc": "你发现一只受伤的灵兽幼崽，可怜巴巴地望着你",
        "success_chance": 0.60,
        "success": {"pet": True, "text": "你悉心照料，灵兽幼崽认你为主！"},
        "fail": {"damage": 0.20, "text": "幼崽的父母突然杀到，护犊心切，将你重创！"},
    },
    {
        "name": "天材地宝",
        "weight": 12,
        "desc": "你闻到一股浓郁药香，发现一株奇珍灵药正在生长",
        "success_chance": 0.65,
        "success": {"items": {"longxiancao": 1, "qiannian_ls": 1}, "text": "你小心翼翼采下灵药，药香扑鼻，收获颇丰！"},
        "fail": {"damage": 0.15, "lose_coins": 60, "text": "守护灵药的妖兽暴起袭击，你仓皇而逃，还丢了灵石！"},
    },
    {
        "name": "古道残碑",
        "weight": 10,
        "desc": "你发现一块刻满古老符文的残碑，隐隐透着大道韵味",
        "success_chance": 0.55,
        "success": {"progress": 800, "gongfa_exp": 100, "text": "你参悟残碑古纹，顿悟大道真意，修为暴涨！"},
        "fail": {"damage": 0.20, "lose_coins": 100, "text": "残碑突现诅咒之力，你心神受创，气血翻涌！"},
    },
    {
        "name": "遗落宝箱",
        "weight": 12,
        "desc": "你在草丛中发现一个古旧的宝箱，锁扣松动，隐隐透出金光",
        "success_chance": 0.65,
        "success": {"coins": 300, "equip": True, "text": "你撬开宝箱，灵石与一件法宝尽入囊中！"},
        "fail": {"damage": 0.10, "lose_coins": 150, "text": "宝箱竟是一个机关陷阱，毒雾喷出，你狼狈逃离！"},
    },
    {
        "name": "星辰坠落",
        "weight": 10,
        "desc": "天际划过一道流星，轰然坠落在不远处，扬起漫天烟尘",
        "success_chance": 0.60,
        "success": {"items": {"xingchenshi": 2}, "coins": 200, "text": "你抢在众人之前赶到，拾得星辰石与灵石！"},
        "fail": {"damage": 0.25, "text": "陨石携带灼热天火，你躲避不及被炸得遍体鳞伤！"},
    },
    {
        "name": "天地灵根",
        "weight": 6,
        "desc": "你感应到一缕天道灵韵，似有灵根在此处悄然孕育",
        "success_chance": 0.55,
        "success": {"items": {"tianling_dan": 1}, "progress": 200, "text": "你寻得天地灵根凝聚的天灵丹，药香绕体三日不散！"},
        "fail": {"damage": 0.15, "text": "灵根灵性反噬，你气血翻涌，受伤不轻！"},
    },
]

# ==================== 负面状态（Debuff）系统 ====================

# 可扩展的负面状态定义：新增一种状态只需在此添加一项，并在需要的逻辑处挂接效果。
# 效果字段：
#   rate            修炼速率加成（负数=降低）
#   fortune         气运减益（倒霉状态）
#   damage_tick     持续掉血（每小时血量，中毒类）
#   block_cultivate 是否禁止闭关
DEBUFFS = {
    "daomei": {
        "name": "霉运缠身",
        "desc": "诸事不顺，喝水塞牙，气运大跌",
        "duration": 180,
        "fortune": -500,
        "rate": -0.05,
    },
    "shenti_touzhi": {
        "name": "身体透支",
        "desc": "双修过度，元气大伤，修炼受阻",
        "duration": 120,
        "rate": -0.20,
    },
    "danyao_zhongdu": {
        "name": "丹药中毒",
        "desc": "丹药服食过多，体内淤毒，触发时立即损失修为并持续掉血",
        "duration": 120,
        "rate": -0.10,
        "damage_tick": 5,
    },
    "zouhuo_rumo": {
        "name": "走火入魔",
        "desc": "闭关过久气血逆行，心神紊乱，无法修炼",
        "duration": 180,
        "rate": -0.30,
        "block_cultivate": True,
    },
}

# 各 debuff 触发概率
DEBUFF_TRIGGER = {
    "xiuxiu_shenti_touzhi": 0.20,   # 每次双修触发身体透支
    "pill_zhongdu_base": 0.05,      # 服用丹药中毒基础概率
    "zouhuo": 0.30,                 # 闭关超时走火入魔
    "pk_fail_daomei": 0.30,         # PK 落败触发霉运
    "breakthrough_fail_daomei": 0.25,  # 突破失败触发霉运
}

# 丹药中毒触发时立即损失的修为比例
PILL_POISON_PROGRESS_LOSS = 0.10
