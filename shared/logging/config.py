"""
共享日志配置模块
提供结构化日志记录的统一配置和工具
"""

import os
import sys
import json
import logging
import logging.config
from typing import Dict, Any, Optional
from datetime import datetime
from pythonjsonlogger import jsonlogger


class ChessRobotFormatter(jsonlogger.JsonFormatter):
    """
    象棋机器人专用JSON格式化器
    添加系统特定字段和格式化规则
    """

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        super().add_fields(log_record, record, message_dict)

        # 添加时间戳
        log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'

        # 添加服务标识
        log_record['service'] = os.getenv('SERVICE_NAME', 'unknown')
        log_record['version'] = os.getenv('SERVICE_VERSION', '1.0.0')

        # 添加主机信息
        log_record['hostname'] = os.getenv('HOSTNAME', 'jetson-chess-robot')

        # 添加日志级别
        log_record['level'] = record.levelname

        # 添加模块信息
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno

        # 添加进程和线程ID
        log_record['process_id'] = os.getpid()
        log_record['thread_id'] = record.thread
        log_record['thread_name'] = record.threadName

        # 如果有异常信息，格式化它
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)


def get_logging_config(
    service_name: str,
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    enable_console: bool = True,
    enable_file: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> Dict[str, Any]:
    """
    获取日志配置字典

    Args:
        service_name: 服务名称
        log_level: 日志级别
        log_file: 日志文件路径
        enable_console: 是否启用控制台输出
        enable_file: 是否启用文件输出
        max_bytes: 日志文件最大大小
        backup_count: 保留的备份文件数量

    Returns:
        logging配置字典
    """

    # 设置环境变量
    os.environ['SERVICE_NAME'] = service_name

    # 默认日志文件路径
    if log_file is None:
        log_dir = "/home/jetson/prog/logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = f"{log_dir}/{service_name}.log"

    # 格式化器配置
    formatters = {
        'json': {
            '()': ChessRobotFormatter,
            'format': '%(timestamp)s %(level)s %(name)s %(message)s'
        },
        'console': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    }

    # 处理器配置
    handlers = {}

    if enable_console:
        handlers['console'] = {
            'class': 'logging.StreamHandler',
            'level': log_level,
            'formatter': 'console',
            'stream': 'ext://sys.stdout'
        }

    if enable_file:
        handlers['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': log_level,
            'formatter': 'json',
            'filename': log_file,
            'maxBytes': max_bytes,
            'backupCount': backup_count,
            'encoding': 'utf8'
        }

    # 根记录器配置
    root_handlers = []
    if enable_console:
        root_handlers.append('console')
    if enable_file:
        root_handlers.append('file')

    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': formatters,
        'handlers': handlers,
        'root': {
            'level': log_level,
            'handlers': root_handlers
        },
        'loggers': {
            # 设置特定模块的日志级别
            'urllib3': {
                'level': 'WARNING',
                'propagate': True
            },
            'requests': {
                'level': 'WARNING',
                'propagate': True
            },
            'redis': {
                'level': 'INFO',
                'propagate': True
            },
            'fastapi': {
                'level': 'INFO',
                'propagate': True
            },
            'uvicorn': {
                'level': 'INFO',
                'propagate': True
            }
        }
    }

    return config


def setup_logging(
    service_name: str,
    log_level: str = None,
    log_file: str = None,
    config_file: str = None
) -> logging.Logger:
    """
    设置日志记录

    Args:
        service_name: 服务名称
        log_level: 日志级别，默认从环境变量获取
        log_file: 日志文件路径
        config_file: 外部配置文件路径

    Returns:
        配置好的logger实例
    """

    # 从环境变量获取配置
    if log_level is None:
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()

    # 如果指定了配置文件，加载外部配置
    if config_file and os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        # 使用默认配置
        config = get_logging_config(
            service_name=service_name,
            log_level=log_level,
            log_file=log_file
        )

    # 应用配置
    logging.config.dictConfig(config)

    # 返回主logger
    logger = logging.getLogger(service_name)
    logger.info(
        f"Logging initialized for {service_name}",
        extra={
            'event': 'logging_initialized',
            'service': service_name,
            'log_level': log_level,
            'log_file': log_file or f"logs/{service_name}.log"
        }
    )

    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    获取logger实例

    Args:
        name: logger名称，默认使用调用模块名

    Returns:
        logger实例
    """
    if name is None:
        # 获取调用者的模块名
        frame = sys._getframe(1)
        name = frame.f_globals.get('__name__', 'unknown')

    return logging.getLogger(name)