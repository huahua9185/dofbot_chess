"""
共享日志记录包
提供结构化日志记录功能
"""

from .config import setup_logging, get_logger, ChessRobotFormatter
from .decorators import log_function_call, log_async_function_call
from .context import LogContext
from .metrics import LogMetricsCollector

__all__ = [
    'setup_logging',
    'get_logger',
    'ChessRobotFormatter',
    'log_function_call',
    'log_async_function_call',
    'LogContext',
    'LogMetricsCollector'
]