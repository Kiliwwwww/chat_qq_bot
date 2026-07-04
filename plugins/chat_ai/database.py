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
                        keyword TEXT PRIMARY KEY,
                        meaning TEXT NOT NULL,
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
                conn.commit()
                logger.info("数据库初始化完成")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")

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

    def add_keyword(self, keyword: str, meaning: str) -> bool:
        """添加或更新关键词映射"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO keywords (keyword, meaning) VALUES (?, ?)",
                    (keyword, meaning),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"添加关键词失败: {e}")
            return False

    def remove_keyword(self, keyword: str) -> bool:
        """删除关键词映射"""
        try:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM keywords WHERE keyword = ?", (keyword,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"删除关键词失败: {e}")
            return False

    def get_all_keywords(self) -> dict[str, str]:
        """获取所有关键词映射"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT keyword, meaning FROM keywords")
                return {row["keyword"]: row["meaning"] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"获取关键词失败: {e}")
            return {}

    def keyword_exists(self, keyword: str) -> bool:
        """检查关键词是否存在"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM keywords WHERE keyword = ?", (keyword,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"检查关键词失败: {e}")
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
