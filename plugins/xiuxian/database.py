"""SQLite 数据库访问层。

所有游戏表都以 group_id 作为关键隔离维度，保证每个群的数据互相独立。
"""

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

from nonebot import logger


class Database:
    """修仙游戏数据库管理类"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    # ==================== 基础连接 ====================

    @contextmanager
    def _get_conn(self):
        """获取数据库连接（上下文管理器，自动提交并关闭连接）"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """初始化所有数据表"""
        try:
            with self._get_conn() as conn:
                conn.executescript(
                    """
                    -- 玩家角色表
                    CREATE TABLE IF NOT EXISTS players (
                        group_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        name TEXT DEFAULT '',
                        realm INTEGER NOT NULL DEFAULT 0,
                        realm_progress REAL NOT NULL DEFAULT 0,
                        spirit_root TEXT NOT NULL DEFAULT '',
                        spirit_quality TEXT NOT NULL DEFAULT '',
                        fortune INTEGER NOT NULL DEFAULT 1000,
                        physique TEXT DEFAULT '',
                        talent TEXT DEFAULT 'random',
                        attack INTEGER DEFAULT 10,
                        defense INTEGER DEFAULT 10,
                        hp INTEGER DEFAULT 100,
                        coin INTEGER DEFAULT 100,
                        alchemy_level INTEGER DEFAULT 1,
                        alchemy_exp INTEGER DEFAULT 0,
                        forge_level INTEGER DEFAULT 1,
                        forge_exp INTEGER DEFAULT 0,
                        bottleneck_until REAL DEFAULT 0,
                        weapon TEXT DEFAULT '',
                        armor TEXT DEFAULT '',
                        treasure TEXT DEFAULT '',
                        ring TEXT DEFAULT '',
                        boots TEXT DEFAULT '',
                        rebirth_count INTEGER DEFAULT 0,
                        cur_hp INTEGER DEFAULT 0,
                        dead_until REAL DEFAULT 0,
                        pk_boost REAL DEFAULT 0,
                        pk_hp_cost INTEGER DEFAULT 0,
                        xiuxiu_until REAL DEFAULT 0,
                        debuffs TEXT DEFAULT '',
                        created_at REAL NOT NULL,
                        PRIMARY KEY (group_id, user_id)
                    );

                    -- 挂机状态表
                    CREATE TABLE IF NOT EXISTS cultivation (
                        group_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        location TEXT NOT NULL,
                        started_at REAL NOT NULL,
                        PRIMARY KEY (group_id, user_id)
                    );

                    -- 功法持有表
                    CREATE TABLE IF NOT EXISTS gongfas (
                        group_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        gongfa_id TEXT NOT NULL,
                        level INTEGER NOT NULL DEFAULT 0,
                        exp REAL NOT NULL DEFAULT 0,
                        PRIMARY KEY (group_id, user_id, gongfa_id)
                    );

                    -- 背包表
                    CREATE TABLE IF NOT EXISTS inventory (
                        group_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        item_id TEXT NOT NULL,
                        quantity INTEGER NOT NULL DEFAULT 1,
                        PRIMARY KEY (group_id, user_id, item_id)
                    );

                    -- 灵宠表
                    CREATE TABLE IF NOT EXISTS pets (
                        group_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        pet_id INTEGER NOT NULL,
                        pet_type TEXT NOT NULL,
                        level INTEGER NOT NULL DEFAULT 1,
                        exp INTEGER NOT NULL DEFAULT 0,
                        evolution INTEGER NOT NULL DEFAULT 1,
                        name TEXT DEFAULT '',
                        PRIMARY KEY (group_id, user_id, pet_id)
                    );

                    -- 世界状态表（每个群一个世界）
                    CREATE TABLE IF NOT EXISTS world_state (
                        group_id INTEGER PRIMARY KEY,
                        weather TEXT DEFAULT '晴',
                        spirit_concentration REAL DEFAULT 1.0,
                        current_event TEXT DEFAULT '',
                        event_end_time REAL DEFAULT 0,
                        last_tick_time REAL DEFAULT 0,
                        merchant_end_time REAL DEFAULT 0,
                        breakthrough_merchant_end_time REAL DEFAULT 0,
                        secret_realm_end_time REAL DEFAULT 0
                    );

                    -- 世界事件日志表
                    CREATE TABLE IF NOT EXISTS world_events_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER NOT NULL,
                        event_type TEXT NOT NULL,
                        started_at REAL NOT NULL,
                        description TEXT DEFAULT ''
                    );

                    -- 师徒关系表
                    CREATE TABLE IF NOT EXISTS furnaces (
                        group_id INTEGER NOT NULL,
                        owner_id INTEGER NOT NULL,
                        target_id INTEGER NOT NULL,
                        started_at REAL NOT NULL,
                        PRIMARY KEY (group_id, owner_id, target_id)
                    );

                    -- 坊市挂单表
                    CREATE TABLE IF NOT EXISTS market_orders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id INTEGER NOT NULL,
                        seller_id INTEGER NOT NULL,
                        item_id TEXT NOT NULL,
                        quantity INTEGER NOT NULL DEFAULT 1,
                        price INTEGER NOT NULL,
                        created_at REAL NOT NULL,
                        status TEXT DEFAULT 'active'
                    );

                    -- 探索冷却表
                    CREATE TABLE IF NOT EXISTS explore_cooldown (
                        group_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        until_time REAL NOT NULL,
                        PRIMARY KEY (group_id, user_id)
                    );

                    -- 群设置表（每个群独立的开关配置）
                    CREATE TABLE IF NOT EXISTS group_settings (
                        group_id INTEGER PRIMARY KEY,
                        game_enabled INTEGER NOT NULL DEFAULT 1
                    );

                    -- 大乱斗报名表
                    CREATE TABLE IF NOT EXISTS battle_royale (
                        group_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        signed_at REAL NOT NULL,
                        PRIMARY KEY (group_id, user_id)
                    );

                    -- 大乱斗每日参与次数表
                    CREATE TABLE IF NOT EXISTS battle_daily (
                        group_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        date_str TEXT NOT NULL,
                        count INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (group_id, user_id, date_str)
                    );

                    -- 种植表
                    CREATE TABLE IF NOT EXISTS planting (
                        group_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        crop_id TEXT NOT NULL,
                        planted_at REAL NOT NULL,
                        PRIMARY KEY (group_id, user_id)
                    );

                    -- 世界 Boss 表（每个群一只）
                    CREATE TABLE IF NOT EXISTS world_boss (
                        group_id INTEGER PRIMARY KEY,
                        boss_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        hp REAL NOT NULL,
                        max_hp REAL NOT NULL,
                        attack INTEGER NOT NULL,
                        spawn_time REAL NOT NULL,
                        expire_time REAL NOT NULL,
                        last_hitter INTEGER DEFAULT 0
                    );

                    -- 世界 Boss 伤害贡献表
                    CREATE TABLE IF NOT EXISTS world_boss_damage (
                        group_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        total_damage REAL NOT NULL DEFAULT 0,
                        last_attack REAL DEFAULT 0,
                        PRIMARY KEY (group_id, user_id)
                    );

                    -- PK 冷却表
                    CREATE TABLE IF NOT EXISTS pk_cooldown (
                        group_id INTEGER NOT NULL,
                        attacker_id INTEGER NOT NULL,
                        target_id INTEGER NOT NULL,
                        until_time REAL NOT NULL,
                        PRIMARY KEY (group_id, attacker_id, target_id)
                    );

                    -- 丹药服用次数表（用于修为丹药效果递减）
                    CREATE TABLE IF NOT EXISTS pill_usage (
                        group_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        pill_key TEXT NOT NULL,
                        count INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (group_id, user_id, pill_key)
                    );

                    CREATE INDEX IF NOT EXISTS idx_players_group ON players(group_id);
                    CREATE INDEX IF NOT EXISTS idx_gongfas_group ON gongfas(group_id);
                    CREATE INDEX IF NOT EXISTS idx_inventory_group ON inventory(group_id);
                    CREATE INDEX IF NOT EXISTS idx_pets_group ON pets(group_id);
                    CREATE INDEX IF NOT EXISTS idx_market_group ON market_orders(group_id, status);
                    CREATE INDEX IF NOT EXISTS idx_furnace_group ON furnaces(group_id);
                    """
                )
                self._migrate_db(conn)
            logger.info("修仙数据库初始化完成")
        except Exception as e:
            logger.error(f"修仙数据库初始化失败: {e}")

    def _migrate_db(self, conn: sqlite3.Connection) -> None:
        """轻量迁移：为旧库补充新增字段"""
        try:
            columns = {r["name"] for r in conn.execute("PRAGMA table_info(players)").fetchall()}
            if "rebirth_count" not in columns:
                conn.execute("ALTER TABLE players ADD COLUMN rebirth_count INTEGER DEFAULT 0")
            if "ring" not in columns:
                conn.execute("ALTER TABLE players ADD COLUMN ring TEXT DEFAULT ''")
            if "boots" not in columns:
                conn.execute("ALTER TABLE players ADD COLUMN boots TEXT DEFAULT ''")
            if "cur_hp" not in columns:
                conn.execute("ALTER TABLE players ADD COLUMN cur_hp INTEGER DEFAULT 0")
            if "dead_until" not in columns:
                conn.execute("ALTER TABLE players ADD COLUMN dead_until REAL DEFAULT 0")
            if "pk_boost" not in columns:
                conn.execute("ALTER TABLE players ADD COLUMN pk_boost REAL DEFAULT 0")
            if "pk_hp_cost" not in columns:
                conn.execute("ALTER TABLE players ADD COLUMN pk_hp_cost INTEGER DEFAULT 0")
            if "xiuxiu_until" not in columns:
                conn.execute("ALTER TABLE players ADD COLUMN xiuxiu_until REAL DEFAULT 0")
            if "debuffs" not in columns:
                conn.execute("ALTER TABLE players ADD COLUMN debuffs TEXT DEFAULT ''")

            wstate_columns = {r["name"] for r in conn.execute("PRAGMA table_info(world_state)").fetchall()}
            if "breakthrough_merchant_end_time" not in wstate_columns:
                conn.execute("ALTER TABLE world_state ADD COLUMN breakthrough_merchant_end_time REAL DEFAULT 0")
        except Exception as e:
            logger.error(f"数据库迁移失败: {e}")

    def _to_dict(self, row: Optional[sqlite3.Row]) -> Optional[dict]:
        return dict(row) if row else None

    # ==================== 玩家操作 ====================

    def create_player(self, group_id: int, user_id: int, data: dict) -> bool:
        """创建玩家角色"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO players
                    (group_id, user_id, name, realm, realm_progress, spirit_root, spirit_quality,
                     fortune, physique, talent, attack, defense, hp, cur_hp, coin,
                     alchemy_level, alchemy_exp, forge_level, forge_exp, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        group_id, user_id, data.get("name", ""),
                        data.get("realm", 0), data.get("realm_progress", 0),
                        data.get("spirit_root", ""), data.get("spirit_quality", ""),
                        data.get("fortune", 1000), data.get("physique", ""),
                        data.get("talent", "random"),
                        data.get("attack", 10), data.get("defense", 10), data.get("hp", 100),
                        data.get("cur_hp", data.get("hp", 100)),
                        data.get("coin", 100),
                        data.get("alchemy_level", 1), data.get("alchemy_exp", 0),
                        data.get("forge_level", 1), data.get("forge_exp", 0),
                        time.time(),
                    ),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"创建玩家失败 group={group_id} user={user_id}: {e}")
            return False

    def get_player(self, group_id: int, user_id: int) -> Optional[dict]:
        """获取玩家角色信息"""
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM players WHERE group_id = ? AND user_id = ?",
                    (group_id, user_id),
                ).fetchone()
                return self._to_dict(row)
        except Exception as e:
            logger.error(f"获取玩家失败 group={group_id} user={user_id}: {e}")
            return None

    def update_player(self, group_id: int, user_id: int, fields: dict) -> bool:
        """更新玩家指定字段（字段名必须存在于 players 表）"""
        if not fields:
            return True
        try:
            # 白名单字段，防止 SQL 注入
            allowed = {
                "name", "realm", "realm_progress", "spirit_root", "spirit_quality",
                "fortune", "physique", "talent", "attack", "defense", "hp", "coin",
                "alchemy_level", "alchemy_exp", "forge_level", "forge_exp",
                "bottleneck_until", "weapon", "armor", "treasure", "ring", "boots", "rebirth_count",
                "cur_hp", "dead_until", "pk_boost", "pk_hp_cost", "xiuxiu_until", "debuffs",
            }
            updates = {k: v for k, v in fields.items() if k in allowed}
            if not updates:
                return False
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            params = list(updates.values()) + [group_id, user_id]
            with self._get_conn() as conn:
                conn.execute(
                    f"UPDATE players SET {set_clause} WHERE group_id = ? AND user_id = ?",
                    params,
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"更新玩家失败 group={group_id} user={user_id}: {e}")
            return False

    def delete_player(self, group_id: int, user_id: int) -> bool:
        """删除玩家角色及其关联数据"""
        try:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM players WHERE group_id = ? AND user_id = ?", (group_id, user_id))
                self._clear_player_related(conn, group_id, user_id)
            return True
        except Exception as e:
            logger.error(f"删除玩家失败 group={group_id} user={user_id}: {e}")
            return False

    def _clear_player_related(self, conn: sqlite3.Connection, group_id: int, user_id: int) -> None:
        """清除玩家关联数据（功法/背包/灵宠/师徒/挂机/冷却/挂单），保留玩家主记录"""
        conn.execute("DELETE FROM cultivation WHERE group_id = ? AND user_id = ?", (group_id, user_id))
        conn.execute("DELETE FROM gongfas WHERE group_id = ? AND user_id = ?", (group_id, user_id))
        conn.execute("DELETE FROM inventory WHERE group_id = ? AND user_id = ?", (group_id, user_id))
        conn.execute("DELETE FROM pets WHERE group_id = ? AND user_id = ?", (group_id, user_id))
        conn.execute("DELETE FROM furnaces WHERE group_id = ? AND (owner_id = ? OR target_id = ?)", (group_id, user_id, user_id))
        conn.execute("DELETE FROM explore_cooldown WHERE group_id = ? AND user_id = ?", (group_id, user_id))
        conn.execute("DELETE FROM market_orders WHERE group_id = ? AND seller_id = ?", (group_id, user_id))

    def reset_player_related(self, group_id: int, user_id: int) -> bool:
        """转世重生：清除玩家关联数据（保留玩家主记录）"""
        try:
            with self._get_conn() as conn:
                self._clear_player_related(conn, group_id, user_id)
            return True
        except Exception as e:
            logger.error(f"重置玩家数据失败 group={group_id} user={user_id}: {e}")
            return False

    def get_all_player_groups(self) -> list[int]:
        """获取所有有玩家的群 ID（用于世界 Tick 遍历）"""
        try:
            with self._get_conn() as conn:
                rows = conn.execute("SELECT DISTINCT group_id FROM players").fetchall()
                return [r["group_id"] for r in rows]
        except Exception as e:
            logger.error(f"获取玩家群列表失败: {e}")
            return []

    # ==================== 挂机修炼 ====================

    def start_cultivation(self, group_id: int, user_id: int, location: str) -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cultivation (group_id, user_id, location, started_at) VALUES (?, ?, ?, ?)",
                    (group_id, user_id, location, time.time()),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"开始修炼失败: {e}")
            return False

    def get_cultivation(self, group_id: int, user_id: int) -> Optional[dict]:
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM cultivation WHERE group_id = ? AND user_id = ?",
                    (group_id, user_id),
                ).fetchone()
                return self._to_dict(row)
        except Exception as e:
            logger.error(f"获取修炼状态失败: {e}")
            return None

    def end_cultivation(self, group_id: int, user_id: int) -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "DELETE FROM cultivation WHERE group_id = ? AND user_id = ?",
                    (group_id, user_id),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"结束修炼失败: {e}")
            return False

    def get_all_cultivating(self, group_id: int) -> list[dict]:
        """获取群内所有正在挂机的玩家"""
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM cultivation WHERE group_id = ?",
                    (group_id,),
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取挂机列表失败: {e}")
            return []

    # ==================== 功法 ====================

    def learn_gongfa(self, group_id: int, user_id: int, gongfa_id: str) -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO gongfas (group_id, user_id, gongfa_id, level, exp) VALUES (?, ?, ?, 0, 0)",
                    (group_id, user_id, gongfa_id),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"学习功法失败: {e}")
            return False

    def get_gongfas(self, group_id: int, user_id: int) -> list[dict]:
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM gongfas WHERE group_id = ? AND user_id = ?",
                    (group_id, user_id),
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取功法列表失败: {e}")
            return []

    def get_gongfa(self, group_id: int, user_id: int, gongfa_id: str) -> Optional[dict]:
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM gongfas WHERE group_id = ? AND user_id = ? AND gongfa_id = ?",
                    (group_id, user_id, gongfa_id),
                ).fetchone()
                return self._to_dict(row)
        except Exception as e:
            logger.error(f"获取功法失败: {e}")
            return None

    def update_gongfa(self, group_id: int, user_id: int, gongfa_id: str, fields: dict) -> bool:
        if not fields:
            return True
        try:
            allowed = {"level", "exp"}
            updates = {k: v for k, v in fields.items() if k in allowed}
            if not updates:
                return False
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            params = list(updates.values()) + [group_id, user_id, gongfa_id]
            with self._get_conn() as conn:
                conn.execute(
                    f"UPDATE gongfas SET {set_clause} WHERE group_id = ? AND user_id = ? AND gongfa_id = ?",
                    params,
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"更新功法失败: {e}")
            return False

    # ==================== 背包 ====================

    def add_item(self, group_id: int, user_id: int, item_id: str, quantity: int = 1) -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO inventory (group_id, user_id, item_id, quantity) VALUES (?, ?, ?, ?)
                    ON CONFLICT(group_id, user_id, item_id) DO UPDATE SET quantity = quantity + excluded.quantity
                    """,
                    (group_id, user_id, item_id, quantity),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"添加物品失败: {e}")
            return False

    def remove_item(self, group_id: int, user_id: int, item_id: str, quantity: int = 1) -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    UPDATE inventory SET quantity = quantity - ?
                    WHERE group_id = ? AND user_id = ? AND item_id = ?
                    """,
                    (quantity, group_id, user_id, item_id),
                )
                conn.execute(
                    "DELETE FROM inventory WHERE group_id = ? AND user_id = ? AND item_id = ? AND quantity <= 0",
                    (group_id, user_id, item_id),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"移除物品失败: {e}")
            return False

    def get_item_quantity(self, group_id: int, user_id: int, item_id: str) -> int:
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT quantity FROM inventory WHERE group_id = ? AND user_id = ? AND item_id = ?",
                    (group_id, user_id, item_id),
                ).fetchone()
                return row["quantity"] if row else 0
        except Exception as e:
            logger.error(f"获取物品数量失败: {e}")
            return 0

    def get_inventory(self, group_id: int, user_id: int) -> list[dict]:
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM inventory WHERE group_id = ? AND user_id = ? ORDER BY item_id",
                    (group_id, user_id),
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取背包失败: {e}")
            return []

    # ==================== 灵宠 ====================

    def add_pet(self, group_id: int, user_id: int, pet_id: int, pet_type: str, name: str = "") -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO pets (group_id, user_id, pet_id, pet_type, level, exp, evolution, name) VALUES (?, ?, ?, ?, 1, 0, 1, ?)",
                    (group_id, user_id, pet_id, pet_type, name),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"添加灵宠失败: {e}")
            return False

    def get_pets(self, group_id: int, user_id: int) -> list[dict]:
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM pets WHERE group_id = ? AND user_id = ? ORDER BY pet_id",
                    (group_id, user_id),
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取灵宠列表失败: {e}")
            return []

    def get_pet(self, group_id: int, user_id: int, pet_id: int) -> Optional[dict]:
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM pets WHERE group_id = ? AND user_id = ? AND pet_id = ?",
                    (group_id, user_id, pet_id),
                ).fetchone()
                return self._to_dict(row)
        except Exception as e:
            logger.error(f"获取灵宠失败: {e}")
            return None

    def update_pet(self, group_id: int, user_id: int, pet_id: int, fields: dict) -> bool:
        if not fields:
            return True
        try:
            allowed = {"level", "exp", "evolution", "name"}
            updates = {k: v for k, v in fields.items() if k in allowed}
            if not updates:
                return False
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            params = list(updates.values()) + [group_id, user_id, pet_id]
            with self._get_conn() as conn:
                conn.execute(
                    f"UPDATE pets SET {set_clause} WHERE group_id = ? AND user_id = ? AND pet_id = ?",
                    params,
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"更新灵宠失败: {e}")
            return False

    # ==================== 世界状态 ====================

    def ensure_world_state(self, group_id: int) -> dict:
        """确保群的世界状态存在，不存在则创建"""
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM world_state WHERE group_id = ?", (group_id,)
                ).fetchone()
                if row:
                    return dict(row)
                now = time.time()
                conn.execute(
                    "INSERT OR IGNORE INTO world_state (group_id, weather, spirit_concentration, last_tick_time) VALUES (?, '晴', 1.0, ?)",
                    (group_id, now),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM world_state WHERE group_id = ?", (group_id,)
                ).fetchone()
                return dict(row)
        except Exception as e:
            logger.error(f"确保世界状态失败 group={group_id}: {e}")
            return {"group_id": group_id, "weather": "晴", "spirit_concentration": 1.0,
                    "current_event": "", "event_end_time": 0, "last_tick_time": time.time(),
                    "merchant_end_time": 0, "breakthrough_merchant_end_time": 0,
                    "secret_realm_end_time": 0}

    def get_world_state(self, group_id: int) -> dict:
        return self.ensure_world_state(group_id)

    def update_world_state(self, group_id: int, fields: dict) -> bool:
        if not fields:
            return True
        try:
            allowed = {"weather", "spirit_concentration", "current_event", "event_end_time",
                       "last_tick_time", "merchant_end_time", "breakthrough_merchant_end_time",
                       "secret_realm_end_time"}
            updates = {k: v for k, v in fields.items() if k in allowed}
            if not updates:
                return False
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            params = list(updates.values()) + [group_id]
            with self._get_conn() as conn:
                conn.execute(
                    f"UPDATE world_state SET {set_clause} WHERE group_id = ?",
                    params,
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"更新世界状态失败 group={group_id}: {e}")
            return False

    def log_world_event(self, group_id: int, event_type: str, description: str = "") -> None:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO world_events_log (group_id, event_type, started_at, description) VALUES (?, ?, ?, ?)",
                    (group_id, event_type, time.time(), description),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"记录世界事件失败: {e}")

    # ==================== 师徒 ====================

    def add_furnace(self, group_id: int, owner_id: int, target_id: int) -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO furnaces (group_id, owner_id, target_id, started_at) VALUES (?, ?, ?, ?)",
                    (group_id, owner_id, target_id, time.time()),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"收徒失败: {e}")
            return False

    def remove_furnace(self, group_id: int, owner_id: int, target_id: int) -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "DELETE FROM furnaces WHERE group_id = ? AND owner_id = ? AND target_id = ?",
                    (group_id, owner_id, target_id),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"解除师徒失败: {e}")
            return False

    def get_furnaces_by_owner(self, group_id: int, owner_id: int) -> list[dict]:
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM furnaces WHERE group_id = ? AND owner_id = ?",
                    (group_id, owner_id),
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取弟子列表失败: {e}")
            return []

    def get_furnace_by_target(self, group_id: int, target_id: int) -> Optional[dict]:
        """查询某人是否被作为弟子（含自己收徒自己的反向）"""
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM furnaces WHERE group_id = ? AND target_id = ?",
                    (group_id, target_id),
                ).fetchone()
                return self._to_dict(row)
        except Exception as e:
            logger.error(f"获取师徒归属失败: {e}")
            return None

    def get_furnaces_by_group(self, group_id: int) -> list[dict]:
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM furnaces WHERE group_id = ?",
                    (group_id,),
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取群师徒列表失败: {e}")
            return []

    # ==================== 坊市 ====================

    def create_order(self, group_id: int, seller_id: int, item_id: str, quantity: int, price: int) -> Optional[int]:
        """创建挂单，返回挂单 ID"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    "INSERT INTO market_orders (group_id, seller_id, item_id, quantity, price, created_at, status) VALUES (?, ?, ?, ?, ?, ?, 'active')",
                    (group_id, seller_id, item_id, quantity, price, time.time()),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"创建挂单失败: {e}")
            return None

    def get_order(self, order_id: int, group_id: int) -> Optional[dict]:
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM market_orders WHERE id = ? AND group_id = ?",
                    (order_id, group_id),
                ).fetchone()
                return self._to_dict(row)
        except Exception as e:
            logger.error(f"获取挂单失败: {e}")
            return None

    def update_order(self, order_id: int, group_id: int, fields: dict) -> bool:
        if not fields:
            return True
        try:
            allowed = {"quantity", "price", "status"}
            updates = {k: v for k, v in fields.items() if k in allowed}
            if not updates:
                return False
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            params = list(updates.values()) + [order_id, group_id]
            with self._get_conn() as conn:
                conn.execute(
                    f"UPDATE market_orders SET {set_clause} WHERE id = ? AND group_id = ?",
                    params,
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"更新挂单失败: {e}")
            return False

    def get_active_orders(self, group_id: int) -> list[dict]:
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM market_orders WHERE group_id = ? AND status = 'active' ORDER BY created_at",
                    (group_id,),
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取挂单列表失败: {e}")
            return []

    # ==================== 探索冷却 ====================

    def set_explore_cooldown(self, group_id: int, user_id: int, until_time: float) -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO explore_cooldown (group_id, user_id, until_time) VALUES (?, ?, ?)",
                    (group_id, user_id, until_time),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"设置探索冷却失败: {e}")
            return False

    def get_explore_cooldown(self, group_id: int, user_id: int) -> float:
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT until_time FROM explore_cooldown WHERE group_id = ? AND user_id = ?",
                    (group_id, user_id),
                ).fetchone()
                return row["until_time"] if row else 0
        except Exception as e:
            logger.error(f"获取探索冷却失败: {e}")
            return 0

    # ==================== 大乱斗报名 ====================

    def add_battle_signup(self, group_id: int, user_id: int) -> bool:
        """报名大乱斗（去重）"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO battle_royale (group_id, user_id, signed_at) VALUES (?, ?, ?)",
                    (group_id, user_id, time.time()),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"报名大乱斗失败: {e}")
            return False

    def is_battle_signed(self, group_id: int, user_id: int) -> bool:
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT 1 FROM battle_royale WHERE group_id = ? AND user_id = ?",
                    (group_id, user_id),
                ).fetchone()
                return row is not None
        except Exception as e:
            logger.error(f"查询大乱斗报名失败: {e}")
            return False

    def get_battle_signups(self, group_id: int) -> list[dict]:
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM battle_royale WHERE group_id = ? ORDER BY signed_at",
                    (group_id,),
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取大乱斗报名失败: {e}")
            return []

    def clear_battle_signups(self, group_id: int) -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM battle_royale WHERE group_id = ?", (group_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"清空大乱斗报名失败: {e}")
            return False

    def get_battle_daily_count(self, group_id: int, user_id: int, date_str: str) -> int:
        """获取玩家某天参与大乱斗的次数"""
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT count FROM battle_daily WHERE group_id = ? AND user_id = ? AND date_str = ?",
                    (group_id, user_id, date_str),
                ).fetchone()
                return row["count"] if row else 0
        except Exception as e:
            logger.error(f"获取大乱斗每日次数失败: {e}")
            return 0

    def add_battle_daily(self, group_id: int, user_id: int, date_str: str, count: int = 1) -> bool:
        """累加玩家某天参与大乱斗的次数"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO battle_daily (group_id, user_id, date_str, count) VALUES (?, ?, ?, ?)
                    ON CONFLICT(group_id, user_id, date_str) DO UPDATE SET count = count + excluded.count
                    """,
                    (group_id, user_id, date_str, count),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"累加大乱斗每日次数失败: {e}")
            return False

    # ==================== 种植 ====================

    def get_planting(self, group_id: int, user_id: int) -> Optional[dict]:
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM planting WHERE group_id = ? AND user_id = ?",
                    (group_id, user_id),
                ).fetchone()
                return self._to_dict(row)
        except Exception as e:
            logger.error(f"获取种植状态失败: {e}")
            return None

    def set_planting(self, group_id: int, user_id: int, crop_id: str) -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO planting (group_id, user_id, crop_id, planted_at) VALUES (?, ?, ?, ?)",
                    (group_id, user_id, crop_id, time.time()),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"设置种植状态失败: {e}")
            return False

    def clear_planting(self, group_id: int, user_id: int) -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "DELETE FROM planting WHERE group_id = ? AND user_id = ?",
                    (group_id, user_id),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"清除种植状态失败: {e}")
            return False

    # ==================== 世界 Boss ====================

    def get_world_boss(self, group_id: int) -> Optional[dict]:
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM world_boss WHERE group_id = ?", (group_id,)
                ).fetchone()
                return self._to_dict(row)
        except Exception as e:
            logger.error(f"获取世界 Boss 失败: {e}")
            return None

    def spawn_world_boss(self, group_id: int, boss: dict) -> bool:
        """刷新一只世界 Boss（覆盖旧的）"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO world_boss
                    (group_id, boss_id, name, hp, max_hp, attack, spawn_time, expire_time, last_hitter)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (group_id, boss["boss_id"], boss["name"], boss["hp"], boss["max_hp"],
                     boss["attack"], boss["spawn_time"], boss["expire_time"], 0),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"刷新世界 Boss 失败: {e}")
            return False

    def clear_world_boss(self, group_id: int) -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM world_boss WHERE group_id = ?", (group_id,))
                conn.execute("DELETE FROM world_boss_damage WHERE group_id = ?", (group_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"清除世界 Boss 失败: {e}")
            return False

    def update_world_boss(self, group_id: int, fields: dict) -> bool:
        if not fields:
            return True
        try:
            allowed = {"hp", "last_hitter"}
            updates = {k: v for k, v in fields.items() if k in allowed}
            if not updates:
                return False
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            params = list(updates.values()) + [group_id]
            with self._get_conn() as conn:
                conn.execute(f"UPDATE world_boss SET {set_clause} WHERE group_id = ?", params)
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"更新世界 Boss 失败: {e}")
            return False

    def get_boss_damage(self, group_id: int, user_id: int) -> Optional[dict]:
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM world_boss_damage WHERE group_id = ? AND user_id = ?",
                    (group_id, user_id),
                ).fetchone()
                return self._to_dict(row)
        except Exception as e:
            logger.error(f"获取 Boss 伤害贡献失败: {e}")
            return None

    def add_boss_damage(self, group_id: int, user_id: int, damage: float) -> bool:
        """累加玩家对 Boss 的伤害并记录攻击时间"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO world_boss_damage (group_id, user_id, total_damage, last_attack)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(group_id, user_id) DO UPDATE SET
                        total_damage = total_damage + excluded.total_damage,
                        last_attack = excluded.last_attack
                    """,
                    (group_id, user_id, damage, time.time()),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"累加 Boss 伤害失败: {e}")
            return False

    def get_boss_contributions(self, group_id: int) -> list[dict]:
        """获取群内所有玩家对 Boss 的伤害贡献（按伤害降序）"""
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM world_boss_damage WHERE group_id = ? ORDER BY total_damage DESC",
                    (group_id,),
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取 Boss 伤害贡献列表失败: {e}")
            return []

    # ==================== PK 冷却 ====================

    def set_pk_cooldown(self, group_id: int, attacker_id: int, target_id: int, until_time: float) -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO pk_cooldown (group_id, attacker_id, target_id, until_time) VALUES (?, ?, ?, ?)",
                    (group_id, attacker_id, target_id, until_time),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"设置 PK 冷却失败: {e}")
            return False

    def get_pk_cooldown(self, group_id: int, attacker_id: int, target_id: int) -> float:
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT until_time FROM pk_cooldown WHERE group_id = ? AND attacker_id = ? AND target_id = ?",
                    (group_id, attacker_id, target_id),
                ).fetchone()
                return row["until_time"] if row else 0
        except Exception as e:
            logger.error(f"获取 PK 冷却失败: {e}")
            return 0

    # ==================== 丹药服用次数 ====================

    def get_pill_usage(self, group_id: int, user_id: int, pill_key: str) -> int:
        """获取玩家服用某种丹药的累计次数"""
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT count FROM pill_usage WHERE group_id = ? AND user_id = ? AND pill_key = ?",
                    (group_id, user_id, pill_key),
                ).fetchone()
                return row["count"] if row else 0
        except Exception as e:
            logger.error(f"获取丹药服用次数失败: {e}")
            return 0

    def add_pill_usage(self, group_id: int, user_id: int, pill_key: str, count: int = 1) -> bool:
        """累加玩家服用某种丹药的次数"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO pill_usage (group_id, user_id, pill_key, count) VALUES (?, ?, ?, ?)
                    ON CONFLICT(group_id, user_id, pill_key) DO UPDATE SET count = count + excluded.count
                    """,
                    (group_id, user_id, pill_key, count),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"累加丹药服用次数失败: {e}")
            return False

    # ==================== 通用 ====================

    # ==================== 群设置 ====================

    def is_game_enabled(self, group_id: int) -> bool:
        """检查群是否开启了修仙功能（默认开启）"""
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT game_enabled FROM group_settings WHERE group_id = ?",
                    (group_id,),
                ).fetchone()
                return row["game_enabled"] == 1 if row else True
        except Exception as e:
            logger.error(f"获取群开关失败 group={group_id}: {e}")
            return True

    def set_game_enabled(self, group_id: int, enabled: bool) -> bool:
        """设置群的修仙功能开关"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO group_settings (group_id, game_enabled) VALUES (?, ?)",
                    (group_id, 1 if enabled else 0),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"设置群开关失败 group={group_id}: {e}")
            return False

    def execute_raw(self, sql: str, params: tuple = ()) -> list[dict]:
        """执行任意查询（仅供内部扩展使用）"""
        try:
            with self._get_conn() as conn:
                rows = conn.execute(sql, params).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            return []
