"""
共享配置模块
"""

from .database import get_database_url, get_redis_url

__all__ = ['get_database_url', 'get_redis_url']