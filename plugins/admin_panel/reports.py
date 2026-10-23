from __future__ import annotations

import re
import sqlite3
import threading
import time
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from nonebot import logger

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHAT_LOG_DIR = PROJECT_ROOT / "data" / "chat_logs"
AI_REQUEST_LOG = PROJECT_ROOT / "log" / "ai_request.log"
LOTTERY_DB = PROJECT_ROOT / "data" / "lottery" / "lottery.db"
REPORT_DB = PROJECT_ROOT / "data" / "report_cache.db"

CHAT_FILE_RE = re.compile(r"^(\d+)_(\d{4}-\d{2}-\d{2})(?:_uploaded)?\.txt$")
CHAT_LINE_RE = re.compile(
    r"\[(\d{4}-\d{2}-\d{2}) (\d{2}):\d{2}:\d{2}\]\[([^\]]*)\]\[(\d+)\]"
)
AI_EVENT_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)$")
AI_REQUEST_RE = re.compile(
    r'^\{"timestamp":\s*"([^"]+)",\s*"model":\s*"([^"]+)"'
)
DURATION_RE = re.compile(r"耗时\s*([0-9.]+)s")

_refresh_lock = threading.Lock()
_refresh_thread_lock = threading.Lock()
_refresh_thread: threading.Thread | None = None
_last_refresh_at = 0.0
_REFRESH_THROTTLE_SECONDS = 1.0
_BACKGROUND_REFRESH_SECONDS = 60.0
_schema_ready = False


def _clamp_days(days: int | str | None) -> int:
    try:
        return max(1, min(int(days or 7), 90))
    except (TypeError, ValueError):
        return 7


def _date_range(days: int) -> list[str]:
    end = date.today()
    start = end - timedelta(days=days - 1)
    return [(start + timedelta(days=offset)).isoformat() for offset in range(days)]


def _connect_report_db() -> sqlite3.Connection:
    REPORT_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(REPORT_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    global _schema_ready
    if _schema_ready:
        return
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS group_daily (
            group_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (group_id, day)
        );
        CREATE TABLE IF NOT EXISTS group_hourly (
            group_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            hour INTEGER NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (group_id, day, hour)
        );
        CREATE TABLE IF NOT EXISTS group_user_daily (
            group_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (group_id, day, user_id)
        );
        CREATE TABLE IF NOT EXISTS group_files (
            group_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            file_path TEXT NOT NULL DEFAULT '',
            offset INTEGER NOT NULL DEFAULT 0,
            size INTEGER NOT NULL DEFAULT 0,
            mtime REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (group_id, day)
        );
        CREATE TABLE IF NOT EXISTS ai_daily (
            day TEXT PRIMARY KEY,
            attempts INTEGER NOT NULL DEFAULT 0,
            success INTEGER NOT NULL DEFAULT 0,
            failure INTEGER NOT NULL DEFAULT 0,
            latency_sum REAL NOT NULL DEFAULT 0,
            latency_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS ai_hourly (
            day TEXT NOT NULL,
            hour INTEGER NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (day, hour)
        );
        CREATE TABLE IF NOT EXISTS ai_model_daily (
            day TEXT NOT NULL,
            model TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (day, model)
        );
        CREATE TABLE IF NOT EXISTS ai_error_daily (
            day TEXT NOT NULL,
            message TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (day, message)
        );
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_group_daily_day ON group_daily(day);
        CREATE INDEX IF NOT EXISTS idx_group_hourly_day ON group_hourly(day);
        CREATE INDEX IF NOT EXISTS idx_group_user_daily_day ON group_user_daily(day);
        CREATE INDEX IF NOT EXISTS idx_group_user_daily_day_group ON group_user_daily(day, group_id);
        CREATE INDEX IF NOT EXISTS idx_group_files_day ON group_files(day);
        CREATE INDEX IF NOT EXISTS idx_ai_hourly_day ON ai_hourly(day);
        CREATE INDEX IF NOT EXISTS idx_ai_model_daily_day ON ai_model_daily(day);
        CREATE INDEX IF NOT EXISTS idx_ai_error_daily_day ON ai_error_daily(day);
        """
    )
    _schema_ready = True


def _collect_group_files() -> dict[tuple[int, str], Path]:
    files: dict[tuple[int, str], Path] = {}
    sizes: dict[tuple[int, str], int] = {}
    if not CHAT_LOG_DIR.exists():
        return files
    for path in CHAT_LOG_DIR.glob("*.txt"):
        match = CHAT_FILE_RE.match(path.name)
        if not match:
            continue
        group_id = int(match.group(1))
        day = match.group(2)
        try:
            size = path.stat().st_size
        except OSError:
            continue
        key = (group_id, day)
        if key not in files or size > sizes[key]:
            files[key] = path
            sizes[key] = size
    return files


def _reset_group_day(conn: sqlite3.Connection, group_id: int, day: str) -> None:
    conn.execute(
        "DELETE FROM group_daily WHERE group_id = ? AND day = ?", (group_id, day)
    )
    conn.execute(
        "DELETE FROM group_hourly WHERE group_id = ? AND day = ?", (group_id, day)
    )
    conn.execute(
        "DELETE FROM group_user_daily WHERE group_id = ? AND day = ?", (group_id, day)
    )


def _sync_group_stats(conn: sqlite3.Connection) -> None:
    for (group_id, day), path in sorted(_collect_group_files().items()):
        try:
            stat = path.stat()
        except OSError:
            continue

        row = conn.execute(
            "SELECT offset, size, file_path, mtime FROM group_files WHERE group_id = ? AND day = ?",
            (group_id, day),
        ).fetchone()
        if (
            row
            and stat.st_size == int(row["size"])
            and int(row["offset"]) == int(row["size"])
            and row["file_path"] == str(path)
            and abs(float(row["mtime"]) - stat.st_mtime) < 1e-6
        ):
            continue
        offset = int(row["offset"]) if row else 0
        if stat.st_size < offset:
            _reset_group_day(conn, group_id, day)
            offset = 0
        if row and stat.st_size == offset:
            conn.execute(
                "UPDATE group_files SET file_path = ?, mtime = ? WHERE group_id = ? AND day = ?",
                (str(path), stat.st_mtime, group_id, day),
            )
            continue

        hours: Counter[int] = Counter()
        users: Counter[int] = Counter()
        names: dict[int, str] = {}
        total = 0
        try:
            with path.open("rb") as handle:
                handle.seek(offset)
                while True:
                    raw = handle.readline()
                    if not raw or not raw.endswith(b"\n"):
                        break
                    offset += len(raw)
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    match = CHAT_LINE_RE.match(line)
                    if not match:
                        continue
                    line_day, hour_text, name, user_id = match.groups()
                    if line_day != day:
                        continue
                    hour = int(hour_text)
                    if hour < 0 or hour > 23:
                        continue
                    uid = int(user_id)
                    hours[hour] += 1
                    users[uid] += 1
                    names[uid] = name
                    total += 1
        except OSError as exc:
            logger.warning(f"读取群聊记录失败 {path}: {exc}")
            continue

        if total:
            conn.execute(
                "INSERT INTO group_daily (group_id, day, count) VALUES (?, ?, ?) "
                "ON CONFLICT(group_id, day) DO UPDATE SET count = count + excluded.count",
                (group_id, day, total),
            )
            conn.executemany(
                "INSERT INTO group_hourly (group_id, day, hour, count) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(group_id, day, hour) DO UPDATE SET count = count + excluded.count",
                [(group_id, day, hour, count) for hour, count in hours.items()],
            )
            conn.executemany(
                "INSERT INTO group_user_daily (group_id, day, user_id, name, count) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(group_id, day, user_id) DO UPDATE SET "
                "count = count + excluded.count, name = excluded.name",
                [
                    (group_id, day, user_id, names.get(user_id, ""), count)
                    for user_id, count in users.items()
                ],
            )

        conn.execute(
            "INSERT INTO group_files (group_id, day, file_path, offset, size, mtime) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(group_id, day) DO UPDATE SET "
            "file_path = excluded.file_path, offset = excluded.offset, "
            "size = excluded.size, mtime = excluded.mtime",
            (group_id, day, str(path), offset, stat.st_size, stat.st_mtime),
        )


def _parse_ai_model(line: bytes) -> tuple[str, str] | None:
    match = AI_REQUEST_RE.match(line[:1024].decode("utf-8", errors="replace"))
    if not match:
        return None
    return match.groups()


def _sync_ai_stats(conn: sqlite3.Connection) -> None:
    if not AI_REQUEST_LOG.exists():
        return

    try:
        stat = AI_REQUEST_LOG.stat()
    except OSError:
        return

    meta = {
        row["key"]: row["value"]
        for row in conn.execute(
            "SELECT key, value FROM meta WHERE key IN ('ai_offset', 'ai_inode')"
        )
    }
    offset = int(meta.get("ai_offset", "0") or 0)
    inode = str(getattr(stat, "st_ino", ""))
    if stat.st_size < offset or (meta.get("ai_inode") and meta["ai_inode"] != inode):
        offset = 0
    if stat.st_size == offset:
        return

    daily: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "attempts": 0,
            "success": 0,
            "failure": 0,
            "latency_sum": 0.0,
            "latency_count": 0,
        }
    )
    hourly: dict[str, Counter[int]] = defaultdict(Counter)
    models: dict[str, Counter[str]] = defaultdict(Counter)
    errors: dict[str, Counter[str]] = defaultdict(Counter)

    try:
        with AI_REQUEST_LOG.open("rb") as handle:
            handle.seek(offset)
            while True:
                raw = handle.readline()
                if not raw or not raw.endswith(b"\n"):
                    break
                offset += len(raw)

                if raw.startswith(b'{"timestamp"'):
                    parsed = _parse_ai_model(raw)
                    if parsed:
                        timestamp, model = parsed
                        if len(timestamp) >= 10:
                            models[timestamp[:10]][model] += 1
                    continue

                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                match = AI_EVENT_RE.match(line)
                if not match:
                    continue
                timestamp, message = match.groups()
                if len(timestamp) < 13:
                    continue
                day = timestamp[:10]
                hour_text = timestamp[11:13]
                hour = int(hour_text) if hour_text.isdigit() else 0

                success = "API 调用成功" in message and "开始" not in message
                failure = "API 调用失败" in message
                if not success and not failure:
                    continue

                item = daily[day]
                item["attempts"] += 1
                if success:
                    item["success"] += 1
                else:
                    item["failure"] += 1
                duration = DURATION_RE.search(message)
                if duration:
                    try:
                        item["latency_sum"] += float(duration.group(1))
                        item["latency_count"] += 1
                    except ValueError:
                        pass
                if 0 <= hour <= 23:
                    hourly[day][hour] += 1
                if failure:
                    errors[day][_error_label(message)] += 1
    except OSError as exc:
        logger.warning(f"读取 AI 请求日志失败: {exc}")
        return

    for day, item in daily.items():
        conn.execute(
            "INSERT INTO ai_daily (day, attempts, success, failure, latency_sum, latency_count) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(day) DO UPDATE SET "
            "attempts = attempts + excluded.attempts, "
            "success = success + excluded.success, "
            "failure = failure + excluded.failure, "
            "latency_sum = latency_sum + excluded.latency_sum, "
            "latency_count = latency_count + excluded.latency_count",
            (
                day,
                int(item["attempts"]),
                int(item["success"]),
                int(item["failure"]),
                float(item["latency_sum"]),
                int(item["latency_count"]),
            ),
        )
    for day, counter in hourly.items():
        conn.executemany(
            "INSERT INTO ai_hourly (day, hour, count) VALUES (?, ?, ?) "
            "ON CONFLICT(day, hour) DO UPDATE SET count = count + excluded.count",
            [(day, hour, count) for hour, count in counter.items()],
        )
    for day, counter in models.items():
        conn.executemany(
            "INSERT INTO ai_model_daily (day, model, count) VALUES (?, ?, ?) "
            "ON CONFLICT(day, model) DO UPDATE SET count = count + excluded.count",
            [(day, model, count) for model, count in counter.items()],
        )
    for day, counter in errors.items():
        conn.executemany(
            "INSERT INTO ai_error_daily (day, message, count) VALUES (?, ?, ?) "
            "ON CONFLICT(day, message) DO UPDATE SET count = count + excluded.count",
            [(day, message, count) for message, count in counter.items()],
        )

    conn.executemany(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        [
            ("ai_offset", str(offset)),
            ("ai_inode", inode),
        ],
    )
    conn.commit()


def refresh_report_cache(force: bool = False) -> None:
    """增量刷新报表缓存。页面接口和定时任务都会调用。"""
    global _last_refresh_at

    with _refresh_lock:
        now = time.monotonic()
        if not force and now - _last_refresh_at < _REFRESH_THROTTLE_SECONDS:
            return
        started = time.monotonic()
        conn = _connect_report_db()
        try:
            _ensure_schema(conn)
            _sync_group_stats(conn)
            _sync_ai_stats(conn)
            conn.execute(
                "INSERT INTO meta (key, value) VALUES ('cache_initialized', '1') "
                "ON CONFLICT(key) DO UPDATE SET value = '1'"
            )
            conn.commit()
        except Exception as exc:
            logger.error(f"报表缓存刷新失败: {exc}")
        finally:
            conn.close()
        _last_refresh_at = time.monotonic()
        elapsed = _last_refresh_at - started
        if elapsed >= 1:
            logger.info(f"报表缓存刷新完成，耗时 {elapsed:.2f}s")


def _cache_initialized() -> bool:
    try:
        conn = _connect_report_db()
    except sqlite3.Error:
        return False
    try:
        return (
            conn.execute(
                "SELECT 1 FROM meta WHERE key = 'cache_initialized'"
            ).fetchone()
            is not None
        )
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def _maybe_start_background_refresh() -> None:
    global _refresh_thread
    with _refresh_thread_lock:
        if _refresh_thread is not None and _refresh_thread.is_alive():
            return
        if time.monotonic() - _last_refresh_at < _BACKGROUND_REFRESH_SECONDS:
            return
        _refresh_thread = threading.Thread(
            target=refresh_report_cache,
            kwargs={"force": True},
            daemon=True,
        )
        _refresh_thread.start()


def _prepare_report_cache() -> None:
    if not _cache_initialized():
        refresh_report_cache(force=True)
        return
    _maybe_start_background_refresh()


def _error_label(message: str) -> str:
    code = re.search(r"Error code:\s*(\d+)", message)
    if code:
        return f"HTTP {code.group(1)}"
    detail = re.search(r"耗时\s*[0-9.]+s:\s*(.*)", message)
    text = detail.group(1) if detail else message
    text = re.sub(r"\s*\(request id:.*", "", text).strip()
    return text[:140] or "未知错误"


def get_group_activity(days: int | str = 7, group_id: str = "all") -> dict[str, Any]:
    _prepare_report_cache()
    days = _clamp_days(days)
    dates = _date_range(days)
    start, end = dates[0], dates[-1]

    selected_gid: int | None = None
    if group_id not in ("", "all", None):
        try:
            selected_gid = int(group_id)
        except (TypeError, ValueError):
            selected_gid = None

    conn = _connect_report_db()
    try:
        groups = [
            int(row[0])
            for row in conn.execute(
                "SELECT DISTINCT group_id FROM group_daily "
                "WHERE day BETWEEN ? AND ? ORDER BY group_id",
                (start, end),
            )
        ]

        where = "day BETWEEN ? AND ?"
        params: list[Any] = [start, end]
        if selected_gid is not None:
            where += " AND group_id = ?"
            params.append(selected_gid)

        daily_rows = {
            row[0]: int(row[1])
            for row in conn.execute(
                f"SELECT day, SUM(count) FROM group_daily WHERE {where} GROUP BY day",
                params,
            )
        }
        daily = [{"date": day, "count": daily_rows.get(day, 0)} for day in dates]

        hourly_rows = {
            int(row[0]): int(row[1])
            for row in conn.execute(
                f"SELECT hour, SUM(count) FROM group_hourly WHERE {where} GROUP BY hour",
                params,
            )
        }
        hourly = [
            {"hour": hour, "count": hourly_rows.get(hour, 0)} for hour in range(24)
        ]

        heatmap_rows = {
            (row[0], int(row[1])): int(row[2])
            for row in conn.execute(
                f"SELECT day, hour, SUM(count) FROM group_hourly "
                f"WHERE {where} GROUP BY day, hour",
                params,
            )
        }
        heatmap = [
            [day_index, hour, heatmap_rows.get((day, hour), 0)]
            for day_index, day in enumerate(dates)
            for hour in range(24)
        ]

        top_users = [
            {
                "user_id": row[0],
                "name": row[1] or str(row[0]),
                "count": int(row[2]),
            }
            for row in conn.execute(
                f"SELECT user_id, MAX(name), SUM(count) AS total "
                f"FROM group_user_daily WHERE {where} "
                f"GROUP BY user_id ORDER BY total DESC LIMIT 10",
                params,
            )
        ]

        active_users = int(
            conn.execute(
                f"SELECT COUNT(DISTINCT user_id) FROM group_user_daily WHERE {where}",
                params,
            ).fetchone()[0]
        )

        ranking_users = {
            int(row[0]): int(row[1])
            for row in conn.execute(
                "SELECT group_id, COUNT(DISTINCT user_id) FROM group_user_daily "
                "WHERE day BETWEEN ? AND ? GROUP BY group_id",
                (start, end),
            )
        }
        group_ranking = [
            {
                "group_id": int(row[0]),
                "count": int(row[1]),
                "users": ranking_users.get(int(row[0]), 0),
            }
            for row in conn.execute(
                "SELECT group_id, SUM(count) AS total FROM group_daily "
                "WHERE day BETWEEN ? AND ? GROUP BY group_id ORDER BY total DESC",
                (start, end),
            )
        ]

        source_files = int(
            conn.execute(
                "SELECT COUNT(*) FROM group_files WHERE day BETWEEN ? AND ?",
                (start, end),
            ).fetchone()[0]
        )
    finally:
        conn.close()

    total = sum(item["count"] for item in daily)
    active_groups = len(groups) if selected_gid is None else (1 if selected_gid in groups else 0)
    return {
        "days": days,
        "start": start,
        "end": end,
        "groups": groups,
        "selected_group": selected_gid if selected_gid is not None else "all",
        "summary": {
            "messages": total,
            "active_groups": active_groups,
            "active_users": active_users,
            "average_daily": round(total / days, 1),
        },
        "daily": daily,
        "hourly": hourly,
        "heatmap": heatmap,
        "top_users": top_users,
        "group_ranking": group_ranking,
        "source_files": source_files,
        "note": "仅统计已开启知识库聊天记录（data/chat_logs）的群，数据来自报表缓存。",
    }


def get_ai_usage(days: int | str = 7) -> dict[str, Any]:
    _prepare_report_cache()
    days = _clamp_days(days)
    dates = _date_range(days)
    start, end = dates[0], dates[-1]

    conn = _connect_report_db()
    try:
        daily_rows = {
            row["day"]: row
            for row in conn.execute(
                "SELECT day, attempts, success, failure, latency_sum, latency_count "
                "FROM ai_daily WHERE day BETWEEN ? AND ?",
                (start, end),
            )
        }
        hourly_rows = {
            int(row[0]): int(row[1])
            for row in conn.execute(
                "SELECT hour, SUM(count) FROM ai_hourly "
                "WHERE day BETWEEN ? AND ? GROUP BY hour",
                (start, end),
            )
        }
        models = [
            {"model": row[0], "count": int(row[1])}
            for row in conn.execute(
                "SELECT model, SUM(count) AS total FROM ai_model_daily "
                "WHERE day BETWEEN ? AND ? GROUP BY model ORDER BY total DESC LIMIT 12",
                (start, end),
            )
        ]
        errors = [
            {"message": row[0], "count": int(row[1])}
            for row in conn.execute(
                "SELECT message, SUM(count) AS total FROM ai_error_daily "
                "WHERE day BETWEEN ? AND ? GROUP BY message ORDER BY total DESC LIMIT 10",
                (start, end),
            )
        ]
    finally:
        conn.close()

    daily = []
    attempts = success = failure = 0
    latency_sum = 0.0
    latency_count = 0
    for day in dates:
        row = daily_rows.get(day)
        day_attempts = int(row["attempts"]) if row else 0
        day_success = int(row["success"]) if row else 0
        day_failure = int(row["failure"]) if row else 0
        day_latency_count = int(row["latency_count"]) if row else 0
        day_latency = (
            round(float(row["latency_sum"]) / day_latency_count, 2)
            if row and day_latency_count
            else 0
        )
        attempts += day_attempts
        success += day_success
        failure += day_failure
        if row:
            latency_sum += float(row["latency_sum"])
            latency_count += day_latency_count
        daily.append(
            {
                "date": day,
                "attempts": day_attempts,
                "success": day_success,
                "failure": day_failure,
                "average_latency": day_latency,
            }
        )

    average_latency = round(latency_sum / latency_count, 2) if latency_count else 0
    success_rate = round(success / attempts * 100, 1) if attempts else 0
    try:
        file_size = AI_REQUEST_LOG.stat().st_size
    except OSError:
        file_size = 0
    return {
        "days": days,
        "start": dates[0],
        "end": dates[-1],
        "available": AI_REQUEST_LOG.exists(),
        "file_size": file_size,
        "summary": {
            "attempts": attempts,
            "success": success,
            "failure": failure,
            "success_rate": success_rate,
            "average_latency": average_latency,
        },
        "daily": daily,
        "hourly": [
            {"hour": hour, "count": hourly_rows.get(hour, 0)} for hour in range(24)
        ],
        "models": models,
        "errors": errors,
        "note": "AI 报表由后台增量解析 log/ai_request.log 生成；旧日志没有 token 用量，暂不统计成本。",
    }


def _connect_ro(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    try:
        return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return None


def _lottery_report(days: int, dates: list[str]) -> dict[str, Any]:
    conn = _connect_ro(LOTTERY_DB)
    if conn is None:
        return {"available": False, "summary": {}, "daily": [], "rarity": [], "top_items": [], "top_draws": []}

    start, end = dates[0], dates[-1]
    try:
        where = "draw_date BETWEEN ? AND ? AND status = 'completed'"
        summary_row = conn.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT user_id), COALESCE(SUM(price), 0), "
            f"COALESCE(AVG(price), 0), COALESCE(MAX(price), 0) "
            f"FROM lottery_draws WHERE {where}",
            (start, end),
        ).fetchone()
        daily_rows = conn.execute(
            f"SELECT draw_date, COUNT(*), COUNT(DISTINCT user_id), COALESCE(SUM(price), 0) "
            f"FROM lottery_draws WHERE {where} GROUP BY draw_date ORDER BY draw_date",
            (start, end),
        ).fetchall()
        rarity_rows = conn.execute(
            f"SELECT rarity, COUNT(*), COALESCE(AVG(price), 0) "
            f"FROM lottery_draws WHERE {where} GROUP BY rarity ORDER BY COUNT(*) DESC",
            (start, end),
        ).fetchall()
        item_rows = conn.execute(
            f"SELECT item_name, COUNT(*), COALESCE(MAX(price), 0) "
            f"FROM lottery_draws WHERE {where} GROUP BY item_name "
            f"ORDER BY COUNT(*) DESC, MAX(price) DESC LIMIT 10",
            (start, end),
        ).fetchall()
        draw_rows = conn.execute(
            f"SELECT item_name, rarity, price, user_id, group_id, draw_date "
            f"FROM lottery_draws WHERE {where} ORDER BY price DESC LIMIT 5",
            (start, end),
        ).fetchall()
    except sqlite3.Error:
        conn.close()
        return {"available": False, "summary": {}, "daily": [], "rarity": [], "top_items": [], "top_draws": []}

    daily_map = {row[0]: row for row in daily_rows}
    daily = []
    for day in dates:
        row = daily_map.get(day)
        daily.append(
            {
                "date": day,
                "draws": row[1] if row else 0,
                "users": row[2] if row else 0,
                "value": row[3] if row else 0,
            }
        )
    conn.close()

    return {
        "available": True,
        "summary": {
            "draws": summary_row[0] if summary_row else 0,
            "users": summary_row[1] if summary_row else 0,
            "total_value": summary_row[2] if summary_row else 0,
            "average_value": round(summary_row[3], 1) if summary_row else 0,
            "max_value": summary_row[4] if summary_row else 0,
        },
        "daily": daily,
        "rarity": [
            {"rarity": row[0] or "未知", "count": row[1], "average_price": round(row[2], 1)}
            for row in rarity_rows
        ],
        "top_items": [
            {"item": row[0] or "未知", "count": row[1], "max_price": row[2]}
            for row in item_rows
        ],
        "top_draws": [
            {
                "item": row[0] or "未知",
                "rarity": row[1] or "未知",
                "price": row[2],
                "user_id": row[3],
                "group_id": row[4],
                "date": row[5],
            }
            for row in draw_rows
        ],
    }


def get_operations(days: int | str = 7) -> dict[str, Any]:
    days = _clamp_days(days)
    dates = _date_range(days)
    return {
        "days": days,
        "start": dates[0],
        "end": dates[-1],
        "lottery": _lottery_report(days, dates),
        "note": "开箱统计只计算状态为 completed 的记录。",
    }
