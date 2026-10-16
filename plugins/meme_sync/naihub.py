"""奶-hub（nai-hub.com）表情包同步核心逻辑。

站点本身是静态页面，图片并不写在 HTML 里，而是由前端读取 data/manifest.json
和各分类的 JSON 清单后，再从 GitHub 仓库取原图。所以这里直接读这些清单，
比模拟浏览器抓 DOM 更快也更稳。

本模块只依赖标准库、不导入 nonebot，可以被定时任务和命令行脚本共用：
    - 定时任务：plugins/meme_sync/__init__.py
    - 命令行：download_naihub.py
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

SITE = "https://nai-hub.com"
DATA_BASE = f"{SITE}/data/"
MANIFEST = f"{DATA_BASE}manifest.json"

# GitHub 上存放原图的仓库名固定为 NaiLoong，owner 随每位贡献者而不同。
GH_REPO_NAME = "NaiLoong"
RAW_PREFIX = "https://raw.githubusercontent.com/"

# raw.githubusercontent.com 在部分网络下会被墙，这几个镜像与站点前端用的是同一组。
PROXIES = [
    "https://gh-proxy.com/{u}",
    "https://ghproxy.net/{u}",
    "https://ghfast.top/{u}",
]
PROBE_URL = f"{RAW_PREFIX}lin-alg/{GH_REPO_NAME}/main/assets/icons/favicon.svg"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

# 日志回调：(level, message)，level 为 info / detail / error
LogFn = Callable[[str, str], None]


def _noop_log(level: str, message: str) -> None:
    """默认不打日志。"""


def _as_filter_list(value: str | Sequence[str] | None) -> list[str] | None:
    """把 "naiwa,naidan" 或 ["naiwa"] 统一成小写列表。"""
    if value is None:
        return None
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    else:
        items = [str(part).strip() for part in value]
    items = [item.lower() for item in items if item]
    return items or None


# --------------------------------------------------------------------------
# 网络
# --------------------------------------------------------------------------

def _fetch_bytes(url: str, timeout: float = 20.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _fetch_json(url: str, timeout: float = 20.0) -> Any:
    return json.loads(_fetch_bytes(url, timeout).decode("utf-8"))


# --------------------------------------------------------------------------
# 清单解析
# --------------------------------------------------------------------------

def to_raw_url(url: str) -> str:
    """把清单里的地址统一成 raw.githubusercontent.com 直链。

    清单里出现过三种写法：
      1. owner/commit/path                              （目前最常见）
      2. https://github.com/owner/repo/blob/ref/path
      3. https://raw.githubusercontent.com/owner/repo/ref/path
    """
    if not isinstance(url, str):
        return ""
    clean = url.strip().split("?")[0].split("#")[0]

    m = re.match(r"^([A-Za-z0-9-]+)/([0-9a-f]{40})/(.+)$", clean, re.I)
    if m:
        return f"{RAW_PREFIX}{m.group(1).lower()}/{GH_REPO_NAME}/{m.group(2).lower()}/{m.group(3)}"

    m = re.match(r"^https?://github\.com/([^/?#]+)/([^/?#]+)/(?:blob|raw)/([^/?#]+)/(.+)$", clean)
    if m:
        return f"{RAW_PREFIX}{m.group(1).lower()}/{m.group(2)}/{m.group(3)}/{m.group(4)}"

    m = re.match(r"^https?://raw\.githubusercontent\.com/([^/?#]+)/([^/?#]+)/([^/?#]+)/(.+)$", clean)
    if m:
        return f"{RAW_PREFIX}{m.group(1).lower()}/{m.group(2)}/{m.group(3)}/{m.group(4)}"

    return clean


def collect_items(
    chars: str | Sequence[str] | None = None,
    subs: str | Sequence[str] | None = None,
    log: LogFn | None = None,
) -> list[dict[str, Any]]:
    """读取 manifest 与各分类清单，返回待下载条目。"""
    log = log or _noop_log
    char_filter = _as_filter_list(chars)
    sub_filter = _as_filter_list(subs)

    manifest = _fetch_json(MANIFEST)
    if not isinstance(manifest, list):
        raise RuntimeError("manifest.json 格式异常")

    items: list[dict[str, Any]] = []
    for meta in manifest:
        char_id = str(meta.get("id") or "")
        char_name = str(meta.get("name") or char_id)
        if char_filter and char_id.lower() not in char_filter:
            continue
        for sub in meta.get("subcategories") or []:
            sub_id = str(sub.get("id") or "")
            if sub_filter and sub_id.lower() not in sub_filter:
                continue
            file_name = sub.get("file")
            if not file_name:
                continue
            try:
                entries = _fetch_json(DATA_BASE + file_name)
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
                log("error", f"跳过 {file_name}：{exc}")
                continue
            if not isinstance(entries, list):
                continue
            for entry in entries:
                raw_url = to_raw_url(entry.get("url", ""))
                if not raw_url:
                    continue
                items.append(
                    {
                        "char_id": char_id,
                        "char_name": char_name,
                        "sub_id": sub_id,
                        "sub_name": str(sub.get("name") or sub_id),
                        "title": str(entry.get("title") or "").strip(),
                        "tags": entry.get("tags") or [],
                        "src_path": str(entry.get("url") or ""),
                        "raw_url": raw_url,
                    }
                )
    return items


def group_items(items: Iterable[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """按 (角色名, 分类名) 分组，保持清单原有顺序。"""
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault((item["char_name"], item["sub_name"]), []).append(item)
    return grouped


# --------------------------------------------------------------------------
# 文件名
# --------------------------------------------------------------------------

_ILLEGAL = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_name(text: str, limit: int = 60) -> str:
    name = _ILLEGAL.sub("_", str(text)).strip(" .")
    if len(name) > limit:
        name = name[:limit].rstrip(" .")
    return name


def build_filename(item: dict[str, Any], used: set[str]) -> str:
    """用「原始编号_中文标题」拼文件名，重名时追加序号。"""
    src_path = item["src_path"].split("?")[0]
    stem = os.path.splitext(os.path.basename(src_path))[0] or "meme"
    ext = os.path.splitext(src_path)[1].lower()
    if ext not in IMAGE_EXT:
        ext = ".jpg"
    stem = safe_name(stem, 40)
    title = safe_name(item["title"])
    base = f"{stem}_{title}" if title else stem

    name = base + ext
    idx = 2
    while name in used:
        name = f"{base}_{idx}{ext}"
        idx += 1
    used.add(name)
    return name


# --------------------------------------------------------------------------
# 下载入口探测
# --------------------------------------------------------------------------

def build_routes(route: str | None = None, log: LogFn | None = None) -> list[str]:
    """返回候选下载入口模板列表（{u} 替换为原图地址），可用的排在前面。"""
    log = log or _noop_log
    direct = "{u}"
    all_routes = [direct] + PROXIES

    if route == "direct":
        return [direct]

    if route in (None, "auto"):
        order = list(all_routes)
    elif re.fullmatch(r"p\d+", route or "") and 0 <= int(route[1:]) < len(PROXIES):
        picked = PROXIES[int(route[1:])]
        order = [picked] + [t for t in all_routes if t != picked]
    else:
        if route not in (None, "auto"):
            log("error", f"未知下载入口 {route}，改用自动探测。")
        order = list(all_routes)

    for tpl in order:
        try:
            _fetch_bytes(tpl.replace("{u}", PROBE_URL), timeout=8.0)
        except Exception:  # noqa: BLE001 - 探测失败就换下一个入口
            continue
        label = "直连 raw.githubusercontent.com" if tpl == direct else tpl.replace("/{u}", "")
        log("info", f"下载入口：{label}")
        return [tpl] + [t for t in all_routes if t != tpl]

    log("error", "所有下载入口探测均失败，将按原顺序逐个重试。")
    return order


def looks_like_image(data: bytes) -> bool:
    return (
        data[:2] == b"\xff\xd8"                       # jpg
        or data[:8] == b"\x89PNG\r\n\x1a\n"           # png
        or data[:6] in (b"GIF87a", b"GIF89a")         # gif
        or data[8:12] == b"WEBP"                      # webp
        or data[:2] == b"BM"                          # bmp
    )


def download_one(
    item: dict[str, Any],
    dest: Path,
    routes: list[str],
    timeout: float,
    force: bool = False,
    retries: int = 3,
) -> tuple[str, int, str]:
    """下载单张图片，返回 (状态, 字节数, 错误信息)；状态为 ok / skip / fail。"""
    if dest.exists() and dest.stat().st_size > 0 and not force:
        return "skip", 0, ""

    last_err = "未知错误"
    for attempt in range(retries):
        tpl = routes[attempt % len(routes)]
        url = tpl.replace("{u}", item["raw_url"])
        try:
            data = _fetch_bytes(url, timeout=timeout)
            if len(data) < 64:
                raise ValueError(f"内容过短（{len(data)} 字节）")
            if not looks_like_image(data):
                raise ValueError("返回内容不是图片")
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".part")
            tmp.write_bytes(data)
            tmp.replace(dest)
            return "ok", len(data), ""
        except Exception as exc:  # noqa: BLE001 - 换入口重试
            last_err = str(exc)
            time.sleep(0.4 * (attempt + 1))
    return "fail", 0, last_err


# --------------------------------------------------------------------------
# 同步入口
# --------------------------------------------------------------------------

def sync(
    out_dir: str | Path,
    *,
    chars: str | Sequence[str] | None = None,
    subs: str | Sequence[str] | None = None,
    workers: int = 8,
    timeout: float = 30.0,
    route: str = "auto",
    flat: bool = False,
    overwrite: bool = False,
    log: LogFn | None = None,
) -> dict[str, Any]:
    """增量同步表情包：已存在的文件直接跳过，只下载新增内容。

    返回统计字典：total / ok / skip / fail / bytes / failures / new_files /
    out_dir / index_path / elapsed。
    """
    log = log or _noop_log
    started = time.time()
    out_root = Path(out_dir).expanduser()

    log("info", "读取清单…")
    items = collect_items(chars, subs, log=log)
    if not items:
        log("error", "没有匹配的图片，请检查角色/分类筛选配置。")
        return {
            "total": 0, "ok": 0, "skip": 0, "fail": 0, "bytes": 0,
            "failures": [], "new_files": [], "out_dir": str(out_root),
            "index_path": "", "elapsed": round(time.time() - started, 1),
        }

    routes = build_routes(route, log=log)

    jobs: list[tuple[dict[str, Any], Path]] = []
    used_names: dict[Path, set[str]] = {}
    for (char_name, sub_name), rows in group_items(items).items():
        folder = out_root if flat else out_root / safe_name(char_name, 30) / safe_name(sub_name, 30)
        used = used_names.setdefault(folder, set())
        for row in rows:
            jobs.append((row, folder / build_filename(row, used)))

    counter = {"ok": 0, "skip": 0, "fail": 0, "bytes": 0}
    failures: list[dict[str, str]] = []
    new_files: list[str] = []
    record: list[dict[str, Any]] = []
    done = 0

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(download_one, row, dest, routes, timeout, overwrite): (row, dest)
            for row, dest in jobs
        }
        for future in as_completed(futures):
            row, dest = futures[future]
            status, size, err = future.result()
            done += 1
            rel = dest.name if flat else str(dest.relative_to(out_root))
            if status == "ok":
                counter["ok"] += 1
                counter["bytes"] += size
                new_files.append(rel)
                log("detail", f"[{done}/{len(jobs)}] 完成 {dest.name}（{size / 1024:.0f} KB）")
            elif status == "skip":
                counter["skip"] += 1
                log("detail", f"[{done}/{len(jobs)}] 已存在，跳过 {dest.name}")
            else:
                counter["fail"] += 1
                failures.append({"title": row["title"], "url": row["raw_url"], "error": err})
                log("error", f"[{done}/{len(jobs)}] 失败 {row['title']}（{err}）")
            record.append(
                {
                    "file": rel,
                    "title": row["title"],
                    "char": row["char_name"],
                    "category": row["sub_name"],
                    "tags": row["tags"],
                    "source": row["raw_url"],
                    "status": status,
                }
            )

    out_root.mkdir(parents=True, exist_ok=True)
    index_path = out_root / "_index.json"
    index_path.write_text(
        json.dumps(
            {
                "site": SITE,
                "synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total": len(jobs),
                "items": sorted(record, key=lambda r: r["file"]),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "total": len(jobs),
        "ok": counter["ok"],
        "skip": counter["skip"],
        "fail": counter["fail"],
        "bytes": counter["bytes"],
        "failures": failures,
        "new_files": sorted(new_files),
        "out_dir": str(out_root),
        "index_path": str(index_path),
        "elapsed": round(time.time() - started, 1),
    }
