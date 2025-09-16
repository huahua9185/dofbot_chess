"""
日志上下文管理模块
提供请求跟踪和上下文传递功能
"""

import uuid
import threading
from typing import Dict, Any, Optional
from contextvars import ContextVar


# 定义上下文变量
request_id_var: ContextVar[str] = ContextVar('request_id')
user_id_var: ContextVar[str] = ContextVar('user_id')
game_id_var: ContextVar[str] = ContextVar('game_id')
service_context_var: ContextVar[Dict[str, Any]] = ContextVar('service_context', default={})


class LogContext:
    """
    日志上下文管理器
    用于在请求生命周期内传递上下文信息
    """

    def __init__(
        self,
        request_id: str = None,
        user_id: str = None,
        game_id: str = None,
        **extra_context
    ):
        self.request_id = request_id or str(uuid.uuid4())
        self.user_id = user_id
        self.game_id = game_id
        self.extra_context = extra_context

        # 保存原始上下文值
        self.original_request_id = None
        self.original_user_id = None
        self.original_game_id = None
        self.original_service_context = None

    def __enter__(self):
        """进入上下文管理器"""
        # 保存原始值
        self.original_request_id = request_id_var.get(None)
        self.original_user_id = user_id_var.get(None)
        self.original_game_id = game_id_var.get(None)
        self.original_service_context = service_context_var.get({})

        # 设置新值
        request_id_var.set(self.request_id)
        if self.user_id:
            user_id_var.set(self.user_id)
        if self.game_id:
            game_id_var.set(self.game_id)

        # 合并额外上下文
        new_context = self.original_service_context.copy()
        new_context.update(self.extra_context)
        service_context_var.set(new_context)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器"""
        # 恢复原始值
        if self.original_request_id is not None:
            request_id_var.set(self.original_request_id)
        if self.original_user_id is not None:
            user_id_var.set(self.original_user_id)
        if self.original_game_id is not None:
            game_id_var.set(self.original_game_id)
        if self.original_service_context is not None:
            service_context_var.set(self.original_service_context)

    @staticmethod
    def get_context() -> Dict[str, Any]:
        """
        获取当前上下文信息

        Returns:
            包含上下文信息的字典
        """
        context = {}

        # 获取基础上下文
        try:
            request_id = request_id_var.get()
            if request_id:
                context['request_id'] = request_id
        except LookupError:
            pass

        try:
            user_id = user_id_var.get()
            if user_id:
                context['user_id'] = user_id
        except LookupError:
            pass

        try:
            game_id = game_id_var.get()
            if game_id:
                context['game_id'] = game_id
        except LookupError:
            pass

        # 获取额外上下文
        try:
            extra_context = service_context_var.get({})
            context.update(extra_context)
        except LookupError:
            pass

        return context

    @staticmethod
    def set_request_id(request_id: str):
        """设置请求ID"""
        request_id_var.set(request_id)

    @staticmethod
    def get_request_id() -> Optional[str]:
        """获取请求ID"""
        try:
            return request_id_var.get()
        except LookupError:
            return None

    @staticmethod
    def set_user_id(user_id: str):
        """设置用户ID"""
        user_id_var.set(user_id)

    @staticmethod
    def get_user_id() -> Optional[str]:
        """获取用户ID"""
        try:
            return user_id_var.get()
        except LookupError:
            return None

    @staticmethod
    def set_game_id(game_id: str):
        """设置游戏ID"""
        game_id_var.set(game_id)

    @staticmethod
    def get_game_id() -> Optional[str]:
        """获取游戏ID"""
        try:
            return game_id_var.get()
        except LookupError:
            return None

    @staticmethod
    def add_context(**kwargs):
        """添加额外上下文信息"""
        try:
            current_context = service_context_var.get({})
            new_context = current_context.copy()
            new_context.update(kwargs)
            service_context_var.set(new_context)
        except LookupError:
            service_context_var.set(kwargs)


class ContextualLoggerAdapter:
    """
    上下文感知的日志适配器
    自动添加上下文信息到日志记录
    """

    def __init__(self, logger):
        self.logger = logger

    def _add_context(self, extra: Dict[str, Any] = None) -> Dict[str, Any]:
        """添加上下文信息到额外字段"""
        context = LogContext.get_context()
        if extra:
            context.update(extra)
        return context

    def debug(self, msg, *args, **kwargs):
        kwargs['extra'] = self._add_context(kwargs.get('extra'))
        return self.logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        kwargs['extra'] = self._add_context(kwargs.get('extra'))
        return self.logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        kwargs['extra'] = self._add_context(kwargs.get('extra'))
        return self.logger.warning(msg, *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        kwargs['extra'] = self._add_context(kwargs.get('extra'))
        return self.logger.warn(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        kwargs['extra'] = self._add_context(kwargs.get('extra'))
        return self.logger.error(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        kwargs['extra'] = self._add_context(kwargs.get('extra'))
        return self.logger.exception(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        kwargs['extra'] = self._add_context(kwargs.get('extra'))
        return self.logger.critical(msg, *args, **kwargs)

    def log(self, level, msg, *args, **kwargs):
        kwargs['extra'] = self._add_context(kwargs.get('extra'))
        return self.logger.log(level, msg, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.logger, name)