from pathlib import Path

from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class Config(BaseModel):
    # 每个 QQ 用户每天的全局抽奖次数
    lottery_daily_limit: int = 3
    # GIF 动画时长与帧率
    lottery_gif_duration_ms: int = 3200
    lottery_gif_fps: int = 10
    lottery_gif_max_width: int = 500
    # 无头浏览器配置
    lottery_browser_timeout_ms: int = 20000
    lottery_browser_channel: str = ""
    lottery_timezone: str = "Asia/Shanghai"
    # 资源与输出位置
    lottery_html_path: Path = DATA_DIR / "lottery.html"
    lottery_items_path: Path = DATA_DIR / "sprite_objects" / "items.json"
    lottery_data_dir: Path = DATA_DIR / "lottery"
