from pathlib import Path

from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class Config(BaseModel):
    # 是否开启每日自动同步
    meme_sync_enabled: bool = True
    # 每天几点几分执行（按 meme_sync_timezone 计时）
    meme_sync_hour: int = 0
    meme_sync_minute: int = 0
    meme_sync_timezone: str = "Asia/Shanghai"
    # 并发数与单张超时
    meme_sync_workers: int = 8
    meme_sync_timeout: float = 30.0
    # 下载入口：auto 自动探测 / direct 直连 / p0 p1 p2 指定镜像
    meme_sync_route: str = "auto"
    # 可选筛选：只同步指定角色或分类，留空表示全部
    meme_sync_chars: str = ""
    meme_sync_subs: str = ""
    # 图片保存位置
    meme_sync_out_dir: Path = DATA_DIR / "naihub-img"

    # 开启奶龙表情包功能的群号（也可在群里用 /开启奶龙 动态开关）
    meme_group_ids: list[int] = []
    # AI 回复附带一张随机表情包的概率（1.0 表示每条都带）
    meme_attach_chance: float = 1.0
    # 回复群友之后，额外单独发一张表情包的概率（不回复任何人，直接发群里）
    meme_standalone_chance: float = 0.2
    # 主动冒泡消息是否也附带表情包
    meme_bubble_attach: bool = True
    # 群开关状态文件
    meme_groups_file: Path = DATA_DIR / "meme_sync" / "groups.json"
    # 手动触发同步的管理员 QQ
    admin_qq: int = 1154798056
