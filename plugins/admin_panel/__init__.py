import asyncio

from nonebot import get_driver, logger

from .reports import refresh_report_cache
from .routes import router

driver = get_driver()

try:
    app = driver.server_app
except AttributeError:
    logger.warning("当前驱动不是 FastAPI，管理面板未挂载")
else:
    app.include_router(router)
    logger.info("可视化管理面板已挂载: /admin")

    @driver.on_startup
    async def _warm_report_cache() -> None:
        try:
            await asyncio.to_thread(refresh_report_cache, True)
            logger.info("报表缓存预热完成")
        except Exception as exc:
            logger.warning(f"报表缓存预热失败: {exc}")

    try:
        from nonebot_plugin_apscheduler import scheduler

        async def _refresh_report_job() -> None:
            await asyncio.to_thread(refresh_report_cache)

        scheduler.add_job(
            _refresh_report_job,
            "interval",
            minutes=5,
            id="admin_report_refresh",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
    except Exception as exc:
        logger.warning(f"报表缓存定时刷新未启用: {exc}")
