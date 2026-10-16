from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class LotteryDatabase:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def initialize_sync(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS lottery_quota (
                    user_id INTEGER NOT NULL,
                    draw_date TEXT NOT NULL,
                    used_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, draw_date)
                );

                CREATE TABLE IF NOT EXISTS lottery_draws (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    group_id INTEGER NOT NULL,
                    draw_date TEXT NOT NULL,
                    attempt_no INTEGER NOT NULL,
                    item_name TEXT NOT NULL,
                    image_name TEXT NOT NULL,
                    rarity TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    gif_path TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    error_message TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_lottery_draws_user_date
                    ON lottery_draws(user_id, draw_date, status, id);
                """
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def reserve_draw_sync(
        self,
        *,
        user_id: int,
        group_id: int,
        draw_date: str,
        created_at: str,
        item: dict[str, Any],
        daily_limit: int,
    ) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT used_count FROM lottery_quota WHERE user_id = ? AND draw_date = ?",
                (user_id, draw_date),
            ).fetchone()
            used_count = int(row["used_count"]) if row else 0
            if used_count >= daily_limit:
                conn.rollback()
                return None

            attempt_no = used_count + 1
            conn.execute(
                """
                INSERT INTO lottery_quota(user_id, draw_date, used_count)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, draw_date)
                DO UPDATE SET used_count = excluded.used_count
                """,
                (user_id, draw_date, attempt_no),
            )
            cursor = conn.execute(
                """
                INSERT INTO lottery_draws(
                    user_id, group_id, draw_date, attempt_no,
                    item_name, image_name, rarity, price,
                    status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    user_id,
                    group_id,
                    draw_date,
                    attempt_no,
                    item["item_name"],
                    item["image_name"],
                    item["rarity"],
                    int(item["price"]),
                    created_at,
                ),
            )
            record_id = int(cursor.lastrowid)
            conn.commit()
            return {
                "id": record_id,
                "user_id": user_id,
                "group_id": group_id,
                "draw_date": draw_date,
                "attempt_no": attempt_no,
                "remaining": max(0, daily_limit - attempt_no),
                **item,
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def complete_draw_sync(
        self, record_id: int, gif_path: str, completed_at: str
    ) -> bool:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                """
                UPDATE lottery_draws
                SET status = 'completed', gif_path = ?, completed_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (gif_path, completed_at, record_id),
            )
            updated = cursor.rowcount == 1
            conn.commit()
            return updated
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def release_draw_sync(self, record_id: int, error_message: str) -> bool:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT user_id, draw_date, status FROM lottery_draws WHERE id = ?",
                (record_id,),
            ).fetchone()
            if row is None or row["status"] != "pending":
                conn.rollback()
                return False

            conn.execute(
                """
                UPDATE lottery_draws
                SET status = 'failed', error_message = ?
                WHERE id = ?
                """,
                (error_message[:500], record_id),
            )
            conn.execute(
                """
                UPDATE lottery_quota
                SET used_count = MAX(0, used_count - 1)
                WHERE user_id = ? AND draw_date = ?
                """,
                (row["user_id"], row["draw_date"]),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def cleanup_stale_pending_sync(
        self, cutoff: datetime, error_message: str = "进程中断，自动释放次数"
    ) -> int:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """
                SELECT id, user_id, draw_date
                FROM lottery_draws
                WHERE status = 'pending' AND created_at < ?
                """,
                (cutoff.isoformat(),),
            ).fetchall()
            for row in rows:
                conn.execute(
                    """
                    UPDATE lottery_draws
                    SET status = 'failed', error_message = ?
                    WHERE id = ?
                    """,
                    (error_message, row["id"]),
                )
                conn.execute(
                    """
                    UPDATE lottery_quota
                    SET used_count = MAX(0, used_count - 1)
                    WHERE user_id = ? AND draw_date = ?
                    """,
                    (row["user_id"], row["draw_date"]),
                )
            conn.commit()
            return len(rows)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_today_draws_sync(
        self, user_id: int, draw_date: str
    ) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT *
                FROM lottery_draws
                WHERE user_id = ? AND draw_date = ? AND status = 'completed'
                ORDER BY id ASC
                """,
                (user_id, draw_date),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_last_completed_item_sync(self, user_id: int) -> str | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT item_name
                FROM lottery_draws
                WHERE user_id = ? AND status = 'completed'
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            return str(row["item_name"]) if row else None
        finally:
            conn.close()

    async def initialize(self) -> None:
        await asyncio.to_thread(self.initialize_sync)

    async def reserve_draw(
        self,
        *,
        user_id: int,
        group_id: int,
        draw_date: str,
        created_at: str,
        item: dict[str, Any],
        daily_limit: int,
    ) -> dict[str, Any] | None:
        return await asyncio.to_thread(
            self.reserve_draw_sync,
            user_id=user_id,
            group_id=group_id,
            draw_date=draw_date,
            created_at=created_at,
            item=item,
            daily_limit=daily_limit,
        )

    async def complete_draw(
        self, record_id: int, gif_path: str, completed_at: str
    ) -> bool:
        return await asyncio.to_thread(
            self.complete_draw_sync, record_id, gif_path, completed_at
        )

    async def release_draw(self, record_id: int, error_message: str) -> bool:
        return await asyncio.to_thread(
            self.release_draw_sync, record_id, error_message
        )

    async def cleanup_stale_pending(self, cutoff: datetime | None = None) -> int:
        cutoff = cutoff or (datetime.now().astimezone() - timedelta(minutes=15))
        return await asyncio.to_thread(self.cleanup_stale_pending_sync, cutoff)

    async def get_today_draws(
        self, user_id: int, draw_date: str
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(
            self.get_today_draws_sync, user_id, draw_date
        )

    async def get_last_completed_item(self, user_id: int) -> str | None:
        return await asyncio.to_thread(self.get_last_completed_item_sync, user_id)
