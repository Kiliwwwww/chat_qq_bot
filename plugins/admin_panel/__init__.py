from nonebot import get_driver, logger

from .routes import router

driver = get_driver()

try:
    app = driver.server_app
except AttributeError:
    logger.warning("当前驱动不是 FastAPI，管理面板未挂载")
else:
    app.include_router(router)
    logger.info("可视化管理面板已挂载: /admin")
