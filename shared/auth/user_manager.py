"""
用户管理器
提供用户增删改查、认证等功能
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .models import User, Role, Permission, UserStatus, Session
from .password_manager import PasswordManager
from .exceptions import (
    UserNotFoundError, UserExistsError, InvalidCredentialsError,
    AuthenticationError, AccountDisabledError, SessionExpiredError
)


class UserManager:
    """用户管理器"""

    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        password_manager: PasswordManager = None,
        max_login_attempts: int = 5,
        lockout_duration_minutes: int = 30
    ):
        """
        初始化用户管理器

        Args:
            database: MongoDB数据库连接
            password_manager: 密码管理器
            max_login_attempts: 最大登录尝试次数
            lockout_duration_minutes: 账户锁定持续时间（分钟）
        """
        self.db = database
        self.users_collection = database.users
        self.sessions_collection = database.sessions
        self.password_manager = password_manager or PasswordManager()
        self.max_login_attempts = max_login_attempts
        self.lockout_duration_minutes = lockout_duration_minutes

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: str = "",
        roles: List[Role] = None,
        status: UserStatus = UserStatus.ACTIVE
    ) -> User:
        """
        创建新用户

        Args:
            username: 用户名
            email: 邮箱
            password: 密码
            full_name: 全名
            roles: 角色列表
            status: 用户状态

        Returns:
            创建的用户对象

        Raises:
            UserExistsError: 用户已存在
            ValueError: 参数无效
        """
        # 验证输入
        if not username or not email or not password:
            raise ValueError("用户名、邮箱和密码不能为空")

        # 验证密码强度
        is_valid, errors = self.password_manager.validate_password_policy(password, username)
        if not is_valid:
            raise ValueError(f"密码不符合安全要求: {'; '.join(errors)}")

        # 检查用户是否已存在
        existing_user = await self.users_collection.find_one({
            '$or': [
                {'username': username},
                {'email': email}
            ]
        })

        if existing_user:
            if existing_user['username'] == username:
                raise UserExistsError(f"用户名 '{username}' 已存在")
            else:
                raise UserExistsError(f"邮箱 '{email}' 已被使用")

        # 创建用户对象
        user = User(
            username=username,
            email=email,
            password_hash=self.password_manager.hash_password(password),
            full_name=full_name,
            roles=roles or [],
            status=status
        )

        # 保存到数据库
        await self.users_collection.insert_one(user.to_dict(include_sensitive=True))

        return user

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        根据用户名获取用户

        Args:
            username: 用户名

        Returns:
            用户对象或None
        """
        user_data = await self.users_collection.find_one({'username': username})
        return User.from_dict(user_data) if user_data else None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """
        根据邮箱获取用户

        Args:
            email: 邮箱

        Returns:
            用户对象或None
        """
        user_data = await self.users_collection.find_one({'email': email})
        return User.from_dict(user_data) if user_data else None

    async def authenticate_user(self, username: str, password: str) -> User:
        """
        认证用户

        Args:
            username: 用户名或邮箱
            password: 密码

        Returns:
            认证成功的用户对象

        Raises:
            InvalidCredentialsError: 凭据无效
            AccountDisabledError: 账户被禁用
            AuthenticationError: 认证失败
        """
        # 支持用户名或邮箱登录
        user = await self.get_user_by_username(username)
        if not user:
            user = await self.get_user_by_email(username)

        if not user:
            raise InvalidCredentialsError("用户名或密码错误")

        # 检查账户状态
        if not user.is_active():
            if user.is_locked():
                raise AccountDisabledError(f"账户被锁定至 {user.locked_until}")
            else:
                raise AccountDisabledError("账户未激活或被禁用")

        # 验证密码
        if not self.password_manager.verify_password(password, user.password_hash):
            # 记录失败的登录尝试
            user.record_login_attempt(success=False)
            await self.update_user(user)

            if user.is_locked():
                raise AccountDisabledError(f"连续登录失败次数过多，账户被锁定 {self.lockout_duration_minutes} 分钟")
            else:
                raise InvalidCredentialsError("用户名或密码错误")

        # 记录成功的登录尝试
        user.record_login_attempt(success=True)
        await self.update_user(user)

        return user

    async def update_user(self, user: User) -> bool:
        """
        更新用户信息

        Args:
            user: 用户对象

        Returns:
            更新是否成功
        """
        user.updated_at = datetime.utcnow()

        result = await self.users_collection.update_one(
            {'username': user.username},
            {'$set': user.to_dict(include_sensitive=True)}
        )

        return result.modified_count > 0

    async def change_password(
        self,
        username: str,
        old_password: str,
        new_password: str
    ) -> bool:
        """
        修改用户密码

        Args:
            username: 用户名
            old_password: 旧密码
            new_password: 新密码

        Returns:
            修改是否成功

        Raises:
            UserNotFoundError: 用户不存在
            InvalidCredentialsError: 旧密码错误
            ValueError: 新密码不符合要求
        """
        user = await self.get_user_by_username(username)
        if not user:
            raise UserNotFoundError()

        # 验证旧密码
        if not self.password_manager.verify_password(old_password, user.password_hash):
            raise InvalidCredentialsError("当前密码错误")

        # 验证新密码强度
        is_valid, errors = self.password_manager.validate_password_policy(new_password, username)
        if not is_valid:
            raise ValueError(f"新密码不符合安全要求: {'; '.join(errors)}")

        # 检查新密码是否与旧密码相同
        if self.password_manager.verify_password(new_password, user.password_hash):
            raise ValueError("新密码不能与当前密码相同")

        # 更新密码
        user.password_hash = self.password_manager.hash_password(new_password)
        return await self.update_user(user)

    async def reset_password(self, username: str, new_password: str) -> bool:
        """
        重置用户密码（管理员功能）

        Args:
            username: 用户名
            new_password: 新密码

        Returns:
            重置是否成功
        """
        user = await self.get_user_by_username(username)
        if not user:
            raise UserNotFoundError()

        # 验证新密码强度
        is_valid, errors = self.password_manager.validate_password_policy(new_password, username)
        if not is_valid:
            raise ValueError(f"新密码不符合安全要求: {'; '.join(errors)}")

        # 更新密码并解锁账户
        user.password_hash = self.password_manager.hash_password(new_password)
        user.unlock_account()

        return await self.update_user(user)

    async def disable_user(self, username: str) -> bool:
        """
        禁用用户

        Args:
            username: 用户名

        Returns:
            操作是否成功
        """
        user = await self.get_user_by_username(username)
        if not user:
            raise UserNotFoundError()

        user.status = UserStatus.INACTIVE
        return await self.update_user(user)

    async def enable_user(self, username: str) -> bool:
        """
        启用用户

        Args:
            username: 用户名

        Returns:
            操作是否成功
        """
        user = await self.get_user_by_username(username)
        if not user:
            raise UserNotFoundError()

        user.status = UserStatus.ACTIVE
        user.unlock_account()
        return await self.update_user(user)

    async def delete_user(self, username: str) -> bool:
        """
        删除用户

        Args:
            username: 用户名

        Returns:
            删除是否成功
        """
        # 同时删除用户的所有会话
        await self.sessions_collection.delete_many({'username': username})

        result = await self.users_collection.delete_one({'username': username})
        return result.deleted_count > 0

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 100,
        status_filter: UserStatus = None
    ) -> List[User]:
        """
        获取用户列表

        Args:
            skip: 跳过的记录数
            limit: 返回的记录数限制
            status_filter: 状态过滤

        Returns:
            用户列表
        """
        query = {}
        if status_filter:
            query['status'] = status_filter.value

        cursor = self.users_collection.find(query).skip(skip).limit(limit)
        users_data = await cursor.to_list(length=limit)

        return [User.from_dict(data) for data in users_data]

    async def create_session(
        self,
        user: User,
        ip_address: str = "",
        user_agent: str = "",
        expires_hours: int = 24
    ) -> Session:
        """
        创建用户会话

        Args:
            user: 用户对象
            ip_address: IP地址
            user_agent: 用户代理
            expires_hours: 过期时间（小时）

        Returns:
            会话对象
        """
        session = Session(
            session_id=str(uuid.uuid4()),
            user_id=user.username,
            username=user.username,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.utcnow() + timedelta(hours=expires_hours)
        )

        await self.sessions_collection.insert_one(session.to_dict())
        return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        获取会话

        Args:
            session_id: 会话ID

        Returns:
            会话对象或None
        """
        session_data = await self.sessions_collection.find_one({'session_id': session_id})
        return Session.from_dict(session_data) if session_data else None

    async def validate_session(self, session_id: str) -> Optional[Session]:
        """
        验证会话

        Args:
            session_id: 会话ID

        Returns:
            有效的会话对象或None

        Raises:
            SessionExpiredError: 会话过期
        """
        session = await self.get_session(session_id)
        if not session:
            return None

        if session.is_expired():
            # 删除过期会话
            await self.sessions_collection.delete_one({'session_id': session_id})
            raise SessionExpiredError()

        if not session.is_valid():
            return None

        # 更新最后活动时间
        session.last_activity = datetime.utcnow()
        await self.sessions_collection.update_one(
            {'session_id': session_id},
            {'$set': {'last_activity': session.last_activity}}
        )

        return session

    async def terminate_session(self, session_id: str) -> bool:
        """
        终止会话

        Args:
            session_id: 会话ID

        Returns:
            操作是否成功
        """
        result = await self.sessions_collection.delete_one({'session_id': session_id})
        return result.deleted_count > 0

    async def terminate_all_user_sessions(self, username: str) -> int:
        """
        终止用户的所有会话

        Args:
            username: 用户名

        Returns:
            终止的会话数量
        """
        result = await self.sessions_collection.delete_many({'username': username})
        return result.deleted_count

    async def cleanup_expired_sessions(self) -> int:
        """
        清理过期会话

        Returns:
            清理的会话数量
        """
        result = await self.sessions_collection.delete_many({
            'expires_at': {'$lt': datetime.utcnow()}
        })
        return result.deleted_count

    async def get_user_sessions(self, username: str) -> List[Session]:
        """
        获取用户的所有活动会话

        Args:
            username: 用户名

        Returns:
            会话列表
        """
        cursor = self.sessions_collection.find({
            'username': username,
            'is_active': True,
            'expires_at': {'$gt': datetime.utcnow()}
        })

        sessions_data = await cursor.to_list(length=None)
        return [Session.from_dict(data) for data in sessions_data]