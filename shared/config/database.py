"""
数据库配置模块
提供数据库连接字符串和配置管理
"""

import os
from typing import Optional


def get_database_url(database_name: str = "chess_robot") -> str:
    """
    获取数据库连接URL

    Args:
        database_name: 数据库名称

    Returns:
        MongoDB连接字符串
    """
    # 从环境变量获取配置
    host = os.getenv('MONGODB_HOST', 'localhost')
    port = int(os.getenv('MONGODB_PORT', '27017'))
    username = os.getenv('MONGODB_USERNAME')
    password = os.getenv('MONGODB_PASSWORD')

    # 构建连接字符串
    if username and password:
        return f"mongodb://{username}:{password}@{host}:{port}/{database_name}"
    else:
        return f"mongodb://{host}:{port}/{database_name}"


def get_redis_url() -> str:
    """
    获取Redis连接URL

    Returns:
        Redis连接字符串
    """
    host = os.getenv('REDIS_HOST', 'localhost')
    port = int(os.getenv('REDIS_PORT', '6379'))
    password = os.getenv('REDIS_PASSWORD')
    db = int(os.getenv('REDIS_DB', '0'))

    if password:
        return f"redis://:{password}@{host}:{port}/{db}"
    else:
        return f"redis://{host}:{port}/{db}"