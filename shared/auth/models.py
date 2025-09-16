"""
用户认证相关数据模型
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class UserStatus(Enum):
    """用户状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class UserRole(Enum):
    """用户角色枚举"""
    ADMIN = "admin"
    OPERATOR = "operator"
    USER = "user"
    GUEST = "guest"


@dataclass
class Permission:
    """权限模型"""
    name: str
    description: str
    resource: str = ""
    action: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __str__(self):
        return f"{self.resource}:{self.action}" if self.resource and self.action else self.name

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'resource': self.resource,
            'action': self.action,
            'created_at': self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Permission':
        return cls(
            name=data['name'],
            description=data['description'],
            resource=data.get('resource', ''),
            action=data.get('action', ''),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.utcnow().isoformat()))
        )


@dataclass
class Role:
    """角色模型"""
    name: str
    description: str
    permissions: List[Permission] = field(default_factory=list)
    is_system: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_permission(self, permission: Permission) -> None:
        """添加权限"""
        if permission not in self.permissions:
            self.permissions.append(permission)
            self.updated_at = datetime.utcnow()

    def remove_permission(self, permission: Permission) -> None:
        """移除权限"""
        if permission in self.permissions:
            self.permissions.remove(permission)
            self.updated_at = datetime.utcnow()

    def has_permission(self, permission_name: str) -> bool:
        """检查是否拥有指定权限"""
        return any(perm.name == permission_name for perm in self.permissions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'permissions': [perm.to_dict() for perm in self.permissions],
            'is_system': self.is_system,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Role':
        permissions = [Permission.from_dict(perm_data) for perm_data in data.get('permissions', [])]
        return cls(
            name=data['name'],
            description=data['description'],
            permissions=permissions,
            is_system=data.get('is_system', False),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.utcnow().isoformat())),
            updated_at=datetime.fromisoformat(data.get('updated_at', datetime.utcnow().isoformat()))
        )


@dataclass
class User:
    """用户模型"""
    username: str
    email: str
    password_hash: str = ""
    full_name: str = ""
    roles: List[Role] = field(default_factory=list)
    status: UserStatus = UserStatus.ACTIVE
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def add_role(self, role: Role) -> None:
        """添加角色"""
        if role not in self.roles:
            self.roles.append(role)
            self.updated_at = datetime.utcnow()

    def remove_role(self, role: Role) -> None:
        """移除角色"""
        if role in self.roles:
            self.roles.remove(role)
            self.updated_at = datetime.utcnow()

    def has_role(self, role_name: str) -> bool:
        """检查是否拥有指定角色"""
        return any(role.name == role_name for role in self.roles)

    def has_permission(self, permission_name: str) -> bool:
        """检查是否拥有指定权限"""
        return any(role.has_permission(permission_name) for role in self.roles)

    def is_locked(self) -> bool:
        """检查账户是否被锁定"""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until

    def is_active(self) -> bool:
        """检查账户是否激活"""
        return self.status == UserStatus.ACTIVE and not self.is_locked()

    def lock_account(self, duration_minutes: int = 30) -> None:
        """锁定账户"""
        self.locked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        self.updated_at = datetime.utcnow()

    def unlock_account(self) -> None:
        """解锁账户"""
        self.locked_until = None
        self.failed_login_attempts = 0
        self.updated_at = datetime.utcnow()

    def record_login_attempt(self, success: bool) -> None:
        """记录登录尝试"""
        if success:
            self.last_login = datetime.utcnow()
            self.failed_login_attempts = 0
        else:
            self.failed_login_attempts += 1
            # 连续失败5次后锁定账户30分钟
            if self.failed_login_attempts >= 5:
                self.lock_account(30)

        self.updated_at = datetime.utcnow()

    def get_all_permissions(self) -> List[Permission]:
        """获取用户所有权限"""
        all_permissions = []
        for role in self.roles:
            all_permissions.extend(role.permissions)
        return list({perm.name: perm for perm in all_permissions}.values())

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """转换为字典"""
        data = {
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'roles': [role.to_dict() for role in self.roles],
            'status': self.status.value,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'failed_login_attempts': self.failed_login_attempts,
            'locked_until': self.locked_until.isoformat() if self.locked_until else None,
            'preferences': self.preferences,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

        if include_sensitive:
            data['password_hash'] = self.password_hash

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """从字典创建用户"""
        roles = [Role.from_dict(role_data) for role_data in data.get('roles', [])]

        return cls(
            username=data['username'],
            email=data['email'],
            password_hash=data.get('password_hash', ''),
            full_name=data.get('full_name', ''),
            roles=roles,
            status=UserStatus(data.get('status', UserStatus.ACTIVE.value)),
            last_login=datetime.fromisoformat(data['last_login']) if data.get('last_login') else None,
            failed_login_attempts=data.get('failed_login_attempts', 0),
            locked_until=datetime.fromisoformat(data['locked_until']) if data.get('locked_until') else None,
            preferences=data.get('preferences', {}),
            metadata=data.get('metadata', {}),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.utcnow().isoformat())),
            updated_at=datetime.fromisoformat(data.get('updated_at', datetime.utcnow().isoformat()))
        )


@dataclass
class Session:
    """用户会话模型"""
    session_id: str
    user_id: str
    username: str
    ip_address: str = ""
    user_agent: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=24))
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """检查会话是否过期"""
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """检查会话是否有效"""
        return self.is_active and not self.is_expired()

    def extend_session(self, hours: int = 24) -> None:
        """延长会话"""
        self.expires_at = datetime.utcnow() + timedelta(hours=hours)
        self.last_activity = datetime.utcnow()

    def terminate(self) -> None:
        """终止会话"""
        self.is_active = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'username': self.username,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'is_active': self.is_active,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        return cls(
            session_id=data['session_id'],
            user_id=data['user_id'],
            username=data['username'],
            ip_address=data.get('ip_address', ''),
            user_agent=data.get('user_agent', ''),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.utcnow().isoformat())),
            last_activity=datetime.fromisoformat(data.get('last_activity', datetime.utcnow().isoformat())),
            expires_at=datetime.fromisoformat(data.get('expires_at', (datetime.utcnow() + timedelta(hours=24)).isoformat())),
            is_active=data.get('is_active', True),
            metadata=data.get('metadata', {})
        )