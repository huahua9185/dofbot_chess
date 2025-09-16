"""
权限管理系统
提供基于角色的访问控制(RBAC)功能
"""

from typing import List, Dict, Any, Callable, Optional, Set
from functools import wraps
from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import User, Role, Permission, UserRole
from .exceptions import AuthorizationError, RoleNotFoundError, PermissionNotFoundError


class PermissionManager:
    """权限管理器"""

    def __init__(self, database: AsyncIOMotorDatabase):
        """
        初始化权限管理器

        Args:
            database: MongoDB数据库连接
        """
        self.db = database
        self.roles_collection = database.roles
        self.permissions_collection = database.permissions

    async def create_permission(self, name: str, description: str, resource: str = "", action: str = "") -> Permission:
        """
        创建权限

        Args:
            name: 权限名称
            description: 权限描述
            resource: 资源名称
            action: 操作类型

        Returns:
            创建的权限对象
        """
        # 检查权限是否已存在
        existing = await self.permissions_collection.find_one({'name': name})
        if existing:
            raise PermissionNotFoundError(f"权限 '{name}' 已存在")

        permission = Permission(
            name=name,
            description=description,
            resource=resource,
            action=action
        )

        await self.permissions_collection.insert_one(permission.to_dict())
        return permission

    async def get_permission(self, name: str) -> Optional[Permission]:
        """
        获取权限

        Args:
            name: 权限名称

        Returns:
            权限对象或None
        """
        perm_data = await self.permissions_collection.find_one({'name': name})
        return Permission.from_dict(perm_data) if perm_data else None

    async def list_permissions(self) -> List[Permission]:
        """
        获取所有权限

        Returns:
            权限列表
        """
        cursor = self.permissions_collection.find({})
        permissions_data = await cursor.to_list(length=None)
        return [Permission.from_dict(data) for data in permissions_data]

    async def create_role(self, name: str, description: str, permissions: List[Permission] = None) -> Role:
        """
        创建角色

        Args:
            name: 角色名称
            description: 角色描述
            permissions: 权限列表

        Returns:
            创建的角色对象
        """
        # 检查角色是否已存在
        existing = await self.roles_collection.find_one({'name': name})
        if existing:
            raise RoleNotFoundError(f"角色 '{name}' 已存在")

        role = Role(
            name=name,
            description=description,
            permissions=permissions or []
        )

        await self.roles_collection.insert_one(role.to_dict())
        return role

    async def get_role(self, name: str) -> Optional[Role]:
        """
        获取角色

        Args:
            name: 角色名称

        Returns:
            角色对象或None
        """
        role_data = await self.roles_collection.find_one({'name': name})
        return Role.from_dict(role_data) if role_data else None

    async def update_role(self, role: Role) -> bool:
        """
        更新角色

        Args:
            role: 角色对象

        Returns:
            更新是否成功
        """
        result = await self.roles_collection.update_one(
            {'name': role.name},
            {'$set': role.to_dict()}
        )
        return result.modified_count > 0

    async def delete_role(self, name: str) -> bool:
        """
        删除角色

        Args:
            name: 角色名称

        Returns:
            删除是否成功
        """
        result = await self.roles_collection.delete_one({'name': name})
        return result.deleted_count > 0

    async def list_roles(self) -> List[Role]:
        """
        获取所有角色

        Returns:
            角色列表
        """
        cursor = self.roles_collection.find({})
        roles_data = await cursor.to_list(length=None)
        return [Role.from_dict(data) for data in roles_data]

    async def add_permission_to_role(self, role_name: str, permission_name: str) -> bool:
        """
        为角色添加权限

        Args:
            role_name: 角色名称
            permission_name: 权限名称

        Returns:
            操作是否成功
        """
        role = await self.get_role(role_name)
        if not role:
            raise RoleNotFoundError(f"角色 '{role_name}' 不存在")

        permission = await self.get_permission(permission_name)
        if not permission:
            raise PermissionNotFoundError(f"权限 '{permission_name}' 不存在")

        if not role.has_permission(permission_name):
            role.add_permission(permission)
            return await self.update_role(role)

        return True

    async def remove_permission_from_role(self, role_name: str, permission_name: str) -> bool:
        """
        从角色中移除权限

        Args:
            role_name: 角色名称
            permission_name: 权限名称

        Returns:
            操作是否成功
        """
        role = await self.get_role(role_name)
        if not role:
            raise RoleNotFoundError(f"角色 '{role_name}' 不存在")

        permission = await self.get_permission(permission_name)
        if permission:
            role.remove_permission(permission)
            return await self.update_role(role)

        return True

    def check_permission(self, user: User, required_permission: str) -> bool:
        """
        检查用户是否拥有指定权限

        Args:
            user: 用户对象
            required_permission: 所需权限

        Returns:
            是否拥有权限
        """
        return user.has_permission(required_permission)

    def check_role(self, user: User, required_role: str) -> bool:
        """
        检查用户是否拥有指定角色

        Args:
            user: 用户对象
            required_role: 所需角色

        Returns:
            是否拥有角色
        """
        return user.has_role(required_role)

    def check_resource_permission(self, user: User, resource: str, action: str) -> bool:
        """
        检查用户对特定资源的操作权限

        Args:
            user: 用户对象
            resource: 资源名称
            action: 操作类型

        Returns:
            是否拥有权限
        """
        # 检查具体的资源:操作权限
        specific_permission = f"{resource}:{action}"
        if user.has_permission(specific_permission):
            return True

        # 检查通用权限
        wildcard_permissions = [
            f"{resource}:*",  # 对该资源的所有操作权限
            "*:*",  # 超级管理员权限
            action  # 通用操作权限
        ]

        return any(user.has_permission(perm) for perm in wildcard_permissions)

    async def initialize_default_permissions(self):
        """初始化默认权限"""
        default_permissions = [
            # 系统管理权限
            Permission("system:admin", "系统管理员权限", "system", "admin"),
            Permission("system:read", "系统读取权限", "system", "read"),
            Permission("system:write", "系统写入权限", "system", "write"),

            # 用户管理权限
            Permission("users:create", "创建用户", "users", "create"),
            Permission("users:read", "查看用户", "users", "read"),
            Permission("users:update", "更新用户", "users", "update"),
            Permission("users:delete", "删除用户", "users", "delete"),
            Permission("users:manage", "管理用户", "users", "manage"),

            # 游戏管理权限
            Permission("games:create", "创建游戏", "games", "create"),
            Permission("games:read", "查看游戏", "games", "read"),
            Permission("games:update", "更新游戏", "games", "update"),
            Permission("games:delete", "删除游戏", "games", "delete"),
            Permission("games:play", "游戏对弈", "games", "play"),

            # 设备控制权限
            Permission("devices:control", "设备控制", "devices", "control"),
            Permission("devices:calibrate", "设备标定", "devices", "calibrate"),
            Permission("devices:monitor", "设备监控", "devices", "monitor"),

            # 视觉服务权限
            Permission("vision:process", "视觉处理", "vision", "process"),
            Permission("vision:configure", "视觉配置", "vision", "configure"),

            # 机器人控制权限
            Permission("robot:control", "机器人控制", "robot", "control"),
            Permission("robot:program", "机器人编程", "robot", "program"),

            # AI引擎权限
            Permission("ai:configure", "AI配置", "ai", "configure"),
            Permission("ai:analyze", "AI分析", "ai", "analyze"),

            # 监控权限
            Permission("monitoring:view", "查看监控", "monitoring", "view"),
            Permission("monitoring:configure", "配置监控", "monitoring", "configure"),

            # 日志权限
            Permission("logs:view", "查看日志", "logs", "view"),
            Permission("logs:export", "导出日志", "logs", "export")
        ]

        for permission in default_permissions:
            existing = await self.permissions_collection.find_one({'name': permission.name})
            if not existing:
                await self.permissions_collection.insert_one(permission.to_dict())

    async def initialize_default_roles(self):
        """初始化默认角色"""
        # 确保权限已存在
        await self.initialize_default_permissions()

        # 获取权限对象
        all_permissions = await self.list_permissions()
        perm_dict = {perm.name: perm for perm in all_permissions}

        # 定义默认角色和对应权限
        default_roles = [
            {
                'name': 'admin',
                'description': '系统管理员，拥有所有权限',
                'permissions': list(perm_dict.values())  # 所有权限
            },
            {
                'name': 'operator',
                'description': '操作员，可以进行游戏和设备操作',
                'permissions': [
                    perm_dict.get('games:create'),
                    perm_dict.get('games:read'),
                    perm_dict.get('games:update'),
                    perm_dict.get('games:play'),
                    perm_dict.get('devices:control'),
                    perm_dict.get('devices:calibrate'),
                    perm_dict.get('devices:monitor'),
                    perm_dict.get('vision:process'),
                    perm_dict.get('robot:control'),
                    perm_dict.get('ai:analyze'),
                    perm_dict.get('monitoring:view'),
                    perm_dict.get('logs:view')
                ]
            },
            {
                'name': 'user',
                'description': '普通用户，可以进行基本游戏操作',
                'permissions': [
                    perm_dict.get('games:create'),
                    perm_dict.get('games:read'),
                    perm_dict.get('games:play'),
                    perm_dict.get('devices:monitor'),
                    perm_dict.get('monitoring:view')
                ]
            },
            {
                'name': 'guest',
                'description': '访客用户，只能查看',
                'permissions': [
                    perm_dict.get('games:read'),
                    perm_dict.get('monitoring:view')
                ]
            }
        ]

        for role_data in default_roles:
            existing = await self.roles_collection.find_one({'name': role_data['name']})
            if not existing:
                role = Role(
                    name=role_data['name'],
                    description=role_data['description'],
                    permissions=[p for p in role_data['permissions'] if p is not None],
                    is_system=True
                )
                await self.roles_collection.insert_one(role.to_dict())


# 装饰器函数
def require_permission(permission: str):
    """
    权限检查装饰器

    Args:
        permission: 所需权限

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 从参数中获取用户对象
            user = kwargs.get('current_user') or (args[0] if args and hasattr(args[0], 'has_permission') else None)

            if not user or not hasattr(user, 'has_permission'):
                raise AuthorizationError("缺少用户认证信息")

            if not user.has_permission(permission):
                raise AuthorizationError(f"缺少权限: {permission}")

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_role(role: str):
    """
    角色检查装饰器

    Args:
        role: 所需角色

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 从参数中获取用户对象
            user = kwargs.get('current_user') or (args[0] if args and hasattr(args[0], 'has_role') else None)

            if not user or not hasattr(user, 'has_role'):
                raise AuthorizationError("缺少用户认证信息")

            if not user.has_role(role):
                raise AuthorizationError(f"缺少角色: {role}")

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_resource_permission(resource: str, action: str):
    """
    资源权限检查装饰器

    Args:
        resource: 资源名称
        action: 操作类型

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 从参数中获取用户对象
            user = kwargs.get('current_user') or (args[0] if args and hasattr(args[0], 'has_permission') else None)

            if not user:
                raise AuthorizationError("缺少用户认证信息")

            # 创建权限管理器实例来检查资源权限
            # 注意：这里需要数据库连接，实际使用时可能需要从上下文中获取
            perm_manager = PermissionManager(None)  # 简化实现

            if not perm_manager.check_resource_permission(user, resource, action):
                raise AuthorizationError(f"缺少对资源 {resource} 的 {action} 权限")

            return func(*args, **kwargs)

        return wrapper

    return decorator


# 便利函数
def has_admin_role(user: User) -> bool:
    """检查用户是否为管理员"""
    return user.has_role('admin')


def has_operator_role(user: User) -> bool:
    """检查用户是否为操作员"""
    return user.has_role('operator') or has_admin_role(user)


def can_manage_users(user: User) -> bool:
    """检查用户是否可以管理其他用户"""
    return user.has_permission('users:manage') or has_admin_role(user)


def can_control_devices(user: User) -> bool:
    """检查用户是否可以控制设备"""
    return (user.has_permission('devices:control') or
            user.has_permission('robot:control') or
            has_operator_role(user))


def can_play_games(user: User) -> bool:
    """检查用户是否可以进行游戏"""
    return user.has_permission('games:play')


def can_view_monitoring(user: User) -> bool:
    """检查用户是否可以查看监控"""
    return user.has_permission('monitoring:view')