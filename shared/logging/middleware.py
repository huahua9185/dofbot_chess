"""
日志中间件模块
为各种框架提供日志集成中间件
"""

import time
import uuid
from typing import Callable, Any
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from .config import get_logger
from .context import LogContext
from .metrics import log_metrics_collector


class FastAPILoggingMiddleware(BaseHTTPMiddleware):
    """
    FastAPI日志中间件
    自动记录HTTP请求和响应信息
    """

    def __init__(self, app, logger_name: str = "fastapi_middleware"):
        super().__init__(app)
        self.logger = get_logger(logger_name)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成请求ID
        request_id = str(uuid.uuid4())
        start_time = time.time()

        # 设置日志上下文
        with LogContext(request_id=request_id):
            # 记录请求开始
            self.logger.info(
                f"HTTP request started",
                extra={
                    'event': 'http_request_started',
                    'method': request.method,
                    'url': str(request.url),
                    'path': request.url.path,
                    'query_params': dict(request.query_params),
                    'headers': dict(request.headers),
                    'client_ip': request.client.host if request.client else None,
                    'user_agent': request.headers.get('user-agent'),
                    'request_id': request_id
                }
            )

            try:
                # 处理请求
                response = await call_next(request)

                # 计算处理时间
                duration = time.time() - start_time

                # 记录响应
                self.logger.info(
                    f"HTTP request completed",
                    extra={
                        'event': 'http_request_completed',
                        'method': request.method,
                        'path': request.url.path,
                        'status_code': response.status_code,
                        'duration_seconds': round(duration, 4),
                        'response_size': response.headers.get('content-length'),
                        'request_id': request_id
                    }
                )

                # 设置响应头
                response.headers['X-Request-ID'] = request_id

                return response

            except Exception as e:
                # 计算处理时间
                duration = time.time() - start_time

                # 记录异常
                self.logger.error(
                    f"HTTP request failed",
                    extra={
                        'event': 'http_request_failed',
                        'method': request.method,
                        'path': request.url.path,
                        'duration_seconds': round(duration, 4),
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'request_id': request_id
                    },
                    exc_info=True
                )

                raise


class RedisLoggingMiddleware:
    """
    Redis操作日志中间件
    记录Redis操作的执行情况
    """

    def __init__(self, redis_client, logger_name: str = "redis_middleware"):
        self.redis_client = redis_client
        self.logger = get_logger(logger_name)

    def _wrap_method(self, method_name: str, original_method: Callable) -> Callable:
        """包装Redis方法以添加日志记录"""

        def wrapper(*args, **kwargs):
            start_time = time.time()

            self.logger.debug(
                f"Redis {method_name} operation started",
                extra={
                    'event': 'redis_operation_started',
                    'operation': method_name,
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys()) if kwargs else []
                }
            )

            try:
                result = original_method(*args, **kwargs)
                duration = time.time() - start_time

                self.logger.debug(
                    f"Redis {method_name} operation completed",
                    extra={
                        'event': 'redis_operation_completed',
                        'operation': method_name,
                        'duration_seconds': round(duration, 4),
                        'success': True
                    }
                )

                return result

            except Exception as e:
                duration = time.time() - start_time

                self.logger.error(
                    f"Redis {method_name} operation failed",
                    extra={
                        'event': 'redis_operation_failed',
                        'operation': method_name,
                        'duration_seconds': round(duration, 4),
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'success': False
                    }
                )

                raise

        return wrapper

    def enable_logging(self):
        """启用Redis操作日志记录"""
        # 需要监控的Redis方法
        methods_to_wrap = [
            'get', 'set', 'hget', 'hset', 'hgetall', 'hmset',
            'lpush', 'lpop', 'rpush', 'rpop', 'llen',
            'sadd', 'srem', 'smembers', 'scard',
            'zadd', 'zrem', 'zrange', 'zcard',
            'publish', 'expire', 'delete', 'exists'
        ]

        for method_name in methods_to_wrap:
            if hasattr(self.redis_client, method_name):
                original_method = getattr(self.redis_client, method_name)
                wrapped_method = self._wrap_method(method_name, original_method)
                setattr(self.redis_client, method_name, wrapped_method)


class AsyncRedisLoggingMiddleware:
    """
    异步Redis操作日志中间件
    """

    def __init__(self, redis_client, logger_name: str = "async_redis_middleware"):
        self.redis_client = redis_client
        self.logger = get_logger(logger_name)

    def _wrap_async_method(self, method_name: str, original_method: Callable) -> Callable:
        """包装异步Redis方法以添加日志记录"""

        async def wrapper(*args, **kwargs):
            start_time = time.time()

            self.logger.debug(
                f"Async Redis {method_name} operation started",
                extra={
                    'event': 'async_redis_operation_started',
                    'operation': method_name,
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys()) if kwargs else []
                }
            )

            try:
                result = await original_method(*args, **kwargs)
                duration = time.time() - start_time

                self.logger.debug(
                    f"Async Redis {method_name} operation completed",
                    extra={
                        'event': 'async_redis_operation_completed',
                        'operation': method_name,
                        'duration_seconds': round(duration, 4),
                        'success': True
                    }
                )

                return result

            except Exception as e:
                duration = time.time() - start_time

                self.logger.error(
                    f"Async Redis {method_name} operation failed",
                    extra={
                        'event': 'async_redis_operation_failed',
                        'operation': method_name,
                        'duration_seconds': round(duration, 4),
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'success': False
                    }
                )

                raise

        return wrapper

    def enable_logging(self):
        """启用异步Redis操作日志记录"""
        methods_to_wrap = [
            'get', 'set', 'hget', 'hset', 'hgetall', 'hmset',
            'lpush', 'lpop', 'rpush', 'rpop', 'llen',
            'sadd', 'srem', 'smembers', 'scard',
            'zadd', 'zrem', 'zrange', 'zcard',
            'publish', 'expire', 'delete', 'exists'
        ]

        for method_name in methods_to_wrap:
            if hasattr(self.redis_client, method_name):
                original_method = getattr(self.redis_client, method_name)
                wrapped_method = self._wrap_async_method(method_name, original_method)
                setattr(self.redis_client, method_name, wrapped_method)


class LoggingHandler:
    """
    自定义日志处理器
    将日志事件发送到指标收集器
    """

    def __init__(self, service_name: str):
        self.service_name = service_name

    def handle(self, record):
        """处理日志记录"""
        # 发送到指标收集器
        log_metrics_collector.record_log(
            service_name=self.service_name,
            level=record.levelname,
            message=record.getMessage(),
            extra=getattr(record, '__dict__', {})
        )


def create_logging_handler(service_name: str) -> LoggingHandler:
    """
    创建日志处理器

    Args:
        service_name: 服务名称

    Returns:
        日志处理器实例
    """
    return LoggingHandler(service_name)