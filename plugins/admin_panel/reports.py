from __future__ import annotations

import re
import sqlite3
import threading
import time
from collections import Counter, defaultdict
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHAT_LOG_DIR = PROJECT_ROOT / "data" / "chat_logs"
AI_REQUEST_LOG = PROJECT_ROOT / "log" / "ai_request.log"
LOTTERY_DB = PROJECT_ROOT / "data" / "lottery" / "lottery.db"
XIUXIAN_DB = PROJECT_ROOT / "data" / "xiuxian" / "xiuxian.db"

REALM_NAMES = [
    "炼气",
    "筑基",
    "金丹",
    "元婴",
    "化神",
    "炼虚",
    "合体",
    "大乘",
    "渡劫",
    "飞升",
]

CHAT_FILE_RE = re.compile(r"^(\d+)_(\d{4}-\d{2}-\d{2})(?:_uploaded)?\.txt$")
CHAT_LINE_RE = re.compile(
    r"\[(\d{4}-\d{2}-\d{2}) (\d{2}):\d{2}:\d{2}\]\[([^\]]*)\]\[(\d+)\]"
)
AI_EVENT_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)$")
AI_REQUEST_RE = re.compile(
    r'^\{"timestamp":\s*"([^"]+)",\s*"model":\s*"([^"]+)"'
)
DURATION_RE = re.compile(r"耗时\s*([0-9.]+)s")

_chat_cache: dict[str, tuple[float, int, dict[str, Any]]] = {}
_chat_cache_lock = threading.Lock()

_ai_cache: dict[str, Any] = {"at": 0.0, "data": None}
_ai_cache_lock = threading.Lock()
_AI_CACHE_SECONDS = 30.0


def _clamp_days(days: int | str | None) -> int:
    try:
        return max(1, min(int(days or 7), 90))
    except (TypeError, ValueError):
        return 7


def _date_range(days: int) -> list[str]:
    end = date.today()
    start = end - timedelta(days=days - 1)
    return [(start + timedelta(days=offset)).isoformat() for offset in range(days)]


def _empty_ai_day() -> dict[str, float]:
    return {
        "attempts": 0,
        "success": 0,
        "failure": 0,
        "latency_sum": 0.0,
        "latency_count": 0,
    }


def _chat_file_aggregate(path: Path, group_id: int, day: str) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError:
        return {"group_id": group_id, "date": day, "total": 0, "hours": [0] * 24, "users": {}, "names": {}}

    key = str(path)
    with _chat_cache_lock:
        cached = _chat_cache.get(key)
        if cached and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
            return cached[2]

    text = path.read_text(encoding="utf-8", errors="replace")
    hours = [0] * 24
    users: Counter[str] = Counter()
    names: dict[str, str] = {}
    total = 0
    for match in CHAT_LINE_RE.finditer(text):
        line_day, hour_text, name, user_id = match.groups()
        if line_day != day:
            continue
        hour = int(hour_text)
        if hour < 0 or hour > 23:
            continue
        hours[hour] += 1
        users[user_id] += 1
        names[user_id] = name
        total += 1

    aggregate = {
        "group_id": group_id,
        "date": day,
        "total": total,
        "hours": hours,
        "users": dict(users),
        "names": names,
    }
    with _chat_cache_lock:
        if len(_chat_cache) > 3000:
            _chat_cache.clear()
        _chat_cache[key] = (stat.st_mtime, stat.st_size, aggregate)
    return aggregate


def _merge_group_aggregate(
    target: dict[str, Any],
    aggregate: dict[str, Any],
) -> None:
    day = aggregate["date"]
    target["daily"][day] += aggregate["total"]
    for hour, count in enumerate(aggregate["hours"]):
        target["daily_hours"][day][hour] += count
    target["users"].update(aggregate["users"])
    target["names"].update(aggregate["names"])


def _new_group_aggregate() -> dict[str, Any]:
    return {
        "daily": Counter(),
        "daily_hours": defaultdict(lambda: [0] * 24),
        "users": Counter(),
        "names": {},
    }


def get_group_activity(days: int | str = 7, group_id: str = "all") -> dict[str, Any]:
    days = _clamp_days(days)
    dates = _date_range(days)
    start, end = dates[0], dates[-1]

    all_groups: set[int] = set()
    files: list[tuple[Path, int, str]] = []
    if CHAT_LOG_DIR.exists():
        for path in CHAT_LOG_DIR.glob("*.txt"):
            match = CHAT_FILE_RE.match(path.name)
            if not match:
                continue
            gid = int(match.group(1))
            day = match.group(2)
            if day < start or day > end:
                continue
            all_groups.add(gid)
            files.append((path, gid, day))
    files.sort(key=lambda item: (item[2], item[1]))

    by_group: dict[int, dict[str, Any]] = defaultdict(_new_group_aggregate)
    for path, gid, day in files:
        aggregate = _chat_file_aggregate(path, gid, day)
        _merge_group_aggregate(by_group[gid], aggregate)

    selected_gid: int | None = None
    if group_id not in ("", "all", None):
        try:
            selected_gid = int(group_id)
        except (TypeError, ValueError):
            selected_gid = None

    if selected_gid is None:
        selected = _new_group_aggregate()
        for aggregate in by_group.values():
            for day, count in aggregate["daily"].items():
                selected["daily"][day] += count
            for day, hours in aggregate["daily_hours"].items():
                for hour, count in enumerate(hours):
                    selected["daily_hours"][day][hour] += count
            selected["users"].update(aggregate["users"])
            selected["names"].update(aggregate["names"])
        active_groups = len(by_group)
    else:
        selected = by_group.get(selected_gid, _new_group_aggregate())
        active_groups = 1 if selected_gid in by_group else 0

    daily = [
        {"date": day, "count": selected["daily"].get(day, 0)}
        for day in dates
    ]
    hourly = [0] * 24
    heatmap = []
    for day_index, day in enumerate(dates):
        day_hours = selected["daily_hours"].get(day, [0] * 24)
        for hour, count in enumerate(day_hours):
            hourly[hour] += count
            heatmap.append([day_index, hour, count])

    top_users = [
        {
            "user_id": user_id,
            "name": selected["names"].get(user_id) or user_id,
            "count": count,
        }
        for user_id, count in selected["users"].most_common(10)
    ]

    group_ranking = []
    for gid, aggregate in by_group.items():
        group_ranking.append(
            {
                "group_id": gid,
                "count": sum(aggregate["daily"].values()),
                "users": len(aggregate["users"]),
            }
        )
    group_ranking.sort(key=lambda item: item["count"], reverse=True)

    total = sum(item["count"] for item in daily)
    return {
        "days": days,
        "start": start,
        "end": end,
        "groups": sorted(all_groups),
        "selected_group": selected_gid if selected_gid is not None else "all",
        "summary": {
            "messages": total,
            "active_groups": active_groups,
            "active_users": len(selected["users"]),
            "average_daily": round(total / days, 1),
        },
        "daily": daily,
        "hourly": [{"hour": hour, "count": count} for hour, count in enumerate(hourly)],
        "heatmap": heatmap,
        "top_users": top_users,
        "group_ranking": group_ranking,
        "source_files": len(files),
        "note": "仅统计已开启知识库聊天记录（data/chat_logs）的群。",
    }


def _parse_ai_raw() -> dict[str, Any]:
    daily: dict[str, dict[str, float]] = defaultdict(_empty_ai_day)
    hourly: dict[str, list[int]] = defaultdict(lambda: [0] * 24)
    models: dict[str, Counter[str]] = defaultdict(Counter)
    errors: dict[str, Counter[str]] = defaultdict(Counter)

    if not AI_REQUEST_LOG.exists():
        return {
            "available": False,
            "daily": {},
            "hourly": {},
            "models": {},
            "errors": {},
            "file_size": 0,
        }

    try:
        with AI_REQUEST_LOG.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if line.startswith('{"timestamp"'):
                    match = AI_REQUEST_RE.match(line)
                    if match:
                        timestamp, model = match.groups()
                        day = timestamp[:10]
                        models[day][model] += 1
                    continue

                match = AI_EVENT_RE.match(line)
                if not match:
                    continue
                timestamp, message = match.groups()
                day = timestamp[:10]
                if len(timestamp) < 13:
                    continue
                hour = int(timestamp[11:13]) if timestamp[11:13].isdigit() else 0

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
    except OSError:
        return {
            "available": False,
            "daily": {},
            "hourly": {},
            "models": {},
            "errors": {},
            "file_size": 0,
        }

    return {
        "available": True,
        "daily": dict(daily),
        "hourly": dict(hourly),
        "models": {day: dict(counter) for day, counter in models.items()},
        "errors": {day: dict(counter) for day, counter in errors.items()},
        "file_size": AI_REQUEST_LOG.stat().st_size,
    }


def _error_label(message: str) -> str:
    code = re.search(r"Error code:\s*(\d+)", message)
    if code:
        return f"HTTP {code.group(1)}"
    detail = re.search(r"耗时\s*[0-9.]+s:\s*(.*)", message)
    text = detail.group(1) if detail else message
    text = re.sub(r"\s*\(request id:.*", "", text).strip()
    return text[:140] or "未知错误"


def _ai_raw_cached() -> dict[str, Any]:
    now = time.time()
    with _ai_cache_lock:
        cached = _ai_cache.get("data")
        if cached is not None and now - _ai_cache["at"] < _AI_CACHE_SECONDS:
            return cached

    data = _parse_ai_raw()
    with _ai_cache_lock:
        _ai_cache["at"] = time.time()
        _ai_cache["data"] = data
    return data


def get_ai_usage(days: int | str = 7) -> dict[str, Any]:
    days = _clamp_days(days)
    dates = _date_range(days)
    raw = _ai_raw_cached()
    daily_raw = raw.get("daily", {})
    hourly_raw = raw.get("hourly", {})
    models_raw = raw.get("models", {})
    errors_raw = raw.get("errors", {})

    daily = []
    hourly = [0] * 24
    models: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    attempts = success = failure = 0
    latency_sum = 0.0
    latency_count = 0

    for day in dates:
        item = daily_raw.get(day) or _empty_ai_day()
        day_attempts = int(item["attempts"])
        day_success = int(item["success"])
        day_failure = int(item["failure"])
        day_latency_count = int(item["latency_count"])
        day_latency = round(item["latency_sum"] / day_latency_count, 2) if day_latency_count else 0
        attempts += day_attempts
        success += day_success
        failure += day_failure
        latency_sum += item["latency_sum"]
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
        day_hours = hourly_raw.get(day) or []
        for hour, count in enumerate(day_hours[:24]):
            hourly[hour] += count
        models.update(models_raw.get(day, {}))
        errors.update(errors_raw.get(day, {}))

    average_latency = round(latency_sum / latency_count, 2) if latency_count else 0
    success_rate = round(success / attempts * 100, 1) if attempts else 0
    return {
        "days": days,
        "start": dates[0],
        "end": dates[-1],
        "available": raw.get("available", False),
        "file_size": raw.get("file_size", 0),
        "summary": {
            "attempts": attempts,
            "success": success,
            "failure": failure,
            "success_rate": success_rate,
            "average_latency": average_latency,
        },
        "daily": daily,
        "hourly": [{"hour": hour, "count": count} for hour, count in enumerate(hourly)],
        "models": [
            {"model": model, "count": count}
            for model, count in models.most_common(12)
        ],
        "errors": [
            {"message": message, "count": count}
            for message, count in errors.most_common(10)
        ],
        "note": "AI 报表来自 log/ai_request.log；旧日志没有 token 用量，暂不统计成本。",
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


def _xiuxian_report(days: int, dates: list[str]) -> dict[str, Any]:
    conn = _connect_ro(XIUXIAN_DB)
    if conn is None:
        return {"available": False, "summary": {}, "realms": [], "groups": [], "daily_battles": []}

    try:
        start, end = dates[0], dates[-1]
        start_ts = datetime.combine(date.fromisoformat(start), dt_time.min).timestamp()
        total_players, total_groups = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT group_id) FROM players"
        ).fetchone()
        new_players = conn.execute(
            "SELECT COUNT(*) FROM players WHERE created_at >= ?",
            (start_ts,),
        ).fetchone()[0]
        realm_rows = conn.execute(
            "SELECT realm, COUNT(*) FROM players GROUP BY realm ORDER BY realm"
        ).fetchall()
        group_rows = conn.execute(
            "SELECT group_id, COUNT(*) FROM players GROUP BY group_id ORDER BY COUNT(*) DESC LIMIT 20"
        ).fetchall()
        battle_rows = conn.execute(
            "SELECT date_str, COUNT(DISTINCT user_id), COALESCE(SUM(count), 0) "
            "FROM battle_daily WHERE date_str BETWEEN ? AND ? GROUP BY date_str ORDER BY date_str",
            (start, end),
        ).fetchall()
        battle_summary = conn.execute(
            "SELECT COUNT(DISTINCT user_id), COALESCE(SUM(count), 0) "
            "FROM battle_daily WHERE date_str BETWEEN ? AND ?",
            (start, end),
        ).fetchone()
    except sqlite3.Error:
        conn.close()
        return {"available": False, "summary": {}, "realms": [], "groups": [], "daily_battles": []}

    conn.close()
    battle_map = {row[0]: row for row in battle_rows}
    daily_battles = []
    for day in dates:
        row = battle_map.get(day)
        daily_battles.append(
            {
                "date": day,
                "battles": row[2] if row else 0,
                "users": row[1] if row else 0,
            }
        )

    return {
        "available": True,
        "summary": {
            "players": total_players,
            "groups": total_groups,
            "new_players": new_players,
            "active_battle_users": battle_summary[0] if battle_summary else 0,
            "battles": battle_summary[1] if battle_summary else 0,
        },
        "realms": [
            {
                "realm": row[0],
                "name": REALM_NAMES[row[0]] if 0 <= row[0] < len(REALM_NAMES) else f"境界 {row[0]}",
                "count": row[1],
            }
            for row in realm_rows
        ],
        "groups": [{"group_id": row[0], "count": row[1]} for row in group_rows],
        "daily_battles": daily_battles,
    }


def get_operations(days: int | str = 7) -> dict[str, Any]:
    days = _clamp_days(days)
    dates = _date_range(days)
    return {
        "days": days,
        "start": dates[0],
        "end": dates[-1],
        "lottery": _lottery_report(days, dates),
        "xiuxian": _xiuxian_report(days, dates),
        "note": "开箱统计只计算状态为 completed 的记录；修仙数据为当前数据库快照。",
    }
