import json
import random
import os
import redis
from datetime import datetime, timedelta
import logging

# 使用标准logging而不是nonebot.logger
logger = logging.getLogger(__name__)


class PigManager:
    """猪猪管理器，使用Redis存储每日猪猪结果"""
    
    def __init__(self, config):
        self.redis_client = None
        self.pig_list = []
        
        # 初始化Redis连接
        try:
            self.redis_client = redis.Redis(
                host=config.redis_host,
                port=config.redis_port,
                db=config.redis_db,
                password=config.redis_password if config.redis_password else None,
                decode_responses=config.redis_decode_responses,
            )
            self.redis_client.ping()
            logger.info("Daily Pig Redis 连接成功")
        except Exception as e:
            logger.error(f"Daily Pig Redis 连接失败: {e}，每日猪猪功能将不可用")
            self.redis_client = None
        
        # 加载猪猪数据
        self._load_pig_data()
    
    def _load_pig_data(self):
        """从pig.json加载猪猪数据"""
        try:
            # 获取项目根目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            pig_json_path = os.path.join(project_root, "data", "pig.json")
            
            with open(pig_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.pig_list = data.get("list", [])
            
            logger.info(f"成功加载 {len(self.pig_list)} 个猪猪数据")
        except Exception as e:
            logger.error(f"加载猪猪数据失败: {e}")
            self.pig_list = []
    
    def _get_daily_pig_key(self, user_id: int, group_id: int) -> str:
        """获取每日猪猪的Redis key（包含日期和群ID）"""
        today = datetime.now().strftime("%Y%m%d")
        return f"daily_pig:result:{today}:{group_id}:{user_id}"
    
    def get_daily_pig(self, user_id: int, group_id: int) -> dict | None:
        """获取用户指定群今日的猪猪结果"""
        if self.redis_client is None:
            return None
        try:
            key = self._get_daily_pig_key(user_id, group_id)
            pig_data = self.redis_client.get(key)
            if pig_data:
                return json.loads(pig_data)
            return None
        except Exception as e:
            logger.error(f"获取每日猪猪失败: {e}")
            return None
    
    def set_daily_pig(self, user_id: int, group_id: int, pig_data: dict) -> bool:
        """保存用户指定群今日的猪猪结果（到当天24点过期）"""
        if self.redis_client is None:
            return False
        try:
            key = self._get_daily_pig_key(user_id, group_id)
            # 计算到当天24点的秒数
            now = datetime.now()
            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            expire_seconds = int((tomorrow - now).total_seconds())
            
            self.redis_client.setex(key, expire_seconds, json.dumps(pig_data, ensure_ascii=False))
            return True
        except Exception as e:
            logger.error(f"保存每日猪猪失败: {e}")
            return False
    
    def get_random_pig(self) -> dict | None:
        """随机获取一个猪猪"""
        if not self.pig_list:
            return None
        
        pig = random.choice(self.pig_list)
        
        # 检查图片文件是否存在
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        img_path = os.path.join(project_root, "data", "pighub-img", pig["name"])
        
        if os.path.exists(img_path):
            return {
                "name": pig["name"],
                "explan": pig["explan"],
                "img_path": img_path
            }
        else:
            logger.warning(f"猪猪图片不存在: {img_path}")
            # 如果图片不存在，继续随机选择
            return self.get_random_pig()
