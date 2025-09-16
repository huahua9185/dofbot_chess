"""
用户认证和授权系统
提供JWT认证、角色权限管理、会话控制等功能
"""

from .jwt_auth import JWTAuthenticator, create_access_token, verify_access_token
from .password_manager import PasswordManager
from .user_manager import UserManager
from .permissions import PermissionManager, require_permission, require_role
from .middleware import AuthMiddleware
from .models import User, Role, Permission
from .exceptions import AuthenticationError, AuthorizationError

__all__ = [
    'JWTAuthenticator',
    'create_access_token',
    'verify_access_token',
    'PasswordManager',
    'UserManager',
    'PermissionManager',
    'require_permission',
    'require_role',
    'AuthMiddleware',
    'User',
    'Role',
    'Permission',
    'AuthenticationError',
    'AuthorizationError'
]