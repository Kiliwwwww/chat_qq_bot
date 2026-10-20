from __future__ import annotations

import asyncio
import codecs
import json
import os
import time
from pathlib import Path

from fastapi import Request
from starlette.responses import StreamingResponse

TAIL_BYTES = 512 * 1024
READ_CHUNK = 64 * 1024
POLL_SECONDS = 0.4
HEARTBEAT_SECONDS = 15.0
MAX_PARTIAL_CHARS = 1024 * 1024


def _sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _tail_text(path: Path, max_bytes: int = TAIL_BYTES) -> str:
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > max_bytes:
            handle.seek(-max_bytes, 2)
        data = handle.read()
    return data.decode("utf-8", errors="replace")


def _file_identity(handle, path: Path) -> tuple[int, int]:
    try:
        stat = os.fstat(handle.fileno())
        return (stat.st_ino, stat.st_dev)
    except (OSError, AttributeError):
        try:
            stat = path.stat()
            return (stat.st_ino, stat.st_dev)
        except OSError:
            return (0, 0)


async def stream_log_file(
    request: Request,
    path: Path,
    initial_lines: int = 100,
) -> StreamingResponse:
    initial_lines = max(0, min(initial_lines, 1000))

    async def event_generator():
        handle = None
        try:
            text = await asyncio.to_thread(_tail_text, path)
            lines = text.splitlines()
            initial = lines[-initial_lines:] if initial_lines else []
            stat = path.stat()
            yield _sse("ready", {"file": path.name, "size": stat.st_size})

            position = stat.st_size
            handle = path.open("rb")
            handle.seek(position)
            identity = _file_identity(handle, path)
            decoder = codecs.getincrementaldecoder("utf-8")("replace")
            buffer = ""

            if initial:
                yield _sse("initial", {"lines": initial, "truncated": len(lines) > len(initial)})

            last_heartbeat = time.monotonic()
            while True:
                if await request.is_disconnected():
                    break

                chunk = handle.read(READ_CHUNK)
                if chunk:
                    buffer += decoder.decode(chunk)
                    parts = buffer.split("\n")
                    buffer = parts.pop()
                    if len(buffer) > MAX_PARTIAL_CHARS:
                        parts.append(buffer)
                        buffer = ""
                    if parts:
                        yield _sse("lines", {"lines": [line.rstrip("\r") for line in parts]})
                    continue

                now = time.monotonic()
                if now - last_heartbeat >= HEARTBEAT_SECONDS:
                    yield ": ping\n\n"
                    last_heartbeat = now

                await asyncio.sleep(POLL_SECONDS)

                try:
                    current = path.stat()
                except OSError:
                    await asyncio.sleep(1.0)
                    continue

                if (current.st_ino, current.st_dev) != identity or current.st_size < handle.tell():
                    yield _sse("reset", {"message": "日志文件已切换或截断，正在从新文件继续读取"})
                    handle.close()
                    handle = path.open("rb")
                    handle.seek(0)
                    identity = _file_identity(handle, path)
                    decoder = codecs.getincrementaldecoder("utf-8")("replace")
                    buffer = ""
                    continue

                if current.st_size == handle.tell():
                    continue

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            try:
                yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})
            except Exception:
                pass
        finally:
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
