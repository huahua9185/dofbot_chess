"""
JWT认证管理器
提供JWT令牌的生成、验证和刷新功能
"""

import os
import jwt
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass

from .exceptions import TokenExpiredError, InvalidTokenError, AuthenticationError
from .models import User


@dataclass
class TokenPair:
    """令牌对"""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600  # 秒

    def to_dict(self) -> Dict[str, Any]:
        return {
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'token_type': self.token_type,
            'expires_in': self.expires_in
        }


class JWTAuthenticator:
    """JWT认证器"""

    def __init__(
        self,
        secret_key: str = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 60,
        refresh_token_expire_days: int = 30,
        issuer: str = "chess-robot-system"
    ):
        """
        初始化JWT认证器

        Args:
            secret_key: JWT签名密钥
            algorithm: 签名算法
            access_token_expire_minutes: 访问令牌过期时间（分钟）
            refresh_token_expire_days: 刷新令牌过期时间（天）
            issuer: 令牌发行者
        """
        self.secret_key = secret_key or os.getenv('JWT_SECRET_KEY') or self._generate_secret_key()
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        self.issuer = issuer

    def _generate_secret_key(self) -> str:
        """生成随机密钥"""
        return secrets.token_urlsafe(32)

    def create_access_token(
        self,
        user: User,
        expires_delta: Optional[timedelta] = None,
        additional_claims: Dict[str, Any] = None
    ) -> str:
        """
        创建访问令牌

        Args:
            user: 用户对象
            expires_delta: 过期时间增量
            additional_claims: 额外声明

        Returns:
            JWT访问令牌
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=self.access_token_expire_minutes)

        expire = datetime.now(timezone.utc) + expires_delta

        # 基本声明
        payload = {
            'sub': user.username,  # 主题（用户名）
            'user_id': user.username,  # 用户ID
            'email': user.email,
            'full_name': user.full_name,
            'roles': [role.name for role in user.roles],
            'permissions': [perm.name for perm in user.get_all_permissions()],
            'iat': datetime.now(timezone.utc),  # 签发时间
            'exp': expire,  # 过期时间
            'iss': self.issuer,  # 发行者
            'type': 'access'  # 令牌类型
        }

        # 添加额外声明
        if additional_claims:
            payload.update(additional_claims)

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(
        self,
        user: User,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        创建刷新令牌

        Args:
            user: 用户对象
            expires_delta: 过期时间增量

        Returns:
            JWT刷新令牌
        """
        if expires_delta is None:
            expires_delta = timedelta(days=self.refresh_token_expire_days)

        expire = datetime.now(timezone.utc) + expires_delta

        payload = {
            'sub': user.username,
            'user_id': user.username,
            'iat': datetime.now(timezone.utc),
            'exp': expire,
            'iss': self.issuer,
            'type': 'refresh',
            'jti': secrets.token_hex(16)  # JWT ID，用于令牌撤销
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_token_pair(
        self,
        user: User,
        access_expires_delta: Optional[timedelta] = None,
        refresh_expires_delta: Optional[timedelta] = None
    ) -> TokenPair:
        """
        创建令牌对

        Args:
            user: 用户对象
            access_expires_delta: 访问令牌过期时间增量
            refresh_expires_delta: 刷新令牌过期时间增量

        Returns:
            令牌对
        """
        access_token = self.create_access_token(user, access_expires_delta)
        refresh_token = self.create_refresh_token(user, refresh_expires_delta)

        expires_in = (access_expires_delta or timedelta(minutes=self.access_token_expire_minutes)).total_seconds()

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(expires_in)
        )

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        验证JWT令牌

        Args:
            token: JWT令牌

        Returns:
            解码后的payload

        Raises:
            TokenExpiredError: 令牌过期
            InvalidTokenError: 令牌无效
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={
                    'verify_signature': True,
                    'verify_exp': True,
                    'verify_iat': True,
                    'verify_iss': True
                }
            )

            # 验证发行者
            if payload.get('iss') != self.issuer:
                raise InvalidTokenError("令牌发行者无效")

            return payload

        except jwt.ExpiredSignatureError:
            raise TokenExpiredError("令牌已过期")
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError(f"令牌无效: {str(e)}")
        except Exception as e:
            raise InvalidTokenError(f"令牌验证失败: {str(e)}")

    def get_current_user_from_token(self, token: str) -> Dict[str, Any]:
        """
        从令牌中获取当前用户信息

        Args:
            token: JWT令牌

        Returns:
            用户信息字典
        """
        payload = self.verify_token(token)

        # 验证令牌类型
        if payload.get('type') != 'access':
            raise InvalidTokenError("无效的令牌类型")

        return {
            'username': payload.get('sub'),
            'user_id': payload.get('user_id'),
            'email': payload.get('email'),
            'full_name': payload.get('full_name'),
            'roles': payload.get('roles', []),
            'permissions': payload.get('permissions', [])
        }

    def refresh_access_token(self, refresh_token: str, user: User) -> str:
        """
        使用刷新令牌获取新的访问令牌

        Args:
            refresh_token: 刷新令牌
            user: 用户对象

        Returns:
            新的访问令牌

        Raises:
            InvalidTokenError: 刷新令牌无效
            TokenExpiredError: 刷新令牌过期
        """
        try:
            payload = self.verify_token(refresh_token)

            # 验证令牌类型
            if payload.get('type') != 'refresh':
                raise InvalidTokenError("无效的刷新令牌类型")

            # 验证用户
            if payload.get('sub') != user.username:
                raise InvalidTokenError("刷新令牌用户不匹配")

            # 生成新的访问令牌
            return self.create_access_token(user)

        except (TokenExpiredError, InvalidTokenError):
            raise
        except Exception as e:
            raise InvalidTokenError(f"刷新令牌失败: {str(e)}")

    def decode_token_without_verification(self, token: str) -> Dict[str, Any]:
        """
        不验证签名的情况下解码令牌（用于调试）

        Args:
            token: JWT令牌

        Returns:
            解码后的payload
        """
        try:
            return jwt.decode(
                token,
                options={
                    'verify_signature': False,
                    'verify_exp': False,
                    'verify_iat': False
                }
            )
        except Exception as e:
            raise InvalidTokenError(f"令牌解码失败: {str(e)}")

    def is_token_expired(self, token: str) -> bool:
        """
        检查令牌是否过期（不验证签名）

        Args:
            token: JWT令牌

        Returns:
            是否过期
        """
        try:
            payload = self.decode_token_without_verification(token)
            exp = payload.get('exp')
            if exp:
                return datetime.now(timezone.utc) > datetime.fromtimestamp(exp, tz=timezone.utc)
            return True
        except:
            return True

    def get_token_expiry(self, token: str) -> Optional[datetime]:
        """
        获取令牌过期时间

        Args:
            token: JWT令牌

        Returns:
            过期时间
        """
        try:
            payload = self.decode_token_without_verification(token)
            exp = payload.get('exp')
            if exp:
                return datetime.fromtimestamp(exp, tz=timezone.utc)
            return None
        except:
            return None

    def extract_bearer_token(self, authorization_header: str) -> str:
        """
        从Authorization头中提取Bearer令牌

        Args:
            authorization_header: Authorization头的值

        Returns:
            JWT令牌

        Raises:
            InvalidTokenError: 头格式无效
        """
        if not authorization_header:
            raise InvalidTokenError("缺少Authorization头")

        parts = authorization_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            raise InvalidTokenError("Authorization头格式无效")

        return parts[1]


# 便利函数
def create_access_token(user: User, secret_key: str = None, expires_delta: timedelta = None) -> str:
    """创建访问令牌的便利函数"""
    auth = JWTAuthenticator(secret_key=secret_key)
    return auth.create_access_token(user, expires_delta)


def verify_access_token(token: str, secret_key: str = None) -> Dict[str, Any]:
    """验证访问令牌的便利函数"""
    auth = JWTAuthenticator(secret_key=secret_key)
    return auth.verify_token(token)