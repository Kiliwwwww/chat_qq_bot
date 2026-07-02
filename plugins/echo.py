from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg
from nonebot.adapters import Message

echo = on_command("echo", aliases={"复读"}, priority=5, block=True)


@echo.handle()
async def handle_echo(event: MessageEvent, args: Message = CommandArg()):
    await echo.finish(args)