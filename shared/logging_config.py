"""
日志配置模块
"""
import logging
import sys


def setup_logging(level: str = "INFO", service_name: str = "robot_chess"):
    """设置日志配置"""

    # 设置日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 设置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # 添加处理器到根日志器
    root_logger.addHandler(console_handler)

    return root_logger


def get_logger(name: str = None):
    """获取日志器"""
    return logging.getLogger(name)