from pathlib import Path

from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class Config(BaseModel):
    """存表情配置"""

    # 图片保存根目录：留空 = 直接存进奶龙表情库（data/naihub-img），
    # 存完立刻能被 /今日奶龙 和开启奶龙后的 AI 跟图抽到；
    # 写一个目录则存到那里，比如 data/saved_images
    save_meme_root: str = ""
    # 单张图片体积上限（字节），超过的跳过，0 表示不限制
    save_meme_max_bytes: int = 20 * 1024 * 1024
    # 能使用这个功能的管理员 QQ
    admin_qq: int = 1154798056
