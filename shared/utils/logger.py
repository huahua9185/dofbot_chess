"""
结构化日志记录工具
"""
import logging
import structlog
from pathlib import Path
from typing import Optional
import os


def setup_logging(
    service_name: str,
    log_level: str = "INFO",
    log_dir: Optional[str] = None
) -> structlog.stdlib.BoundLogger:
    """
    设置结构化日志系统

    Args:
        service_name: 服务名称
        log_level: 日志级别
        log_dir: 日志目录，默认为环境变量LOG_DIR或/var/log/robot-chess

    Returns:
        配置好的结构化日志记录器
    """

    # 获取日志目录
    if log_dir is None:
        log_dir = os.getenv("LOG_DIR", "/var/log/robot-chess")

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # 配置结构化日志处理器
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 配置标准Python日志
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
        handlers=[
            logging.FileHandler(log_path / f"{service_name}.log"),
            logging.StreamHandler()
        ]
    )

    # 创建结构化日志记录器
    logger = structlog.get_logger(service_name)
    logger.info("日志系统初始化完成", service=service_name, level=log_level)

    return logger


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    获取日志记录器

    Args:
        name: 日志记录器名称

    Returns:
        结构化日志记录器
    """
    return structlog.get_logger(name)