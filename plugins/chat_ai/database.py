import sqlite3
from pathlib import Path
from typing import Optional

from nonebot import logger


class Database:
    """SQLite 数据库管理类"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """初始化数据库表"""
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS whitelist (
                        user_id INTEGER PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS group_whitelist (
                        group_id INTEGER PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS keywords (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        content TEXT NOT NULL UNIQUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS welcome_messages (
                        group_id INTEGER PRIMARY KEY,
                        message TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ad_keywords (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        keyword TEXT NOT NULL UNIQUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ai_services (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        api_key TEXT NOT NULL,
                        base_url TEXT NOT NULL,
                        model TEXT NOT NULL,
                        is_active INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ad_recall_groups (
                        group_id INTEGER PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS group_kb_config (
                        group_id INTEGER PRIMARY KEY,
                        kb_id TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS statistics (
                        key TEXT PRIMARY KEY,
                        count INTEGER DEFAULT 0,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                self._init_default_ad_keywords(conn)
                logger.info("数据库初始化完成")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")

    def _init_default_ad_keywords(self, conn: sqlite3.Connection) -> None:
        """初始化默认广告关键词（仅在表为空时插入）"""
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM ad_keywords")
            count = cursor.fetchone()[0]
            if count > 0:
                return

            default_keywords = [
                "加微信", "加好友", "加V", "加vx", "加wx",
                "扫码", "二维码", "长按识别",
                "兼职", "日结", "日入", "日赚", "躺赚",
                "代理", "加盟", "招商", "招代理",
                "优惠", "促销", "特价", "秒杀", "抢购",
                "刷单", "好评返现", "返利",
                "免费领", "免费送", "0元",
                "进群", "拉群", "加群",
                "网贷", "贷款", "借钱", "下款",
                "博彩", "彩票", "赌", "开奖",
                "数字货币", "虚拟币", "比特币", "USDT",
                "色情", "约炮", "小姐姐",
            ]
            conn.executemany(
                "INSERT OR IGNORE INTO ad_keywords (keyword) VALUES (?)",
                [(kw,) for kw in default_keywords]
            )
            conn.commit()
            logger.info(f"已初始化 {len(default_keywords)} 个默认广告关键词")
        except Exception as e:
            logger.error(f"初始化默认广告关键词失败: {e}")

    def get_all_users(self) -> set[int]:
        """获取所有白名单用户"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT user_id FROM whitelist")
                return {row["user_id"] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"获取白名单失败: {e}")
            return set()

    def add_user(self, user_id: int) -> bool:
        """添加用户到白名单"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)",
                    (user_id,),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"添加用户失败: {e}")
            return False

    def remove_user(self, user_id: int) -> bool:
        """从白名单移除用户"""
        try:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM whitelist WHERE user_id = ?", (user_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"移除用户失败: {e}")
            return False

    def user_exists(self, user_id: int) -> bool:
        """检查用户是否在白名单中"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM whitelist WHERE user_id = ?", (user_id,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"检查用户失败: {e}")
            return False

    def get_all_groups(self) -> set[int]:
        """获取所有白名单群"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT group_id FROM group_whitelist")
                return {row["group_id"] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"获取群白名单失败: {e}")
            return set()

    def add_group(self, group_id: int) -> bool:
        """添加群到白名单"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO group_whitelist (group_id) VALUES (?)",
                    (group_id,),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"添加群失败: {e}")
            return False

    def remove_group(self, group_id: int) -> bool:
        """从白名单移除群"""
        try:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM group_whitelist WHERE group_id = ?", (group_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"移除群失败: {e}")
            return False

    def group_exists(self, group_id: int) -> bool:
        """检查群是否在白名单中"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM group_whitelist WHERE group_id = ?", (group_id,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"检查群失败: {e}")
            return False

    def add_keyword(self, content: str) -> bool:
        """添加提示词"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO keywords (content) VALUES (?)",
                    (content,),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"添加提示词失败: {e}")
            return False

    def remove_keyword(self, keyword_id: int) -> bool:
        """通过 ID 删除提示词"""
        try:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"删除提示词失败: {e}")
            return False

    def get_all_keywords(self) -> list[dict]:
        """获取所有提示词"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT id, content FROM keywords ORDER BY id")
                return [{"id": row["id"], "content": row["content"]} for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取提示词失败: {e}")
            return []

    def keyword_exists(self, content: str) -> bool:
        """检查提示词是否存在"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM keywords WHERE content = ?", (content,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"检查提示词失败: {e}")
            return False

    def keyword_id_exists(self, keyword_id: int) -> bool:
        """检查提示词 ID 是否存在"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM keywords WHERE id = ?", (keyword_id,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"检查提示词 ID 失败: {e}")
            return False

    def get_setting(self, key: str, default: str = "") -> str:
        """获取设置值"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT value FROM settings WHERE key = ?", (key,)
                )
                row = cursor.fetchone()
                return row["value"] if row else default
        except Exception as e:
            logger.error(f"获取设置失败: {e}")
            return default

    def set_setting(self, key: str, value: str) -> bool:
        """保存设置值"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (key, value),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"保存设置失败: {e}")
            return False

    def get_all_welcome_messages(self) -> dict[int, str]:
        """获取所有群欢迎语"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT group_id, message FROM welcome_messages")
                return {row["group_id"]: row["message"] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"获取欢迎语失败: {e}")
            return {}

    def set_welcome_message(self, group_id: int, message: str) -> bool:
        """设置群欢迎语"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO welcome_messages (group_id, message, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (group_id, message),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"设置欢迎语失败: {e}")
            return False

    def remove_welcome_message(self, group_id: int) -> bool:
        """删除群欢迎语"""
        try:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM welcome_messages WHERE group_id = ?", (group_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"删除欢迎语失败: {e}")
            return False

    def get_welcome_message(self, group_id: int) -> Optional[str]:
        """获取指定群的欢迎语"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT message FROM welcome_messages WHERE group_id = ?", (group_id,)
                )
                row = cursor.fetchone()
                return row["message"] if row else None
        except Exception as e:
            logger.error(f"获取欢迎语失败: {e}")
            return None

    def add_ad_keyword(self, keyword: str) -> bool:
        """添加广告关键词"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO ad_keywords (keyword) VALUES (?)",
                    (keyword,),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"添加广告关键词失败: {e}")
            return False

    def remove_ad_keyword(self, keyword_id: int) -> bool:
        """通过 ID 删除广告关键词"""
        try:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM ad_keywords WHERE id = ?", (keyword_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"删除广告关键词失败: {e}")
            return False

    def get_all_ad_keywords(self) -> list[dict]:
        """获取所有广告关键词"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT id, keyword FROM ad_keywords ORDER BY id")
                return [{"id": row["id"], "keyword": row["keyword"]} for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取广告关键词失败: {e}")
            return []

    def ad_keyword_exists(self, keyword: str) -> bool:
        """检查广告关键词是否存在"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM ad_keywords WHERE keyword = ?", (keyword,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"检查广告关键词失败: {e}")
            return False

    # ==================== 广告撤回群管理 ====================

    def get_all_ad_recall_groups(self) -> set[int]:
        """获取所有开启广告撤回的群"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT group_id FROM ad_recall_groups")
                return {row["group_id"] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"获取广告撤回群列表失败: {e}")
            return set()

    def add_ad_recall_group(self, group_id: int) -> bool:
        """添加群到广告撤回列表"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO ad_recall_groups (group_id) VALUES (?)",
                    (group_id,),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"添加广告撤回群失败: {e}")
            return False

    def remove_ad_recall_group(self, group_id: int) -> bool:
        """从广告撤回列表移除群"""
        try:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM ad_recall_groups WHERE group_id = ?", (group_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"移除广告撤回群失败: {e}")
            return False

    def ad_recall_group_exists(self, group_id: int) -> bool:
        """检查群是否开启广告撤回"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM ad_recall_groups WHERE group_id = ?", (group_id,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"检查广告撤回群失败: {e}")
            return False

    # ==================== AI 服务管理 ====================
    
    def add_ai_service(self, name: str, api_key: str, base_url: str, model: str) -> bool:
        """添加 AI 服务配置"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO ai_services (name, api_key, base_url, model) VALUES (?, ?, ?, ?)",
                    (name, api_key, base_url, model),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"添加 AI 服务失败: {e}")
            return False

    def remove_ai_service(self, service_id: int) -> bool:
        """删除 AI 服务配置"""
        try:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM ai_services WHERE id = ?", (service_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"删除 AI 服务失败: {e}")
            return False

    def get_all_ai_services(self) -> list[dict]:
        """获取所有 AI 服务配置"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT id, name, api_key, base_url, model, is_active FROM ai_services ORDER BY id"
                )
                return [
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "api_key": row["api_key"],
                        "base_url": row["base_url"],
                        "model": row["model"],
                        "is_active": bool(row["is_active"]),
                    }
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            logger.error(f"获取 AI 服务列表失败: {e}")
            return []

    def get_active_ai_service(self) -> Optional[dict]:
        """获取当前激活的 AI 服务"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT id, name, api_key, base_url, model FROM ai_services WHERE is_active = 1"
                )
                row = cursor.fetchone()
                if row:
                    return {
                        "id": row["id"],
                        "name": row["name"],
                        "api_key": row["api_key"],
                        "base_url": row["base_url"],
                        "model": row["model"],
                    }
                return None
        except Exception as e:
            logger.error(f"获取激活 AI 服务失败: {e}")
            return None

    def set_active_ai_service(self, service_id: int) -> bool:
        """设置激活的 AI 服务"""
        try:
            with self._get_conn() as conn:
                # 先取消所有激活状态
                conn.execute("UPDATE ai_services SET is_active = 0")
                # 设置指定服务为激活
                conn.execute(
                    "UPDATE ai_services SET is_active = 1 WHERE id = ?",
                    (service_id,),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"设置激活 AI 服务失败: {e}")
            return False

    def ai_service_exists(self, service_id: int) -> bool:
        """检查 AI 服务是否存在"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM ai_services WHERE id = ?", (service_id,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"检查 AI 服务失败: {e}")
            return False

    # ==================== 知识库群配置管理 ====================

    def get_all_kb_groups(self) -> dict[int, str]:
        """获取所有开启知识库的群及其知识库ID"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT group_id, kb_id FROM group_kb_config")
                return {row["group_id"]: row["kb_id"] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"获取知识库群列表失败: {e}")
            return {}

    def add_kb_group(self, group_id: int, kb_id: str) -> bool:
        """添加群到知识库配置"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO group_kb_config (group_id, kb_id) VALUES (?, ?)",
                    (group_id, kb_id),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"添加知识库群失败: {e}")
            return False

    def remove_kb_group(self, group_id: int) -> bool:
        """从知识库配置移除群"""
        try:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM group_kb_config WHERE group_id = ?", (group_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"移除知识库群失败: {e}")
            return False

    def get_kb_id_by_group(self, group_id: int) -> str | None:
        """获取指定群的知识库ID"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT kb_id FROM group_kb_config WHERE group_id = ?", (group_id,)
                )
                row = cursor.fetchone()
                return row["kb_id"] if row else None
        except Exception as e:
            logger.error(f"获取群知识库ID失败: {e}")
            return None

    def kb_group_exists(self, group_id: int) -> bool:
        """检查群是否开启了知识库"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM group_kb_config WHERE group_id = ?", (group_id,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"检查知识库群失败: {e}")
            return False

    # ==================== 统计计数管理 ====================

    def increment_stat(self, key: str, amount: int = 1) -> bool:
        """增加指定统计项的计数"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO statistics (key, count, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
                    "ON CONFLICT(key) DO UPDATE SET count = count + ?, updated_at = CURRENT_TIMESTAMP",
                    (key, amount, amount),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"增加统计计数失败: {e}")
            return False

    def get_stat(self, key: str) -> int:
        """获取指定统计项的计数"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT count FROM statistics WHERE key = ?", (key,)
                )
                row = cursor.fetchone()
                return row["count"] if row else 0
        except Exception as e:
            logger.error(f"获取统计计数失败: {e}")
            return 0

    def get_all_stats(self) -> dict[str, int]:
        """获取所有统计数据"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT key, count FROM statistics")
                return {row["key"]: row["count"] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"获取统计数据失败: {e}")
            return {}
