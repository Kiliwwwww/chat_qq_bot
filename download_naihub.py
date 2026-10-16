#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""奶-hub（nai-hub.com）表情包批量下载脚本。

站点本身是静态页面，图片并不写在 HTML 里，而是由前端读取 data/manifest.json
和各分类的 JSON 清单后，再从 GitHub 仓库取原图。所以本脚本直接读这些清单，
比用浏览器抓 DOM 更快也更稳。

用法示例：
    python download_naihub.py --list              # 只列出清单，不下载
    python download_naihub.py                     # 下载全部到 data/naihub-img/
    python download_naihub.py --char naiwa        # 只下奶蛙
    python download_naihub.py --sub animated      # 只下动图
    python download_naihub.py --route direct      # 强制直连，不走镜像加速

只依赖 Python 标准库。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

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

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def fetch_bytes(url: str, timeout: float = 20.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_json(url: str, timeout: float = 20.0) -> Any:
    return json.loads(fetch_bytes(url, timeout).decode("utf-8"))


# --------------------------------------------------------------------------
# 清单解析
# --------------------------------------------------------------------------

def to_raw_url(url: str) -> str:
    """把清单里的地址统一成 raw.githubusercontent.com 直链。

    清单里出现过三种写法：
      1. owner/commit/path                              （目前最常见）
      2. https://github.com/owner/repo/blob/ref/path     （ref 可能是 commit 短号）
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


def collect_items(chars: list[str] | None, subs: list[str] | None) -> list[dict[str, Any]]:
    """读取 manifest 与各分类清单，返回待下载条目。"""
    manifest = fetch_json(MANIFEST)
    if not isinstance(manifest, list):
        raise RuntimeError("manifest.json 格式异常")

    items: list[dict[str, Any]] = []
    for meta in manifest:
        char_id = str(meta.get("id") or "")
        char_name = str(meta.get("name") or char_id)
        if chars and char_id.lower() not in chars:
            continue
        for sub in meta.get("subcategories") or []:
            sub_id = str(sub.get("id") or "")
            if subs and sub_id.lower() not in subs:
                continue
            file_name = sub.get("file")
            if not file_name:
                continue
            try:
                entries = fetch_json(DATA_BASE + file_name)
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
                log(f"  跳过 {file_name}：{exc}")
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

def build_routes(route: str | None) -> list[str]:
    """返回候选下载入口模板列表（{u} 替换为原图地址），可用的排在前面。"""
    direct = "{u}"
    all_routes = [direct] + PROXIES

    if route == "direct":
        return [direct]

    order: list[str] = []
    if route in (None, "auto"):
        order = list(all_routes)
    elif re.fullmatch(r"p\d+", route or ""):
        idx = int(route[1:])
        if 0 <= idx < len(PROXIES):
            order = [PROXIES[idx]] + [t for t in all_routes if t != PROXIES[idx]]
        else:
            log(f"未知入口 {route}，改用自动探测。")
            order = list(all_routes)
    else:
        log(f"未知入口 {route}，改用自动探测。")
        order = list(all_routes)

    for tpl in order:
        try:
            fetch_bytes(tpl.replace("{u}", PROBE_URL), timeout=8.0)
        except Exception:  # noqa: BLE001 - 探测失败就换下一个入口
            continue
        label = "直连 raw.githubusercontent.com" if tpl == direct else tpl.replace("/{u}", "")
        log(f"下载入口：{label}")
        return [tpl] + [t for t in all_routes if t != tpl]

    log("警告：所有入口探测均失败，将按原顺序逐个重试。")
    return order


def looks_like_image(data: bytes) -> bool:
    return (
        data[:2] == b"\xff\xd8"                       # jpg
        or data[:8] == b"\x89PNG\r\n\x1a\n"           # png
        or data[:6] in (b"GIF87a", b"GIF89a")         # gif
        or data[8:12] == b"WEBP"                      # webp
        or data[:2] == b"BM"                          # bmp
    )


def download_one(item: dict[str, Any], dest: Path, routes: list[str], timeout: float,
                 force: bool = False, retries: int = 3) -> tuple[str, int]:
    """下载单张图片，返回 (状态, 字节数)；状态为 ok / skip / fail。"""
    if dest.exists() and dest.stat().st_size > 0 and not force:
        return "skip", 0

    last_err = "未知错误"
    for attempt in range(retries):
        tpl = routes[attempt % len(routes)]
        url = tpl.replace("{u}", item["raw_url"])
        try:
            data = fetch_bytes(url, timeout=timeout)
            if len(data) < 64:
                raise ValueError(f"内容过短（{len(data)} 字节）")
            if not looks_like_image(data):
                raise ValueError("返回内容不是图片")
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".part")
            tmp.write_bytes(data)
            tmp.replace(dest)
            return "ok", len(data)
        except Exception as exc:  # noqa: BLE001 - 换入口重试
            last_err = str(exc)
            time.sleep(0.4 * (attempt + 1))
    log(f"    重试结束仍失败（{last_err}）")
    return "fail", 0


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(
        description="批量下载奶-hub（nai-hub.com）表情包",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--out", default="data/naihub-img",
                        help="保存目录（默认 data/naihub-img）")
    parser.add_argument("--char", default="",
                        help="只下指定角色，逗号分隔：naiwa,naidan,nai-emblem,others")
    parser.add_argument("--sub", default="",
                        help="只下指定分类，逗号分隔：animated,static")
    parser.add_argument("--workers", type=int, default=8, help="并发数（默认 8）")
    parser.add_argument("--timeout", type=float, default=30.0, help="单张超时秒数（默认 30）")
    parser.add_argument("--route", default="auto",
                        help="下载入口：auto（默认自动探测）/ direct（直连）/ p0 p1 p2（指定镜像）")
    parser.add_argument("--flat", action="store_true", help="不建角色/分类子目录，全部平铺")
    parser.add_argument("--list", action="store_true", help="只列出清单，不下载")
    parser.add_argument("--overwrite", action="store_true", help="已存在也重新下载")
    args = parser.parse_args(argv)

    chars = [c.strip().lower() for c in args.char.split(",") if c.strip()] or None
    subs = [s.strip().lower() for s in args.sub.split(",") if s.strip()] or None

    print("读取清单…", flush=True)
    try:
        items = collect_items(chars, subs)
    except Exception as exc:  # noqa: BLE001
        print(f"读取清单失败：{exc}")
        print("若提示连接被拒绝，请检查网络或代理设置后重试。")
        return 1

    if not items:
        print("没有匹配的图片，请检查 --char / --sub 参数。")
        return 1

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault((item["char_name"], item["sub_name"]), []).append(item)

    if args.list:
        for (char_name, sub_name), rows in grouped.items():
            print(f"\n{char_name} / {sub_name}（{len(rows)} 张）")
            for row in rows:
                print(f"  - {row['title'] or os.path.basename(row['src_path'])}")
        print(f"\n合计 {len(items)} 张")
        return 0

    out_root = Path(args.out).expanduser()
    routes = build_routes(args.route)

    print(f"共 {len(items)} 张 → {out_root.resolve()}（并发 {args.workers}）")

    jobs: list[tuple[dict[str, Any], Path]] = []
    used_names: dict[Path, set[str]] = {}
    for (char_name, sub_name), rows in grouped.items():
        folder = out_root if args.flat else out_root / safe_name(char_name, 30) / safe_name(sub_name, 30)
        used = used_names.setdefault(folder, set())
        for row in rows:
            jobs.append((row, folder / build_filename(row, used)))

    counter = {"ok": 0, "skip": 0, "fail": 0, "bytes": 0}
    counter_lock = threading.Lock()
    record: list[dict[str, Any]] = []
    record_lock = threading.Lock()
    failures: list[str] = []
    done = 0

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(download_one, row, dest, routes, args.timeout, args.overwrite): (row, dest)
            for row, dest in jobs
        }
        for future in as_completed(futures):
            row, dest = futures[future]
            status, size = future.result()
            done += 1
            with counter_lock:
                if status == "ok":
                    counter["ok"] += 1
                    counter["bytes"] += size
                elif status == "skip":
                    counter["skip"] += 1
                else:
                    counter["fail"] += 1
                    failures.append(f"{row['title']} ← {row['raw_url']}")
            if status == "ok":
                log(f"[{done}/{len(jobs)}] 完成 {dest.name}（{size / 1024:.0f} KB）")
            elif status == "skip":
                log(f"[{done}/{len(jobs)}] 已存在，跳过 {dest.name}")
            else:
                log(f"[{done}/{len(jobs)}] 失败 {row['title']}")
            with record_lock:
                record.append(
                    {
                        "file": dest.name if args.flat else str(dest.relative_to(out_root)),
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
                "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total": len(jobs),
                "items": sorted(record, key=lambda r: r["file"]),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n完成：下载 {ok} 张（{mb:.1f} MB），跳过 {skip} 张，失败 {fail} 张".format(
        ok=counter["ok"], mb=counter["bytes"] / 1024 / 1024,
        skip=counter["skip"], fail=counter["fail"]))
    print(f"目录：{out_root.resolve()}")
    print(f"索引：{index_path}")
    if failures:
        print("失败清单：")
        for line in failures[:20]:
            print(f"  - {line}")
    return 1 if counter["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
