from nonebot import on_command, get_plugin_config
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot import logger

from .config import Config
from .member_utils import get_random_member, get_user_nickname, download_avatar
from .image_generator import generate_wife_image, generate_baby_image
from .pairing import PairingManager

# 获取配置
config = get_plugin_config(Config)

# 配对管理器
pairing_manager = PairingManager(config)

# 今日老婆命令（群聊和私聊都可用）
daily_wife_cmd = on_command("今日老婆", priority=5, block=True)

# 原神家庭命令（群聊）
daily_baby_cmd = on_command("原神家庭", priority=5, block=True)

# 今日老婆配置命令（仅私聊可用）
daily_wife_set_cmd = on_command("今日老婆配置", priority=5, block=True)


@daily_wife_set_cmd.handle()
async def handle_daily_wife_set(bot: Bot, event: PrivateMessageEvent, args: Message = CommandArg()):
    """处理今日老婆配置命令（仅私聊）
    格式: /今日老婆配置 QQ号 配对QQ号
    例如: /今日老婆配置 1154798056 603590221
    """
    # 解析参数
    arg_text = args.extract_plain_text().strip()
    parts = arg_text.split()
    
    if len(parts) != 2:
        await daily_wife_set_cmd.finish("格式错误！正确格式: /今日老婆配置 QQ号 配对QQ号")
    
    try:
        user_id = int(parts[0])
        wife_id = int(parts[1])
    except ValueError:
        await daily_wife_set_cmd.finish("QQ号必须是数字")
    
    # 设置全局配对
    if pairing_manager.set_pairing(user_id, wife_id):
        await daily_wife_set_cmd.finish(f"配置成功！{user_id} 的今日老婆固定为 {wife_id}（所有群生效）")
    else:
        await daily_wife_set_cmd.finish("配置失败，Redis连接异常")


@daily_wife_cmd.handle()
async def handle_daily_wife(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """处理今日老婆命令（群聊）"""
    group_id = event.group_id
    sender_id = event.user_id
    
    # 检查今日是否已经抽过
    cached_wife_id = pairing_manager.get_daily_result(sender_id)
    if cached_wife_id:
        wife_name = await get_user_nickname(bot, group_id, cached_wife_id)
        sender_name = await get_user_nickname(bot, group_id, sender_id)
        
        sender_avatar = await download_avatar(sender_id)
        wife_avatar = await download_avatar(cached_wife_id)
        
        if sender_avatar and wife_avatar:
            image_data = generate_wife_image(
                sender_avatar=sender_avatar,
                wife_avatar=wife_avatar,
                sender_name=sender_name,
                wife_name=wife_name,
                width=config.image_width,
                height=config.image_height,
                avatar_size=config.avatar_size,
            )
            await daily_wife_cmd.finish(MessageSegment.image(image_data))
        else:
            await daily_wife_cmd.finish("获取头像失败，请稍后再试~")
    
    # 检查是否有预设配对
    wife_id = pairing_manager.get_pairing(sender_id)
    wife_member = None
    
    if wife_id:
        try:
            wife_member = await bot.get_group_member_info(group_id=group_id, user_id=wife_id)
        except Exception:
            wife_member = None
    
    # 没有预设配对或预设配对不在群里，随机选择
    if wife_member is None:
        exclude_id = sender_id if not config.allow_self else None
        wife_member = await get_random_member(bot, group_id, exclude_user_id=exclude_id)
    
    if wife_member is None:
        await daily_wife_cmd.finish("群里没有其他可选的群友啦~")
    
    wife_id = wife_member["user_id"]
    sender_name = await get_user_nickname(bot, group_id, sender_id)
    wife_name = await get_user_nickname(bot, group_id, wife_id)
    
    # 保存今日结果
    pairing_manager.set_daily_result(sender_id, wife_id)
    
    # 下载头像
    logger.info(f"开始下载头像: sender_id={sender_id}, wife_id={wife_id}")
    sender_avatar = await download_avatar(sender_id)
    wife_avatar = await download_avatar(wife_id)
    
    if sender_avatar is None or wife_avatar is None:
        logger.error(f"头像下载失败: sender_avatar={sender_avatar is not None}, wife_avatar={wife_avatar is not None}")
        await daily_wife_cmd.finish("获取头像失败，请稍后再试~")
    
    # 生成图片
    try:
        image_data = generate_wife_image(
            sender_avatar=sender_avatar,
            wife_avatar=wife_avatar,
            sender_name=sender_name,
            wife_name=wife_name,
            width=config.image_width,
            height=config.image_height,
            avatar_size=config.avatar_size,
        )
    except Exception as e:
        logger.error(f"生成今日老婆图片失败: {e}")
        await daily_wife_cmd.finish("生成图片失败，请稍后再试~")
    
    # 发送图片
    await daily_wife_cmd.finish(MessageSegment.image(image_data))


@daily_baby_cmd.handle()
async def handle_daily_baby(bot: Bot, event: GroupMessageEvent):
    """处理原神家庭命令（群聊）
    前提：必须已经抽取了今日老婆
    一个家庭一天最多三个孩子
    """
    group_id = event.group_id
    sender_id = event.user_id
    
    # 检查是否有今日老婆
    wife_id = pairing_manager.get_daily_result(sender_id)
    if not wife_id:
        await daily_baby_cmd.finish("你还没有今日老婆哦，先发送「今日老婆」抽取一个吧~")
    
    # 获取昵称
    sender_name = await get_user_nickname(bot, group_id, sender_id)
    wife_name = await get_user_nickname(bot, group_id, wife_id)
    
    # 获取已有的孩子列表
    children_ids = pairing_manager.get_daily_children(sender_id, group_id)
    
    # 如果已经有3个孩子，直接返回结果
    if len(children_ids) >= 3:
        children_names = []
        for child_id in children_ids:
            child_name = await get_user_nickname(bot, group_id, child_id)
            children_names.append(child_name)
        
        # 下载所有头像
        logger.info(f"已有3个孩子，直接返回结果: sender_id={sender_id}, wife_id={wife_id}, children={children_ids}")
        sender_avatar = await download_avatar(sender_id)
        wife_avatar = await download_avatar(wife_id)
        children_avatars = []
        for child_id in children_ids:
            child_avatar = await download_avatar(child_id)
            children_avatars.append(child_avatar)
        
        if not all([sender_avatar, wife_avatar] + children_avatars):
            logger.error("头像下载失败")
            await daily_baby_cmd.finish("获取头像失败，请稍后再试~")
        
        # 生成图片
        try:
            image_data = generate_baby_image(
                sender_avatar=sender_avatar,
                wife_avatar=wife_avatar,
                baby_avatars=children_avatars,
                sender_name=sender_name,
                wife_name=wife_name,
                baby_names=children_names,
                width=config.image_width,
                height=config.image_height,
                avatar_size=config.avatar_size,
            )
        except Exception as e:
            logger.error(f"生成原神家庭图片失败: {e}")
            await daily_baby_cmd.finish("生成图片失败，请稍后再试~")
        
        await daily_baby_cmd.finish(MessageSegment.image(image_data))
    
    # 随机抽取一个群友作为小孩（排除自己、老婆和已有的孩子）
    members = await bot.get_group_member_list(group_id=group_id)
    exclude_ids = {sender_id, wife_id} | set(children_ids)
    available_members = [m for m in members if m["user_id"] not in exclude_ids]
    
    if not available_members:
        await daily_baby_cmd.finish("群里没有其他可选的群友当家庭成员啦~")
    
    import random
    baby_member = random.choice(available_members)
    baby_id = baby_member["user_id"]
    
    # 存入数据库
    pairing_manager.add_daily_child(sender_id, group_id, baby_id)
    
    # 更新孩子列表
    children_ids = pairing_manager.get_daily_children(sender_id, group_id)
    children_names = []
    for child_id in children_ids:
        child_name = await get_user_nickname(bot, group_id, child_id)
        children_names.append(child_name)
    
    # 下载所有头像
    logger.info(f"开始下载头像: sender_id={sender_id}, wife_id={wife_id}, children={children_ids}")
    sender_avatar = await download_avatar(sender_id)
    wife_avatar = await download_avatar(wife_id)
    children_avatars = []
    for child_id in children_ids:
        child_avatar = await download_avatar(child_id)
        children_avatars.append(child_avatar)
    
    if not all([sender_avatar, wife_avatar] + children_avatars):
        logger.error("头像下载失败")
        await daily_baby_cmd.finish("获取头像失败，请稍后再试~")
    
    # 生成图片
    try:
        image_data = generate_baby_image(
            sender_avatar=sender_avatar,
            wife_avatar=wife_avatar,
            baby_avatars=children_avatars,
            sender_name=sender_name,
            wife_name=wife_name,
            baby_names=children_names,
            width=config.image_width,
            height=config.image_height,
            avatar_size=config.avatar_size,
        )
    except Exception as e:
        logger.error(f"生成原神家庭图片失败: {e}")
        await daily_baby_cmd.finish("生成图片失败，请稍后再试~")
    
    # 发送图片
    await daily_baby_cmd.finish(MessageSegment.image(image_data))
