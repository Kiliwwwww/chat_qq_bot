from pydantic import BaseModel


class Config(BaseModel):
    """可视化管理面板配置"""

    admin_panel_enabled: bool = True
    admin_panel_password: str = ""
    admin_panel_session_hours: int = 12
    admin_panel_login_max_attempts: int = 5
    admin_panel_login_window_seconds: int = 60
