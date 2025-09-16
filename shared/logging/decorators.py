"""
日志装饰器模块
提供函数调用日志记录装饰器
"""

import time
import functools
import asyncio
from typing import Callable, Any, Dict, Optional
from .config import get_logger


def log_function_call(
    logger_name: str = None,
    log_args: bool = True,
    log_result: bool = True,
    log_duration: bool = True,
    log_exceptions: bool = True,
    level: str = "INFO"
) -> Callable:
    """
    记录函数调用的装饰器

    Args:
        logger_name: logger名称
        log_args: 是否记录参数
        log_result: 是否记录返回值
        log_duration: 是否记录执行时间
        log_exceptions: 是否记录异常
        level: 日志级别
    """

    def decorator(func: Callable) -> Callable:
        logger = get_logger(logger_name or func.__module__)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            func_name = f"{func.__module__}.{func.__name__}"

            # 准备日志上下文
            log_context = {
                'event': 'function_call',
                'function': func_name,
                'function_name': func.__name__,
                'module': func.__module__
            }

            # 记录参数
            if log_args:
                # 过滤敏感参数
                filtered_args = _filter_sensitive_data(args)
                filtered_kwargs = _filter_sensitive_data(kwargs)
                log_context.update({
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys()) if kwargs else [],
                    'args': filtered_args if len(str(filtered_args)) < 1000 else "<truncated>",
                    'kwargs': filtered_kwargs if len(str(filtered_kwargs)) < 1000 else "<truncated>"
                })

            try:
                # 调用函数
                result = func(*args, **kwargs)

                # 计算执行时间
                if log_duration:
                    duration = time.time() - start_time
                    log_context['duration_seconds'] = round(duration, 4)

                # 记录返回值
                if log_result and result is not None:
                    filtered_result = _filter_sensitive_data(result)
                    log_context['result'] = filtered_result if len(str(filtered_result)) < 1000 else "<truncated>"

                log_context['status'] = 'success'

                # 记录成功日志
                getattr(logger, level.lower())(
                    f"Function {func_name} completed successfully",
                    extra=log_context
                )

                return result

            except Exception as e:
                # 计算执行时间
                if log_duration:
                    duration = time.time() - start_time
                    log_context['duration_seconds'] = round(duration, 4)

                log_context.update({
                    'status': 'error',
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                })

                # 记录异常日志
                if log_exceptions:
                    logger.error(
                        f"Function {func_name} failed with exception",
                        extra=log_context,
                        exc_info=True
                    )

                raise

        return wrapper
    return decorator


def log_async_function_call(
    logger_name: str = None,
    log_args: bool = True,
    log_result: bool = True,
    log_duration: bool = True,
    log_exceptions: bool = True,
    level: str = "INFO"
) -> Callable:
    """
    记录异步函数调用的装饰器

    Args:
        logger_name: logger名称
        log_args: 是否记录参数
        log_result: 是否记录返回值
        log_duration: 是否记录执行时间
        log_exceptions: 是否记录异常
        level: 日志级别
    """

    def decorator(func: Callable) -> Callable:
        logger = get_logger(logger_name or func.__module__)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            func_name = f"{func.__module__}.{func.__name__}"

            # 准备日志上下文
            log_context = {
                'event': 'async_function_call',
                'function': func_name,
                'function_name': func.__name__,
                'module': func.__module__
            }

            # 记录参数
            if log_args:
                filtered_args = _filter_sensitive_data(args)
                filtered_kwargs = _filter_sensitive_data(kwargs)
                log_context.update({
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys()) if kwargs else [],
                    'args': filtered_args if len(str(filtered_args)) < 1000 else "<truncated>",
                    'kwargs': filtered_kwargs if len(str(filtered_kwargs)) < 1000 else "<truncated>"
                })

            try:
                # 调用异步函数
                result = await func(*args, **kwargs)

                # 计算执行时间
                if log_duration:
                    duration = time.time() - start_time
                    log_context['duration_seconds'] = round(duration, 4)

                # 记录返回值
                if log_result and result is not None:
                    filtered_result = _filter_sensitive_data(result)
                    log_context['result'] = filtered_result if len(str(filtered_result)) < 1000 else "<truncated>"

                log_context['status'] = 'success'

                # 记录成功日志
                getattr(logger, level.lower())(
                    f"Async function {func_name} completed successfully",
                    extra=log_context
                )

                return result

            except Exception as e:
                # 计算执行时间
                if log_duration:
                    duration = time.time() - start_time
                    log_context['duration_seconds'] = round(duration, 4)

                log_context.update({
                    'status': 'error',
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                })

                # 记录异常日志
                if log_exceptions:
                    logger.error(
                        f"Async function {func_name} failed with exception",
                        extra=log_context,
                        exc_info=True
                    )

                raise

        return wrapper
    return decorator


def _filter_sensitive_data(data: Any) -> Any:
    """
    过滤敏感数据

    Args:
        data: 要过滤的数据

    Returns:
        过滤后的数据
    """
    if isinstance(data, dict):
        filtered = {}
        for key, value in data.items():
            # 检查敏感字段
            if any(sensitive in key.lower() for sensitive in ['password', 'token', 'key', 'secret', 'credential']):
                filtered[key] = "***HIDDEN***"
            else:
                filtered[key] = _filter_sensitive_data(value)
        return filtered
    elif isinstance(data, (list, tuple)):
        return type(data)(_filter_sensitive_data(item) for item in data)
    else:
        return data