"""
共享配置模块
"""

from .database import get_database_url, get_redis_url
from .settings import get_settings, Settings

# 为了兼容性，提供get_config函数
get_config = get_settings

__all__ = ['get_database_url', 'get_redis_url', 'get_settings', 'get_config', 'Settings']