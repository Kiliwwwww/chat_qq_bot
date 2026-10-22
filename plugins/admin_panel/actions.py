from __future__ import annotations

import asyncio
import io
import sqlite3
import tempfile
import time
import zipfile
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "log"
DATA_DIR = PROJECT_ROOT / "data"
CHAT_LOG_DIR = DATA_DIR / "chat_logs"

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
ACTION_META = {
    "news": {
        "label": "立即推送今日新闻",
        "description": "抓取微博热搜和知乎热榜并推送到所有群",
    },
    "meme_sync": {
        "label": "立即同步表情包",
        "description": "从奶-hub 增量下载表情包，已存在的文件会跳过",
    },
    "kb_upload": {
        "label": "立即执行知识库入库",
        "description": "上传昨日及更早的群聊记录与总结到 RAGFlow",
    },
}

ACTION_STATE: dict[str, dict[str, Any]] = {
    name: {
        "name": name,
        "status": "idle",
        "started_at": None,
        "finished_at": None,
        "elapsed_seconds": 0,
        "result": "",
        "error": "",
    }
    for name in ACTION_META
}
_ACTION_TASKS: set[asyncio.Task] = set()
_ACTION_GUARD = asyncio.Lock()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def get_scheduler_jobs() -> list[dict[str, Any]]:
    try:
        from nonebot_plugin_apscheduler import scheduler
    except Exception as exc:
        return [{"id": "unavailable", "name": "调度器不可用", "trigger": str(exc), "next_run_time": ""}]

    jobs = []
    for job in scheduler.get_jobs():
        next_run = getattr(job, "next_run_time", None)
        jobs.append(
            {
                "id": job.id,
                "name": job.name or job.id,
                "func": getattr(job.func, "__name__", ""),
                "trigger": str(job.trigger),
                "next_run_time": next_run.isoformat(timespec="seconds") if next_run else "",
            }
        )
    jobs.sort(key=lambda item: (item["next_run_time"] == "", item["next_run_time"], item["id"]))
    return jobs


def get_action_states() -> list[dict[str, Any]]:
    actions = []
    for name, meta in ACTION_META.items():
        state = dict(ACTION_STATE[name])
        state.update(meta)
        actions.append(state)
    return actions


async def _execute_action(name: str) -> str:
    if name == "news":
        from plugins.chat_ai.commands.scheduler import daily_news_push

        return await daily_news_push()
    if name == "kb_upload":
        from nonebot import get_plugin_config
        from plugins.chat_ai.commands.scheduler import daily_kb_upload
        from plugins.chat_ai.config import Config as ChatAIConfig

        if not get_plugin_config(ChatAIConfig).ragflow_enabled:
            return "RAGFlow 未启用，已跳过知识库入库"
        await daily_kb_upload()
        return "知识库入库任务已执行，详情见日志"
    if name == "meme_sync":
        from plugins.meme_sync import _summary_text, _sync_now

        result = await _sync_now()
        return _summary_text(result)
    raise ValueError(f"未知操作: {name}")


async def start_action(name: str) -> dict[str, Any]:
    if name not in ACTION_META:
        raise ValueError(f"未知操作: {name}")
    async with _ACTION_GUARD:
        state = ACTION_STATE[name]
        if state["status"] == "running":
            raise RuntimeError("该操作正在执行中")
        state.update(
            status="running",
            started_at=_now_iso(),
            finished_at=None,
            elapsed_seconds=0,
            result="",
            error="",
        )
        task = asyncio.create_task(_run_action(name))
        _ACTION_TASKS.add(task)
        task.add_done_callback(_ACTION_TASKS.discard)
        return dict(state)


async def _run_action(name: str) -> None:
    started = time.perf_counter()
    state = ACTION_STATE[name]
    try:
        result = await _execute_action(name)
        state["result"] = result
    except Exception as exc:
        state["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        state["elapsed_seconds"] = round(time.perf_counter() - started, 2)
        state["finished_at"] = _now_iso()
        state["status"] = "error" if state["error"] else "success"


def _safe_file(base: Path, name: str) -> Path:
    if not name or Path(name).name != name:
        raise ValueError("非法文件名")
    base_resolved = base.resolve()
    path = (base / name).resolve()
    if base_resolved not in path.parents or not path.is_file():
        raise ValueError("文件不存在")
    return path


def resolve_file(base: Path, name: str) -> Path:
    return _safe_file(base, name)


def _tail_text(path: Path, max_bytes: int = 512 * 1024) -> tuple[str, bool]:
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > max_bytes:
            handle.seek(-max_bytes, 2)
        data = handle.read()
    return data.decode("utf-8", errors="replace"), size > max_bytes


def list_files(base: Path, suffixes: set[str], limit: int = 500) -> list[dict[str, Any]]:
    if not base.exists():
        return []
    files = []
    for path in base.iterdir():
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        stat = path.stat()
        files.append(
            {
                "name": path.name,
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                "mtime": stat.st_mtime,
            }
        )
    files.sort(key=lambda item: item["mtime"], reverse=True)
    for item in files:
        item.pop("mtime", None)
    return files[:limit]


def _search_file(
    path: Path,
    name: str,
    limit: int,
    keyword: str,
    level: str,
) -> dict[str, Any]:
    matched: deque[str] = deque(maxlen=limit)
    total = 0
    with path.open("rb") as handle:
        for raw in handle:
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if level and level not in line.upper():
                continue
            if keyword and keyword not in line.lower():
                continue
            total += 1
            matched.append(line)
    selected = list(matched)
    return {
        "name": name,
        "content": "\n".join(selected),
        "returned_lines": len(selected),
        "matched_lines": total,
        "truncated": total > len(selected),
        "mode": "search",
        "size": path.stat().st_size,
    }


def read_tail_file(
    base: Path,
    name: str,
    lines: int = 200,
    keyword: str = "",
    level: str = "",
    full: bool = False,
) -> dict[str, Any]:
    path = _safe_file(base, name)
    lines = max(1, min(lines, 5000))
    keyword = keyword.strip()
    level = level.strip().upper()
    if full and (keyword or level):
        return _search_file(path, name, lines, keyword.lower(), level)

    text, truncated = _tail_text(path)
    all_lines = text.splitlines()
    if level:
        all_lines = [line for line in all_lines if level in line.upper()]
    if keyword:
        all_lines = [line for line in all_lines if keyword.lower() in line.lower()]
    selected = all_lines[-lines:]
    return {
        "name": name,
        "content": "\n".join(selected),
        "returned_lines": len(selected),
        "matched_lines": len(all_lines),
        "truncated": truncated,
        "mode": "tail",
        "size": path.stat().st_size,
    }


def _dir_stats(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "count": 0, "bytes": 0, "last_modified": ""}
    count = 0
    total = 0
    latest = 0.0
    for item in path.rglob("*"):
        if not item.is_file() or item.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        try:
            stat = item.stat()
        except OSError:
            continue
        count += 1
        total += stat.st_size
        latest = max(latest, stat.st_mtime)
    return {
        "path": str(path),
        "exists": True,
        "count": count,
        "bytes": total,
        "last_modified": datetime.fromtimestamp(latest).astimezone().isoformat(timespec="seconds") if latest else "",
    }


def get_meme_stats() -> dict[str, Any]:
    return {
        "naihub": _dir_stats(DATA_DIR / "naihub-img"),
        "pighub": _dir_stats(DATA_DIR / "pighub-img"),
    }


def _sqlite_backup(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        target_conn = sqlite3.connect(str(target))
        try:
            source_conn.backup(target_conn)
        finally:
            target_conn.close()
    finally:
        source_conn.close()


def _build_backup() -> bytes:
    items: list[tuple[str, Path]] = []
    try:
        from plugins.chat_ai.state import db

        items.append(("chat_ai.db", Path(db.db_path)))
    except Exception:
        pass
    items.extend(
        [
            ("xiuxian.db", DATA_DIR / "xiuxian" / "xiuxian.db"),
            ("lottery.db", DATA_DIR / "lottery" / "lottery.db"),
            ("meme_groups.json", DATA_DIR / "meme_sync" / "groups.json"),
            ("pig.json", DATA_DIR / "pig.json"),
        ]
    )

    buffer = io.BytesIO()
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            written = []
            for name, source in items:
                if not source.exists() or not source.is_file():
                    continue
                target = temp_path / name
                try:
                    if source.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
                        _sqlite_backup(source, target)
                    else:
                        target.write_bytes(source.read_bytes())
                except Exception:
                    try:
                        target.write_bytes(source.read_bytes())
                    except Exception:
                        continue
                archive.write(target, arcname=f"data/{name}")
                written.append(name)
            manifest = [
                "QQ Bot 数据备份",
                f"生成时间: {_now_iso()}",
                "说明: 仅备份数据库和少量业务 JSON，不包含 .env、日志和表情包图片。",
                "",
                "已备份:",
                *[f"- {name}" for name in written],
            ]
            archive.writestr("README.txt", "\n".join(manifest))
    return buffer.getvalue()


async def create_backup() -> bytes:
    return await asyncio.to_thread(_build_backup)
