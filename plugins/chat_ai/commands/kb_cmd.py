from datetime import datetime
from pathlib import Path

from nonebot import on_command, get_plugin_config, logger
from nonebot.adapters.onebot.v11 import MessageEvent, PrivateMessageEvent
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message

from ..config import Config
from .. import state
from ..state import db, CHAT_LOG_DIR, init_ai_service
from ..summarizer import generate_summary

kb_add_cmd = on_command("kb_add", priority=5, block=True)
kb_del_cmd = on_command("kb_del", priority=5, block=True)
kb_list_cmd = on_command("kb_list", priority=5, block=True)
kb_upload_cmd = on_command("kb_upload", priority=5, block=True)
kb_summary_cmd = on_command("kb_summary", priority=5, block=True)
kb_sync_cmd = on_command("kb_sync", priority=5, block=True)


def _get_chat_log_path(group_id: int, date_str: str = None) -> Path:
    """获取聊天记录文件路径"""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    return CHAT_LOG_DIR / f"{group_id}_{date_str}.txt"


@kb_add_cmd.handle()
async def handle_kb_add(event: MessageEvent, args: Message = CommandArg()):
    """添加群知识库配置：/kb_add <群号> <知识库ID>"""
    if not isinstance(event, PrivateMessageEvent):
        await kb_add_cmd.finish("请在私聊中使用此命令")

    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await kb_add_cmd.finish("只有管理员可以使用此命令")

    arg_text = args.extract_plain_text().strip()
    parts = arg_text.split()
    if len(parts) < 2:
        await kb_add_cmd.finish("用法：/kb_add <群号> <知识库ID>\n例如：/kb_add 123456 8b31cb78863511f1a31795a9f4a03d97")

    try:
        group_id = int(parts[0])
    except ValueError:
        await kb_add_cmd.finish("群号必须是数字")

    kb_id = parts[1]

    if db.add_kb_group(group_id, kb_id):
        state.kb_groups[group_id] = kb_id
        await kb_add_cmd.finish(f"已添加群 {group_id} 的知识库配置，知识库ID：{kb_id}")
    else:
        await kb_add_cmd.finish("添加失败，请检查日志")


@kb_del_cmd.handle()
async def handle_kb_del(event: MessageEvent, args: Message = CommandArg()):
    """删除群知识库配置：/kb_del <群号>"""
    if not isinstance(event, PrivateMessageEvent):
        await kb_del_cmd.finish("请在私聊中使用此命令")

    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await kb_del_cmd.finish("只有管理员可以使用此命令")

    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await kb_del_cmd.finish("用法：/kb_del <群号>")

    try:
        group_id = int(arg_text)
    except ValueError:
        await kb_del_cmd.finish("群号必须是数字")

    if db.remove_kb_group(group_id):
        state.kb_groups.pop(group_id, None)
        await kb_del_cmd.finish(f"已删除群 {group_id} 的知识库配置")
    else:
        await kb_del_cmd.finish("删除失败，请检查日志")


@kb_list_cmd.handle()
async def handle_kb_list(event: MessageEvent):
    """查看群知识库配置列表：/kb_list"""
    if not isinstance(event, PrivateMessageEvent):
        await kb_list_cmd.finish("请在私聊中使用此命令")

    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await kb_list_cmd.finish("只有管理员可以使用此命令")

    kb_groups = db.get_all_kb_groups()
    if not kb_groups:
        await kb_list_cmd.finish("当前没有配置任何群知识库")

    lines = ["群知识库配置列表："]
    for gid, kid in kb_groups.items():
        lines.append(f"群 {gid} -> 知识库 {kid}")

    await kb_list_cmd.finish("\n".join(lines))


def _mark_as_uploaded(file_path: Path) -> None:
    """标记文件为已上传（重命名添加 _uploaded 后缀）"""
    uploaded_path = file_path.with_name(file_path.stem + "_uploaded" + file_path.suffix)
    try:
        file_path.rename(uploaded_path)
    except Exception as e:
        logger.error(f"标记文件已上传失败: {e}")


def _get_unuploaded_path(group_id: int, date_str: str = None) -> Path | None:
    """获取未上传的聊天记录文件路径，不存在则返回 None"""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    log_path = CHAT_LOG_DIR / f"{group_id}_{date_str}.txt"
    if log_path.exists():
        return log_path
    return None


@kb_upload_cmd.handle()
async def handle_kb_upload(event: MessageEvent, args: Message = CommandArg()):
    """手动上传聊天记录到知识库：/kb_upload [群号] [日期]
    不带参数则上传所有群今天的聊天记录"""
    if not isinstance(event, PrivateMessageEvent):
        await kb_upload_cmd.finish("请在私聊中使用此命令")

    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await kb_upload_cmd.finish("只有管理员可以使用此命令")

    if not state.ai_service:
        init_ai_service()

    if not state.ragflow_client:
        await kb_upload_cmd.finish("RAGFlow 客户端未初始化，请检查配置")

    arg_text = args.extract_plain_text().strip()
    parts = arg_text.split() if arg_text else []

    target_group_id = None
    target_date = None

    if len(parts) >= 1:
        try:
            target_group_id = int(parts[0])
        except ValueError:
            if parts[0] != "all":
                await kb_upload_cmd.finish("群号必须是数字")
    if len(parts) >= 2:
        target_date = parts[1]

    kb_groups = db.get_all_kb_groups()
    if not kb_groups:
        await kb_upload_cmd.finish("当前没有配置任何群知识库")

    if target_group_id:
        if target_group_id not in kb_groups:
            await kb_upload_cmd.finish(f"群 {target_group_id} 未配置知识库")
        groups_to_upload = {target_group_id: kb_groups[target_group_id]}
    else:
        groups_to_upload = kb_groups

    date_str = target_date or datetime.now().strftime("%Y-%m-%d")
    results = []

    for gid, kid in groups_to_upload.items():
        log_path = _get_unuploaded_path(gid, date_str)
        if not log_path:
            results.append(f"群 {gid}: 无待上传的 {date_str} 聊天记录")
            continue

        if log_path.stat().st_size == 0:
            results.append(f"群 {gid}: {date_str} 聊天记录为空，跳过")
            continue

        success = await state.ragflow_client.upload_and_parse(kid, log_path)
        if success:
            _mark_as_uploaded(log_path)
            results.append(f"群 {gid}: 上传成功 -> 知识库 {kid}")
        else:
            results.append(f"群 {gid}: 上传失败")

    await kb_upload_cmd.finish("\n".join(results))


def _find_summary_source(group_id: int, date_str: str) -> Path | None:
    """查找可用于生成总结的聊天记录文件（原始或已上传）"""
    raw_path = CHAT_LOG_DIR / f"{group_id}_{date_str}.txt"
    if raw_path.exists():
        return raw_path
    uploaded_path = CHAT_LOG_DIR / f"{group_id}_{date_str}_uploaded.txt"
    if uploaded_path.exists():
        return uploaded_path
    for p in CHAT_LOG_DIR.glob(f"{group_id}_{date_str}*.txt"):
        if "_summary" in p.stem:
            continue
        return p
    return None


def _find_existing_summary(group_id: int, date_str: str) -> Path | None:
    """查找已生成的总结文件（已上传或未上传）"""
    for p in CHAT_LOG_DIR.glob(f"{group_id}_{date_str}_summary*.txt"):
        return p
    return None


@kb_summary_cmd.handle()
async def handle_kb_summary(event: MessageEvent, args: Message = CommandArg()):
    """手动生成聊天记录总结并上传知识库：/kb_summary [群号] [日期]
    不带参数则处理所有群当天的聊天记录"""
    if not isinstance(event, PrivateMessageEvent):
        await kb_summary_cmd.finish("请在私聊中使用此命令")

    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await kb_summary_cmd.finish("只有管理员可以使用此命令")

    if not state.ai_service:
        init_ai_service()

    if not state.ragflow_client:
        await kb_summary_cmd.finish("RAGFlow 客户端未初始化，请检查配置")

    arg_text = args.extract_plain_text().strip()
    parts = arg_text.split() if arg_text else []

    target_group_id = None
    target_date = None

    if len(parts) >= 1:
        try:
            target_group_id = int(parts[0])
        except ValueError:
            if parts[0] != "all":
                await kb_summary_cmd.finish("群号必须是数字")
    if len(parts) >= 2:
        target_date = parts[1]

    kb_groups = db.get_all_kb_groups()
    if not kb_groups:
        await kb_summary_cmd.finish("当前没有配置任何群知识库")

    if target_group_id:
        if target_group_id not in kb_groups:
            await kb_summary_cmd.finish(f"群 {target_group_id} 未配置知识库")
        groups_to_upload = {target_group_id: kb_groups[target_group_id]}
    else:
        groups_to_upload = kb_groups

    date_str = target_date or datetime.now().strftime("%Y-%m-%d")
    results = []

    for gid, kid in groups_to_upload.items():
        source_path = _find_summary_source(gid, date_str)
        if not source_path:
            results.append(f"群 {gid}: 无 {date_str} 聊天记录文件")
            continue

        if _find_existing_summary(gid, date_str):
            results.append(f"群 {gid}: {date_str} 总结已存在，跳过")
            continue

        try:
            summary_path = await generate_summary(gid, date_str, source_path)
        except Exception as e:
            logger.error(f"群 {gid} 生成聊天总结失败: {e}")
            results.append(f"群 {gid}: 总结生成失败: {e}")
            continue

        if not summary_path:
            results.append(f"群 {gid}: 总结生成失败")
            continue

        success = await state.ragflow_client.upload_and_parse(kid, summary_path)
        if success:
            _mark_as_uploaded(summary_path)
            results.append(f"群 {gid}: 总结上传成功 -> 知识库 {kid}")
        else:
            results.append(f"群 {gid}: 总结上传失败")

    await kb_summary_cmd.finish("\n".join(results))


@kb_sync_cmd.handle()
async def handle_kb_sync(event: MessageEvent, args: Message = CommandArg()):
    """同步上传聊天记录并生成总结：/kb_sync [群号] [日期]
    同时完成原始记录上传和总结生成上传，日期默认今天"""
    if not isinstance(event, PrivateMessageEvent):
        await kb_sync_cmd.finish("请在私聊中使用此命令")

    config = get_plugin_config(Config)
    if event.user_id != config.admin_qq:
        await kb_sync_cmd.finish("只有管理员可以使用此命令")

    if not state.ai_service:
        init_ai_service()

    if not state.ragflow_client:
        await kb_sync_cmd.finish("RAGFlow 客户端未初始化，请检查配置")

    arg_text = args.extract_plain_text().strip()
    parts = arg_text.split() if arg_text else []

    target_group_id = None
    target_date = None

    if len(parts) >= 1:
        try:
            target_group_id = int(parts[0])
        except ValueError:
            if parts[0] != "all":
                await kb_sync_cmd.finish("群号必须是数字")
    if len(parts) >= 2:
        target_date = parts[1]

    kb_groups = db.get_all_kb_groups()
    if not kb_groups:
        await kb_sync_cmd.finish("当前没有配置任何群知识库")

    if target_group_id:
        if target_group_id not in kb_groups:
            await kb_sync_cmd.finish(f"群 {target_group_id} 未配置知识库")
        groups_to_sync = {target_group_id: kb_groups[target_group_id]}
    else:
        groups_to_sync = kb_groups

    date_str = target_date or datetime.now().strftime("%Y-%m-%d")
    results = []

    for gid, kid in groups_to_sync.items():
        # 1. 上传原始聊天记录（未上传的）
        log_path = _get_unuploaded_path(gid, date_str)
        if log_path and log_path.stat().st_size > 0:
            raw_ok = await state.ragflow_client.upload_and_parse(kid, log_path)
            if raw_ok:
                _mark_as_uploaded(log_path)
                results.append(f"群 {gid}: 原始记录上传成功 -> 知识库 {kid}")
            else:
                results.append(f"群 {gid}: 原始记录上传失败")
        elif not log_path:
            results.append(f"群 {gid}: 无 {date_str} 聊天记录文件")
        else:
            results.append(f"群 {gid}: {date_str} 聊天记录为空，跳过")

        # 2. 生成并上传总结（已存在的跳过）
        source_path = _find_summary_source(gid, date_str)
        if not source_path:
            continue

        if _find_existing_summary(gid, date_str):
            results.append(f"群 {gid}: {date_str} 总结已存在，跳过")
            continue

        try:
            summary_path = await generate_summary(gid, date_str, source_path)
        except Exception as e:
            logger.error(f"群 {gid} 生成聊天总结失败: {e}")
            results.append(f"群 {gid}: 总结生成失败: {e}")
            continue

        if not summary_path:
            results.append(f"群 {gid}: 总结生成失败")
            continue

        summary_ok = await state.ragflow_client.upload_and_parse(kid, summary_path)
        if summary_ok:
            _mark_as_uploaded(summary_path)
            results.append(f"群 {gid}: 总结上传成功 -> 知识库 {kid}")
        else:
            results.append(f"群 {gid}: 总结上传失败")

    await kb_sync_cmd.finish("\n".join(results))
