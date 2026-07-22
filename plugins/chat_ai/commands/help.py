from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent

help_cmd = on_command("help", aliases={"帮助"}, priority=5, block=True)


@help_cmd.handle()
async def handle_help(event: MessageEvent):
    """显示帮助信息"""
    help_text = """可用命令：
/help 或 /帮助 - 显示此帮助
/reset 或 /重置对话 - 重置当前对话历史
/settings <QQ号> 或 /设置 - 管理用户白名单（管理员）
/groupsettings <群号> 或 /群设置 - 管理群白名单（管理员）
/setkey <一句话> 或 /设置关键词 - 添加提示词（管理员）
/setkey 或 /设置关键词 - 查看所有提示词（管理员）
/setkey del <ID> 或 /设置关键词 del <ID> - 删除提示词（管理员）
/邻家大姐姐人格 - 切换到邻家大姐姐人格
/雌小鬼人格 - 切换回默认人格
/贴表情 <QQ号> - 给指定用户消息贴随机表情（管理员）
/取消贴表情 <QQ号> - 取消给指定用户贴的表情（管理员）
/贴表情all <QQ号> - 给指定用户在所有群贴🐒表情（管理员，支持私聊）
/取消贴表情all <QQ号> - 取消给指定用户在所有群贴🐒表情（管理员，支持私聊）
/全体贴表情 - 给群内所有人消息随机贴表情（管理员）
/取消全体贴表情 - 取消全体贴表情（管理员）
/欢迎语 <内容> - 设置新成员入群欢迎语（管理员）
/欢迎语 - 查看当前群欢迎语（管理员）
/排行榜 或 /ranking - 查看群发言排行榜（管理员）
/weibo <UID> - 获取微博用户最新动态（私聊）
/sendweibo <UID> <群号> - 发送微博图片到指定群（私聊）"""
    await help_cmd.finish(help_text)
