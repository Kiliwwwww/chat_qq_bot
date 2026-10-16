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
    # 手动触发同步的管理员 QQ
    admin_qq: int = 1154798056
