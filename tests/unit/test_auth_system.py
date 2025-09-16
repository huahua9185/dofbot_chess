"""
认证系统单元测试
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock

# 设置测试环境的路径
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.auth import (
    PasswordManager, JWTAuthenticator, UserManager, PermissionManager,
    User, Role, Permission, UserStatus, TokenPair,
    AuthenticationError, AuthorizationError, UserExistsError,
    InvalidCredentialsError, TokenExpiredError, InvalidTokenError
)


class TestPasswordManager:
    """密码管理器测试"""

    def setup_method(self):
        """设置测试方法"""
        self.password_manager = PasswordManager()

    def test_hash_password(self):
        """测试密码哈希"""
        password = "TestPassword123!"
        hashed = self.password_manager.hash_password(password)

        assert hashed != password
        assert len(hashed) > 50  # bcrypt hash长度

    def test_verify_password(self):
        """测试密码验证"""
        password = "TestPassword123!"
        hashed = self.password_manager.hash_password(password)

        # 正确密码验证
        assert self.password_manager.verify_password(password, hashed)

        # 错误密码验证
        assert not self.password_manager.verify_password("WrongPassword", hashed)

    def test_generate_password(self):
        """测试密码生成"""
        password = self.password_manager.generate_password(length=12)

        assert len(password) == 12
        assert any(c.isupper() for c in password)  # 有大写字母
        assert any(c.islower() for c in password)  # 有小写字母
        assert any(c.isdigit() for c in password)  # 有数字

    def test_check_password_strength(self):
        """测试密码强度检查"""
        # 强密码
        strong_password = "ComplexPassword123!@#"
        strength = self.password_manager.check_password_strength(strong_password)
        assert strength.is_strong
        assert strength.score >= 4

        # 弱密码
        weak_password = "123456"
        strength = self.password_manager.check_password_strength(weak_password)
        assert not strength.is_strong
        assert strength.score < 3

    def test_validate_password_policy(self):
        """测试密码策略验证"""
        # 符合策略的密码
        valid_password = "ValidPassword123!"
        is_valid, errors = self.password_manager.validate_password_policy(valid_password)
        assert is_valid
        assert len(errors) == 0

        # 不符合策略的密码
        invalid_password = "weak"
        is_valid, errors = self.password_manager.validate_password_policy(invalid_password)
        assert not is_valid
        assert len(errors) > 0


class TestJWTAuthenticator:
    """JWT认证器测试"""

    def setup_method(self):
        """设置测试方法"""
        self.jwt_auth = JWTAuthenticator(secret_key="test_secret_key")
        self.test_user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            full_name="Test User",
            roles=[Role("user", "普通用户", [Permission("games:play", "游戏权限")])]
        )

    def test_create_access_token(self):
        """测试创建访问令牌"""
        token = self.jwt_auth.create_access_token(self.test_user)

        assert isinstance(token, str)
        assert len(token) > 100  # JWT token长度

    def test_create_refresh_token(self):
        """测试创建刷新令牌"""
        token = self.jwt_auth.create_refresh_token(self.test_user)

        assert isinstance(token, str)
        assert len(token) > 100

    def test_create_token_pair(self):
        """测试创建令牌对"""
        token_pair = self.jwt_auth.create_token_pair(self.test_user)

        assert isinstance(token_pair, TokenPair)
        assert token_pair.access_token
        assert token_pair.refresh_token
        assert token_pair.token_type == "Bearer"

    def test_verify_token(self):
        """测试验证令牌"""
        token = self.jwt_auth.create_access_token(self.test_user)
        payload = self.jwt_auth.verify_token(token)

        assert payload['sub'] == self.test_user.username
        assert payload['type'] == 'access'

    def test_expired_token(self):
        """测试过期令牌"""
        # 创建已过期的令牌
        expired_token = self.jwt_auth.create_access_token(
            self.test_user,
            expires_delta=timedelta(seconds=-1)  # 负数时间，立即过期
        )

        with pytest.raises(TokenExpiredError):
            self.jwt_auth.verify_token(expired_token)

    def test_invalid_token(self):
        """测试无效令牌"""
        with pytest.raises(InvalidTokenError):
            self.jwt_auth.verify_token("invalid.token.here")

    def test_get_current_user_from_token(self):
        """测试从令牌获取用户信息"""
        token = self.jwt_auth.create_access_token(self.test_user)
        user_info = self.jwt_auth.get_current_user_from_token(token)

        assert user_info['username'] == self.test_user.username
        assert user_info['email'] == self.test_user.email
        assert 'games:play' in user_info['permissions']

    def test_extract_bearer_token(self):
        """测试提取Bearer令牌"""
        token = "sample_token"
        auth_header = f"Bearer {token}"

        extracted = self.jwt_auth.extract_bearer_token(auth_header)
        assert extracted == token

        # 无效格式
        with pytest.raises(InvalidTokenError):
            self.jwt_auth.extract_bearer_token("Invalid header")


class TestUserModel:
    """用户模型测试"""

    def setup_method(self):
        """设置测试方法"""
        self.permission = Permission("games:play", "游戏权限")
        self.role = Role("user", "普通用户", [self.permission])
        self.user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            roles=[self.role]
        )

    def test_user_creation(self):
        """测试用户创建"""
        assert self.user.username == "testuser"
        assert self.user.email == "test@example.com"
        assert self.user.status == UserStatus.ACTIVE

    def test_has_role(self):
        """测试角色检查"""
        assert self.user.has_role("user")
        assert not self.user.has_role("admin")

    def test_has_permission(self):
        """测试权限检查"""
        assert self.user.has_permission("games:play")
        assert not self.user.has_permission("admin:all")

    def test_is_active(self):
        """测试用户激活状态"""
        assert self.user.is_active()

        # 禁用用户
        self.user.status = UserStatus.INACTIVE
        assert not self.user.is_active()

    def test_lock_account(self):
        """测试账户锁定"""
        self.user.lock_account(30)  # 锁定30分钟

        assert self.user.is_locked()
        assert not self.user.is_active()

    def test_unlock_account(self):
        """测试账户解锁"""
        self.user.lock_account(30)
        assert self.user.is_locked()

        self.user.unlock_account()
        assert not self.user.is_locked()
        assert self.user.failed_login_attempts == 0

    def test_record_login_attempt(self):
        """测试登录尝试记录"""
        # 成功登录
        self.user.record_login_attempt(True)
        assert self.user.last_login is not None
        assert self.user.failed_login_attempts == 0

        # 失败登录
        for i in range(5):
            self.user.record_login_attempt(False)

        assert self.user.failed_login_attempts == 5
        assert self.user.is_locked()  # 失败5次后锁定

    def test_user_serialization(self):
        """测试用户序列化"""
        user_dict = self.user.to_dict()

        assert user_dict['username'] == self.user.username
        assert user_dict['email'] == self.user.email
        assert 'password_hash' not in user_dict  # 默认不包含敏感信息

        # 包含敏感信息
        sensitive_dict = self.user.to_dict(include_sensitive=True)
        assert 'password_hash' in sensitive_dict

    def test_user_deserialization(self):
        """测试用户反序列化"""
        user_dict = self.user.to_dict(include_sensitive=True)
        restored_user = User.from_dict(user_dict)

        assert restored_user.username == self.user.username
        assert restored_user.email == self.user.email
        assert restored_user.password_hash == self.user.password_hash


@pytest.mark.asyncio
class TestUserManager:
    """用户管理器测试"""

    def setup_method(self):
        """设置测试方法"""
        self.mock_db = MagicMock()
        self.mock_collection = AsyncMock()
        self.mock_db.users = self.mock_collection
        self.mock_db.sessions = AsyncMock()

        self.password_manager = PasswordManager()
        self.user_manager = UserManager(self.mock_db, self.password_manager)

    async def test_create_user_success(self):
        """测试成功创建用户"""
        # 模拟数据库查询返回None（用户不存在）
        self.mock_collection.find_one.return_value = None
        self.mock_collection.insert_one.return_value = AsyncMock()

        user = await self.user_manager.create_user(
            username="newuser",
            email="new@example.com",
            password="ValidPassword123!"
        )

        assert user.username == "newuser"
        assert user.email == "new@example.com"
        assert user.status == UserStatus.ACTIVE

        # 验证数据库调用
        self.mock_collection.find_one.assert_called_once()
        self.mock_collection.insert_one.assert_called_once()

    async def test_create_user_exists(self):
        """测试创建已存在的用户"""
        # 模拟用户已存在
        self.mock_collection.find_one.return_value = {
            'username': 'existinguser',
            'email': 'existing@example.com'
        }

        with pytest.raises(UserExistsError):
            await self.user_manager.create_user(
                username="existinguser",
                email="new@example.com",
                password="ValidPassword123!"
            )

    async def test_authenticate_user_success(self):
        """测试成功认证用户"""
        # 创建测试用户数据
        password = "TestPassword123!"
        hashed_password = self.password_manager.hash_password(password)

        user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password_hash': hashed_password,
            'full_name': '',
            'roles': [],
            'status': UserStatus.ACTIVE.value,
            'last_login': None,
            'failed_login_attempts': 0,
            'locked_until': None,
            'preferences': {},
            'metadata': {},
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }

        self.mock_collection.find_one.return_value = user_data
        self.mock_collection.update_one.return_value = AsyncMock()

        user = await self.user_manager.authenticate_user('testuser', password)

        assert user.username == 'testuser'
        assert user.last_login is not None

    async def test_authenticate_user_invalid_credentials(self):
        """测试无效凭据认证"""
        password = "TestPassword123!"
        hashed_password = self.password_manager.hash_password(password)

        user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password_hash': hashed_password,
            'full_name': '',
            'roles': [],
            'status': UserStatus.ACTIVE.value,
            'last_login': None,
            'failed_login_attempts': 0,
            'locked_until': None,
            'preferences': {},
            'metadata': {},
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }

        self.mock_collection.find_one.return_value = user_data
        self.mock_collection.update_one.return_value = AsyncMock()

        with pytest.raises(InvalidCredentialsError):
            await self.user_manager.authenticate_user('testuser', 'wrongpassword')


class TestPermissionManager:
    """权限管理器测试"""

    def setup_method(self):
        """设置测试方法"""
        self.mock_db = MagicMock()
        self.mock_roles_collection = AsyncMock()
        self.mock_permissions_collection = AsyncMock()
        self.mock_db.roles = self.mock_roles_collection
        self.mock_db.permissions = self.mock_permissions_collection

        self.permission_manager = PermissionManager(self.mock_db)

    def test_check_permission(self):
        """测试权限检查"""
        permission = Permission("games:play", "游戏权限")
        role = Role("user", "普通用户", [permission])
        user = User("testuser", "test@example.com", roles=[role])

        assert self.permission_manager.check_permission(user, "games:play")
        assert not self.permission_manager.check_permission(user, "admin:all")

    def test_check_role(self):
        """测试角色检查"""
        role = Role("user", "普通用户")
        user = User("testuser", "test@example.com", roles=[role])

        assert self.permission_manager.check_role(user, "user")
        assert not self.permission_manager.check_role(user, "admin")

    def test_check_resource_permission(self):
        """测试资源权限检查"""
        permission = Permission("games:play", "游戏权限", "games", "play")
        role = Role("user", "普通用户", [permission])
        user = User("testuser", "test@example.com", roles=[role])

        assert self.permission_manager.check_resource_permission(user, "games", "play")
        assert not self.permission_manager.check_resource_permission(user, "admin", "manage")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])