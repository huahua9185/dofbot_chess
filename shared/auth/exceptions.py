"""
认证和授权异常类
"""


class AuthError(Exception):
    """认证和授权基础异常类"""

    def __init__(self, message: str, error_code: str = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class AuthenticationError(AuthError):
    """身份认证异常"""

    def __init__(self, message: str = "身份认证失败", error_code: str = "AUTH_FAILED"):
        super().__init__(message, error_code)


class AuthorizationError(AuthError):
    """权限授权异常"""

    def __init__(self, message: str = "权限不足", error_code: str = "PERMISSION_DENIED"):
        super().__init__(message, error_code)


class TokenExpiredError(AuthenticationError):
    """令牌过期异常"""

    def __init__(self, message: str = "令牌已过期", error_code: str = "TOKEN_EXPIRED"):
        super().__init__(message, error_code)


class InvalidTokenError(AuthenticationError):
    """无效令牌异常"""

    def __init__(self, message: str = "令牌无效", error_code: str = "INVALID_TOKEN"):
        super().__init__(message, error_code)


class UserNotFoundError(AuthenticationError):
    """用户不存在异常"""

    def __init__(self, message: str = "用户不存在", error_code: str = "USER_NOT_FOUND"):
        super().__init__(message, error_code)


class UserExistsError(AuthError):
    """用户已存在异常"""

    def __init__(self, message: str = "用户已存在", error_code: str = "USER_EXISTS"):
        super().__init__(message, error_code)


class InvalidCredentialsError(AuthenticationError):
    """无效凭据异常"""

    def __init__(self, message: str = "用户名或密码错误", error_code: str = "INVALID_CREDENTIALS"):
        super().__init__(message, error_code)


class SessionExpiredError(AuthenticationError):
    """会话过期异常"""

    def __init__(self, message: str = "会话已过期", error_code: str = "SESSION_EXPIRED"):
        super().__init__(message, error_code)


class AccountDisabledError(AuthenticationError):
    """账户被禁用异常"""

    def __init__(self, message: str = "账户已被禁用", error_code: str = "ACCOUNT_DISABLED"):
        super().__init__(message, error_code)


class RoleNotFoundError(AuthorizationError):
    """角色不存在异常"""

    def __init__(self, message: str = "角色不存在", error_code: str = "ROLE_NOT_FOUND"):
        super().__init__(message, error_code)


class PermissionNotFoundError(AuthorizationError):
    """权限不存在异常"""

    def __init__(self, message: str = "权限不存在", error_code: str = "PERMISSION_NOT_FOUND"):
        super().__init__(message, error_code)