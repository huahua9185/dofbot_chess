"""
认证中间件
为FastAPI应用提供JWT认证和权限验证中间件
"""

import re
from typing import Optional, List, Dict, Any, Callable
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
try:
    from fastapi.middleware.base import BaseHTTPMiddleware
except ImportError:
    from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .jwt_auth import JWTAuthenticator
from .user_manager import UserManager
from .permissions import PermissionManager
from .models import User
from .exceptions import (
    AuthenticationError, AuthorizationError, TokenExpiredError,
    InvalidTokenError, SessionExpiredError
)
from ..logging import get_logger, LogContext


logger = get_logger(__name__)


class JWTBearer(HTTPBearer):
    """JWT Bearer认证"""

    def __init__(
        self,
        jwt_authenticator: JWTAuthenticator,
        user_manager: UserManager,
        auto_error: bool = True
    ):
        super().__init__(auto_error=auto_error)
        self.jwt_auth = jwt_authenticator
        self.user_manager = user_manager

    async def __call__(self, request: Request) -> Optional[User]:
        """
        验证JWT令牌并返回用户对象

        Args:
            request: FastAPI请求对象

        Returns:
            用户对象或None

        Raises:
            HTTPException: 认证失败
        """
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)

        if not credentials:
            return None

        try:
            # 验证令牌
            payload = self.jwt_auth.verify_token(credentials.credentials)
            username = payload.get('sub')

            if not username:
                raise InvalidTokenError("令牌中缺少用户信息")

            # 获取用户对象
            user = await self.user_manager.get_user_by_username(username)
            if not user:
                raise InvalidTokenError("用户不存在")

            if not user.is_active():
                raise AuthenticationError("用户账户未激活或被禁用")

            # 设置日志上下文
            LogContext.set_user_id(username)

            logger.info("用户认证成功", extra={
                'event': 'user_authenticated',
                'username': username,
                'user_roles': [role.name for role in user.roles],
                'request_path': request.url.path
            })

            return user

        except TokenExpiredError:
            logger.warning("令牌已过期", extra={
                'event': 'token_expired',
                'request_path': request.url.path
            })
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌已过期",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except InvalidTokenError as e:
            logger.warning("无效令牌", extra={
                'event': 'invalid_token',
                'error': str(e),
                'request_path': request.url.path
            })
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except AuthenticationError as e:
            logger.warning("认证失败", extra={
                'event': 'authentication_failed',
                'error': str(e),
                'request_path': request.url.path
            })
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )


class AuthMiddleware(BaseHTTPMiddleware):
    """认证和授权中间件"""

    def __init__(
        self,
        app,
        jwt_authenticator: JWTAuthenticator,
        user_manager: UserManager,
        permission_manager: PermissionManager = None,
        excluded_paths: List[str] = None,
        public_paths: List[str] = None
    ):
        """
        初始化认证中间件

        Args:
            app: FastAPI应用
            jwt_authenticator: JWT认证器
            user_manager: 用户管理器
            permission_manager: 权限管理器
            excluded_paths: 排除的路径（不需要认证）
            public_paths: 公开路径（使用正则表达式）
        """
        super().__init__(app)
        self.jwt_auth = jwt_authenticator
        self.user_manager = user_manager
        self.permission_manager = permission_manager

        # 默认不需要认证的路径
        self.excluded_paths = excluded_paths or [
            '/docs',
            '/redoc',
            '/openapi.json',
            '/health',
            '/api/auth/login',
            '/api/auth/register',
            '/api/auth/refresh',
            '/favicon.ico'
        ]

        # 编译公开路径的正则表达式
        self.public_patterns = []
        for path in (public_paths or []):
            try:
                self.public_patterns.append(re.compile(path))
            except re.error:
                logger.warning(f"无效的路径正则表达式: {path}")

    def _is_public_path(self, path: str) -> bool:
        """检查路径是否为公开路径"""
        # 检查排除路径
        if path in self.excluded_paths:
            return True

        # 检查以排除路径开头的路径
        for excluded_path in self.excluded_paths:
            if path.startswith(excluded_path):
                return True

        # 检查正则表达式匹配
        for pattern in self.public_patterns:
            if pattern.match(path):
                return True

        return False

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        """
        中间件主处理函数

        Args:
            request: HTTP请求
            call_next: 下一个中间件或路由处理器

        Returns:
            HTTP响应
        """
        path = request.url.path
        method = request.method

        # 跳过公开路径
        if self._is_public_path(path):
            return await call_next(request)

        # 跳过预检请求
        if method == "OPTIONS":
            return await call_next(request)

        try:
            # 提取Authorization头
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "missing_authorization",
                        "message": "缺少Authorization头",
                        "request_id": LogContext.get_request_id()
                    }
                )

            # 提取Bearer令牌
            try:
                token = self.jwt_auth.extract_bearer_token(auth_header)
            except InvalidTokenError as e:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "invalid_authorization_header",
                        "message": str(e),
                        "request_id": LogContext.get_request_id()
                    }
                )

            # 验证令牌
            try:
                payload = self.jwt_auth.verify_token(token)
                username = payload.get('sub')
            except TokenExpiredError:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "token_expired",
                        "message": "令牌已过期",
                        "request_id": LogContext.get_request_id()
                    }
                )
            except InvalidTokenError as e:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "invalid_token",
                        "message": str(e),
                        "request_id": LogContext.get_request_id()
                    }
                )

            # 获取用户信息
            user = await self.user_manager.get_user_by_username(username)
            if not user or not user.is_active():
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "user_inactive",
                        "message": "用户账户未激活或被禁用",
                        "request_id": LogContext.get_request_id()
                    }
                )

            # 将用户信息添加到请求状态中
            request.state.current_user = user
            request.state.token_payload = payload

            # 设置日志上下文
            LogContext.set_user_id(username)
            LogContext.add_context(
                user_roles=[role.name for role in user.roles],
                permissions=[perm.name for perm in user.get_all_permissions()]
            )

            logger.debug("请求通过认证", extra={
                'event': 'request_authenticated',
                'username': username,
                'path': path,
                'method': method
            })

            # 继续处理请求
            response = await call_next(request)

            return response

        except Exception as e:
            logger.error("认证中间件处理异常", extra={
                'event': 'auth_middleware_error',
                'error': str(e),
                'path': path,
                'method': method
            }, exc_info=True)

            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "authentication_error",
                    "message": "认证过程中发生错误",
                    "request_id": LogContext.get_request_id()
                }
            )


class PermissionMiddleware(BaseHTTPMiddleware):
    """权限验证中间件"""

    def __init__(
        self,
        app,
        permission_manager: PermissionManager,
        path_permissions: Dict[str, Dict[str, str]] = None
    ):
        """
        初始化权限中间件

        Args:
            app: FastAPI应用
            permission_manager: 权限管理器
            path_permissions: 路径权限映射 {path_pattern: {method: permission}}
        """
        super().__init__(app)
        self.permission_manager = permission_manager
        self.path_permissions = path_permissions or {}

        # 编译路径模式
        self.compiled_patterns = {}
        for pattern, perms in self.path_permissions.items():
            try:
                self.compiled_patterns[re.compile(pattern)] = perms
            except re.error:
                logger.warning(f"无效的路径权限模式: {pattern}")

    def _get_required_permission(self, path: str, method: str) -> Optional[str]:
        """获取路径和方法对应的所需权限"""
        for pattern, permissions in self.compiled_patterns.items():
            if pattern.match(path):
                return permissions.get(method.upper())
        return None

    async def dispatch(self, request: Request, call_next: Callable) -> JSONResponse:
        """
        权限验证处理

        Args:
            request: HTTP请求
            call_next: 下一个中间件或路由处理器

        Returns:
            HTTP响应
        """
        path = request.url.path
        method = request.method

        # 获取当前用户（应该由认证中间件设置）
        user = getattr(request.state, 'current_user', None)
        if not user:
            # 如果没有用户信息，让认证中间件处理
            return await call_next(request)

        # 检查路径所需权限
        required_permission = self._get_required_permission(path, method)
        if not required_permission:
            # 没有特定权限要求，继续处理
            return await call_next(request)

        # 验证权限
        if not user.has_permission(required_permission):
            logger.warning("权限验证失败", extra={
                'event': 'permission_denied',
                'username': user.username,
                'required_permission': required_permission,
                'user_permissions': [perm.name for perm in user.get_all_permissions()],
                'path': path,
                'method': method
            })

            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "permission_denied",
                    "message": f"缺少权限: {required_permission}",
                    "request_id": LogContext.get_request_id()
                }
            )

        logger.debug("权限验证通过", extra={
            'event': 'permission_granted',
            'username': user.username,
            'required_permission': required_permission,
            'path': path,
            'method': method
        })

        return await call_next(request)


# FastAPI依赖函数
def get_current_user(request: Request) -> User:
    """
    FastAPI依赖函数：获取当前认证用户

    Args:
        request: FastAPI请求对象

    Returns:
        当前用户对象

    Raises:
        HTTPException: 用户未认证
    """
    user = getattr(request.state, 'current_user', None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户未认证"
        )
    return user


def get_current_active_user(request: Request) -> User:
    """
    FastAPI依赖函数：获取当前活跃用户

    Args:
        request: FastAPI请求对象

    Returns:
        当前活跃用户对象

    Raises:
        HTTPException: 用户未认证或未激活
    """
    user = get_current_user(request)
    if not user.is_active():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户账户未激活"
        )
    return user


def require_permissions(permissions: List[str]):
    """
    权限检查依赖工厂

    Args:
        permissions: 所需权限列表

    Returns:
        权限检查函数
    """

    def check_permissions(request: Request) -> User:
        user = get_current_active_user(request)

        missing_permissions = [
            perm for perm in permissions
            if not user.has_permission(perm)
        ]

        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限: {', '.join(missing_permissions)}"
            )

        return user

    return check_permissions


def require_roles(roles: List[str]):
    """
    角色检查依赖工厂

    Args:
        roles: 所需角色列表

    Returns:
        角色检查函数
    """

    def check_roles(request: Request) -> User:
        user = get_current_active_user(request)

        user_roles = [role.name for role in user.roles]
        if not any(role in user_roles for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少角色权限，需要其中之一: {', '.join(roles)}"
            )

        return user

    return check_roles