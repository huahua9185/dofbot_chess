"""
认证服务主程序
提供用户认证、授权和会话管理的REST API
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from motor.motor_asyncio import AsyncIOMotorClient

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.logging import setup_logging, get_logger, LogContext
from shared.auth import (
    JWTAuthenticator, UserManager, PermissionManager, PasswordManager,
    AuthMiddleware, get_current_user, get_current_active_user, require_permissions,
    User, Role, Permission, UserStatus, TokenPair,
    AuthenticationError, AuthorizationError, UserExistsError, UserNotFoundError,
    InvalidCredentialsError, AccountDisabledError
)
from shared.config.database import get_database_url


# 设置结构化日志
logger = setup_logging("auth_service")

# 全局变量
app = None
db_client = None
db = None
user_manager = None
permission_manager = None
jwt_authenticator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global db_client, db, user_manager, permission_manager, jwt_authenticator

    # 启动时执行
    logger.info("认证服务启动", extra={'event': 'auth_service_startup'})

    try:
        # 初始化数据库连接
        database_url = get_database_url()
        db_client = AsyncIOMotorClient(database_url)
        db = db_client.chess_robot

        # 初始化管理器
        password_manager = PasswordManager()
        user_manager = UserManager(db, password_manager)
        permission_manager = PermissionManager(db)
        jwt_authenticator = JWTAuthenticator()

        # 初始化默认权限和角色
        await permission_manager.initialize_default_permissions()
        await permission_manager.initialize_default_roles()

        # 创建默认管理员用户
        await create_default_admin()

        logger.info("认证服务初始化完成", extra={
            'event': 'auth_service_initialized',
            'database_url': database_url.replace(database_url.split('@')[0], '***') if '@' in database_url else database_url
        })

    except Exception as e:
        logger.error("认证服务初始化失败", extra={
            'event': 'auth_service_init_failed',
            'error': str(e)
        }, exc_info=True)
        raise

    yield

    # 关闭时执行
    logger.info("认证服务关闭", extra={'event': 'auth_service_shutdown'})
    if db_client:
        db_client.close()


async def create_default_admin():
    """创建默认管理员用户"""
    admin_username = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
    admin_password = os.getenv('DEFAULT_ADMIN_PASSWORD', 'ChessRobot2024!')
    admin_email = os.getenv('DEFAULT_ADMIN_EMAIL', 'admin@chessrobot.local')

    try:
        # 检查是否已存在
        existing_user = await user_manager.get_user_by_username(admin_username)
        if existing_user:
            logger.info("默认管理员用户已存在", extra={
                'event': 'default_admin_exists',
                'username': admin_username
            })
            return

        # 获取管理员角色
        admin_role = await permission_manager.get_role('admin')
        if not admin_role:
            logger.error("管理员角色不存在")
            return

        # 创建管理员用户
        admin_user = await user_manager.create_user(
            username=admin_username,
            email=admin_email,
            password=admin_password,
            full_name="系统管理员",
            roles=[admin_role],
            status=UserStatus.ACTIVE
        )

        logger.info("创建默认管理员用户成功", extra={
            'event': 'default_admin_created',
            'username': admin_username,
            'email': admin_email
        })

    except Exception as e:
        logger.error("创建默认管理员用户失败", extra={
            'event': 'default_admin_creation_failed',
            'error': str(e)
        }, exc_info=True)


# 创建FastAPI应用
app = FastAPI(
    title="Chess Robot Auth Service",
    description="智能象棋机器人认证和授权服务",
    version="1.0.0",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 安全方案
security = HTTPBearer()


# 请求/响应模型
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str = ""


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UserResponse(BaseModel):
    username: str
    email: str
    full_name: str
    roles: List[str]
    permissions: List[str]
    status: str
    last_login: Optional[datetime] = None
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            roles=[role.name for role in user.roles],
            permissions=[perm.name for perm in user.get_all_permissions()],
            status=user.status.value,
            last_login=user.last_login,
            created_at=user.created_at
        )


@app.post("/api/auth/register", response_model=UserResponse)
async def register(request: RegisterRequest):
    """用户注册"""
    with LogContext(operation="user_registration"):
        try:
            logger.info("用户注册请求", extra={
                'event': 'user_registration_request',
                'username': request.username,
                'email': request.email
            })

            # 获取默认用户角色
            user_role = await permission_manager.get_role('user')
            if not user_role:
                logger.error("默认用户角色不存在")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="系统配置错误"
                )

            user = await user_manager.create_user(
                username=request.username,
                email=request.email,
                password=request.password,
                full_name=request.full_name,
                roles=[user_role]
            )

            logger.info("用户注册成功", extra={
                'event': 'user_registered',
                'username': user.username,
                'email': user.email
            })

            return UserResponse.from_user(user)

        except UserExistsError as e:
            logger.warning("用户注册失败：用户已存在", extra={
                'event': 'user_registration_failed',
                'username': request.username,
                'error': str(e)
            })
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        except ValueError as e:
            logger.warning("用户注册失败：参数无效", extra={
                'event': 'user_registration_failed',
                'username': request.username,
                'error': str(e)
            })
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error("用户注册失败：系统错误", extra={
                'event': 'user_registration_error',
                'username': request.username,
                'error': str(e)
            }, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="注册失败"
            )


@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """用户登录"""
    with LogContext(operation="user_login"):
        try:
            logger.info("用户登录请求", extra={
                'event': 'user_login_request',
                'username': request.username
            })

            # 认证用户
            user = await user_manager.authenticate_user(request.username, request.password)

            # 创建令牌对
            token_pair = jwt_authenticator.create_token_pair(user)

            logger.info("用户登录成功", extra={
                'event': 'user_login_success',
                'username': user.username,
                'roles': [role.name for role in user.roles]
            })

            return {
                'access_token': token_pair.access_token,
                'refresh_token': token_pair.refresh_token,
                'token_type': token_pair.token_type,
                'expires_in': token_pair.expires_in,
                'user': UserResponse.from_user(user)
            }

        except (InvalidCredentialsError, AccountDisabledError) as e:
            logger.warning("用户登录失败", extra={
                'event': 'user_login_failed',
                'username': request.username,
                'error': str(e)
            })
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
        except Exception as e:
            logger.error("用户登录错误", extra={
                'event': 'user_login_error',
                'username': request.username,
                'error': str(e)
            }, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="登录失败"
            )


@app.post("/api/auth/refresh")
async def refresh_token(refresh_token: str):
    """刷新访问令牌"""
    with LogContext(operation="token_refresh"):
        try:
            # 验证刷新令牌
            payload = jwt_authenticator.verify_token(refresh_token)
            username = payload.get('sub')

            if payload.get('type') != 'refresh':
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="无效的刷新令牌类型"
                )

            # 获取用户
            user = await user_manager.get_user_by_username(username)
            if not user or not user.is_active():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="用户不存在或已禁用"
                )

            # 生成新的访问令牌
            new_access_token = jwt_authenticator.create_access_token(user)

            logger.info("令牌刷新成功", extra={
                'event': 'token_refreshed',
                'username': username
            })

            return {
                'access_token': new_access_token,
                'token_type': 'Bearer',
                'expires_in': jwt_authenticator.access_token_expire_minutes * 60
            }

        except Exception as e:
            logger.error("令牌刷新失败", extra={
                'event': 'token_refresh_failed',
                'error': str(e)
            })
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="刷新令牌失败"
            )


@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """获取当前用户信息"""
    return UserResponse.from_user(current_user)


@app.post("/api/auth/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user)
):
    """修改密码"""
    with LogContext(operation="change_password", user_id=current_user.username):
        try:
            await user_manager.change_password(
                current_user.username,
                request.old_password,
                request.new_password
            )

            logger.info("用户修改密码成功", extra={
                'event': 'password_changed',
                'username': current_user.username
            })

            return {'message': '密码修改成功'}

        except InvalidCredentialsError as e:
            logger.warning("修改密码失败：凭据无效", extra={
                'event': 'password_change_failed',
                'username': current_user.username,
                'error': str(e)
            })
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except ValueError as e:
            logger.warning("修改密码失败：密码不符合要求", extra={
                'event': 'password_change_failed',
                'username': current_user.username,
                'error': str(e)
            })
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )


@app.post("/api/auth/logout")
async def logout(current_user: User = Depends(get_current_active_user)):
    """用户登出"""
    with LogContext(operation="user_logout", user_id=current_user.username):
        # 在实际实现中，这里应该将令牌加入黑名单或撤销会话
        logger.info("用户登出", extra={
            'event': 'user_logout',
            'username': current_user.username
        })

        return {'message': '登出成功'}


@app.get("/api/auth/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_permissions(['users:read']))
):
    """获取用户列表（需要users:read权限）"""
    try:
        users = await user_manager.list_users(skip=skip, limit=limit)
        return [UserResponse.from_user(user) for user in users]
    except Exception as e:
        logger.error("获取用户列表失败", extra={
            'event': 'list_users_failed',
            'error': str(e)
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户列表失败"
        )


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        'status': 'healthy',
        'service': 'auth_service',
        'timestamp': datetime.utcnow().isoformat()
    }


# 异常处理器
@app.exception_handler(AuthenticationError)
async def authentication_exception_handler(request: Request, exc: AuthenticationError):
    """认证异常处理器"""
    logger.warning("认证异常", extra={
        'event': 'authentication_exception',
        'error': str(exc),
        'path': request.url.path
    })

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            'error': exc.error_code,
            'message': exc.message,
            'request_id': LogContext.get_request_id()
        }
    )


@app.exception_handler(AuthorizationError)
async def authorization_exception_handler(request: Request, exc: AuthorizationError):
    """授权异常处理器"""
    logger.warning("授权异常", extra={
        'event': 'authorization_exception',
        'error': str(exc),
        'path': request.url.path
    })

    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            'error': exc.error_code,
            'message': exc.message,
            'request_id': LogContext.get_request_id()
        }
    )


if __name__ == "__main__":
    import uvicorn

    with LogContext(service_name="auth_service", operation="service_startup"):
        logger.info("启动认证服务", extra={
            'event': 'auth_service_startup_initiated',
            'host': '0.0.0.0',
            'port': 8006
        })

        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8006,
            log_level="info",
            reload=False
        )