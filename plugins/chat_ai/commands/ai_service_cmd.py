from nonebot import on_command, get_plugin_config
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message

from ..config import Config
from ..state import db, init_ai_service

config = get_plugin_config(Config)

# 添加 AI 服务命令
add_ai_service_cmd = on_command("添加ai服务", aliases={"addaiservice"}, priority=5, block=True)

# 查看 AI 服务列表命令
ai_service_list_cmd = on_command("ai服务", aliases={"aiservice", "aiservices"}, priority=5, block=True)

# 切换 AI 服务命令
switch_ai_service_cmd = on_command("切换ai服务", aliases={"switchaiservice"}, priority=5, block=True)

# 删除 AI 服务命令
delete_ai_service_cmd = on_command("删除ai服务", aliases={"deleteaiservice"}, priority=5, block=True)


def _is_admin(user_id: int) -> bool:
    """检查是否为管理员"""
    return user_id == config.admin_qq


@add_ai_service_cmd.handle()
async def handle_add_ai_service(event: MessageEvent, args: Message = CommandArg()):
    """添加 AI 服务"""
    if not _is_admin(event.user_id):
        await add_ai_service_cmd.finish("只有管理员才能添加 AI 服务")
    
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await add_ai_service_cmd.finish(
            "格式: /添加ai服务 <名称> <api_key> <base_url> <model>\n"
            "示例: /添加ai服务 小米AI tp-xxx https://api.xiaomimimo.com/v1 mimo-v2.5"
        )
    
    parts = arg_text.split()
    if len(parts) < 4:
        await add_ai_service_cmd.finish(
            "参数不完整，格式: /添加ai服务 <名称> <api_key> <base_url> <model>"
        )
    
    name = parts[0]
    api_key = parts[1]
    base_url = parts[2]
    model = parts[3]
    
    if db.add_ai_service(name, api_key, base_url, model):
        await add_ai_service_cmd.finish(f"AI 服务 '{name}' 添加成功！\n使用 /切换ai服务 <id> 来切换到此服务")
    else:
        await add_ai_service_cmd.finish("添加失败，请检查日志")


@ai_service_list_cmd.handle()
async def handle_ai_service_list(event: MessageEvent):
    """查看 AI 服务列表"""
    services = db.get_all_ai_services()
    
    if not services:
        await ai_service_list_cmd.finish("暂无 AI 服务配置\n使用 /添加ai服务 来添加")
    
    msg = "AI 服务列表：\n"
    msg += "━━━━━━━━━━━━━━\n"
    for svc in services:
        status = "✅ 使用中" if svc["is_active"] else ""
        msg += f"ID: {svc['id']}\n"
        msg += f"名称: {svc['name']}\n"
        msg += f"模型: {svc['model']}\n"
        msg += f"地址: {svc['base_url']}\n"
        if status:
            msg += f"状态: {status}\n"
        msg += "━━━━━━━━━━━━━━\n"
    
    msg += "\n使用 /切换ai服务 <id> 切换服务"
    await ai_service_list_cmd.finish(msg)


@switch_ai_service_cmd.handle()
async def handle_switch_ai_service(event: MessageEvent, args: Message = CommandArg()):
    """切换 AI 服务"""
    if not _is_admin(event.user_id):
        await switch_ai_service_cmd.finish("只有管理员才能切换 AI 服务")
    
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await switch_ai_service_cmd.finish("格式: /切换ai服务 <id>\n使用 /ai服务 查看可用的服务列表")
    
    try:
        service_id = int(arg_text)
    except ValueError:
        await switch_ai_service_cmd.finish("ID 必须是数字")
    
    if not db.ai_service_exists(service_id):
        await switch_ai_service_cmd.finish(f"ID 为 {service_id} 的 AI 服务不存在")
    
    if db.set_active_ai_service(service_id):
        # 重新初始化 AI 服务
        init_ai_service()
        service = db.get_active_ai_service()
        await switch_ai_service_cmd.finish(
            f"已切换到 AI 服务: {service['name']}\n"
            f"模型: {service['model']}\n"
            f"地址: {service['base_url']}"
        )
    else:
        await switch_ai_service_cmd.finish("切换失败，请检查日志")


@delete_ai_service_cmd.handle()
async def handle_delete_ai_service(event: MessageEvent, args: Message = CommandArg()):
    """删除 AI 服务"""
    if not _is_admin(event.user_id):
        await delete_ai_service_cmd.finish("只有管理员才能删除 AI 服务")
    
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await delete_ai_service_cmd.finish("格式: /删除ai服务 <id>\n使用 /ai服务 查看可用的服务列表")
    
    try:
        service_id = int(arg_text)
    except ValueError:
        await delete_ai_service_cmd.finish("ID 必须是数字")
    
    if not db.ai_service_exists(service_id):
        await delete_ai_service_cmd.finish(f"ID 为 {service_id} 的 AI 服务不存在")
    
    # 检查是否为当前激活的服务
    active_service = db.get_active_ai_service()
    if active_service and active_service["id"] == service_id:
        await delete_ai_service_cmd.finish("不能删除当前正在使用的服务，请先切换到其他服务")
    
    if db.remove_ai_service(service_id):
        await delete_ai_service_cmd.finish(f"AI 服务 (ID: {service_id}) 已删除")
    else:
        await delete_ai_service_cmd.finish("删除失败，请检查日志")
