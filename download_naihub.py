#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""奶-hub（nai-hub.com）表情包批量下载脚本（命令行入口）。

下载逻辑在 plugins/meme_sync/naihub.py，机器人的每日定时同步用的是同一份代码，
所以不会出现两份实现各自演化的问题。

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
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
CORE_PATH = REPO_ROOT / "plugins" / "meme_sync" / "naihub.py"


def _load_core() -> Any:
    """按文件路径加载核心模块。

    直接 import plugins.meme_sync 会连带执行插件的 __init__.py，
    而那里需要 NoneBot 环境，所以这里绕过包机制单独加载。
    """
    spec = importlib.util.spec_from_file_location("naihub_core", CORE_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit(f"找不到同步核心模块：{CORE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


naihub = _load_core()


def _printer(level: str, message: str) -> None:
    print(message, flush=True)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(
        description="批量下载奶-hub（nai-hub.com）表情包",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--out", default=str(REPO_ROOT / "data" / "naihub-img"),
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

    if args.list:
        print("读取清单…", flush=True)
        try:
            items = naihub.collect_items(args.char, args.sub, log=_printer)
        except Exception as exc:  # noqa: BLE001
            print(f"读取清单失败：{exc}")
            print("若提示连接被拒绝，请检查网络或代理设置后重试。")
            return 1
        if not items:
            print("没有匹配的图片，请检查 --char / --sub 参数。")
            return 1
        for (char_name, sub_name), rows in naihub.group_items(items).items():
            print(f"\n{char_name} / {sub_name}（{len(rows)} 张）")
            for row in rows:
                print(f"  - {row['title'] or os.path.basename(row['src_path'])}")
        print(f"\n合计 {len(items)} 张")
        return 0

    out_dir = Path(args.out).expanduser()
    print(f"保存到 {out_dir.resolve()}，并发 {args.workers}", flush=True)
    try:
        result = naihub.sync(
            out_dir,
            chars=args.char,
            subs=args.sub,
            workers=args.workers,
            timeout=args.timeout,
            route=args.route,
            flat=args.flat,
            overwrite=args.overwrite,
            log=_printer,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"同步失败：{exc}")
        return 1

    if result["total"] == 0:
        print("没有匹配的图片，请检查 --char / --sub 参数。")
        return 1

    print("\n完成：下载 {ok} 张（{mb:.1f} MB），跳过 {skip} 张，失败 {fail} 张".format(
        ok=result["ok"], mb=result["bytes"] / 1024 / 1024,
        skip=result["skip"], fail=result["fail"]))
    print(f"目录：{Path(result['out_dir']).resolve()}")
    print(f"索引：{result['index_path']}")
    if result["failures"]:
        print("失败清单：")
        for item in result["failures"][:20]:
            print(f"  - {item['title']} ← {item['url']}（{item['error']}）")
    return 1 if result["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
