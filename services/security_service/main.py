# -*- coding: utf-8 -*-
"""
安全服务主模块
提供统一的安全管理API和监控功能
"""

import sys
import os
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# 导入共享模块
from shared.logging_config import get_logger
from shared.redis_client import RedisClient
from shared.security import (
    EncryptionManager,
    SecurityMonitor,
    DataClassifier,
    TokenVault,
    AccessValidator,
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
    AccessResult
)
from shared.auth import JWTAuthenticator, UserManager


# 配置日志
logger = get_logger(__name__)


# Pydantic模型
class EncryptionRequest(BaseModel):
    data: str
    algorithm: str = "aes"
    key_id: Optional[str] = None


class DecryptionRequest(BaseModel):
    encrypted_data: Dict[str, Any]


class TokenStoreRequest(BaseModel):
    token_id: str
    token_value: str
    token_type: str = "generic"
    expires_hours: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class SecurityEventRequest(BaseModel):
    event_type: str
    severity: str
    source_ip: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    user_agent: Optional[str] = None


class AccessValidationRequest(BaseModel):
    ip_address: str
    user_id: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    request_info: Optional[Dict[str, Any]] = None


class SecurityServiceApp:
    """安全服务应用"""

    def __init__(self):
        self.app = None
        self.encryption_manager = None
        self.security_monitor = None
        self.data_classifier = None
        self.token_vault = None
        self.access_validator = None
        self.redis_client = None
        self.jwt_authenticator = None
        self.user_manager = None

    async def initialize(self):
        """初始化服务组件"""
        try:
            logger.info("初始化安全服务...")

            # 初始化Redis客户端
            self.redis_client = RedisClient()
            await self.redis_client.connect()

            # 初始化加密管理器
            self.encryption_manager = EncryptionManager()

            # 创建默认密钥
            aes_key = self.encryption_manager.create_aes_key("default")
            rsa_private, rsa_public = self.encryption_manager.create_rsa_keypair("default")
            logger.info(f"创建默认AES密钥: {aes_key[:16]}...")
            logger.info("创建默认RSA密钥对")

            # 初始化安全监控器
            self.security_monitor = SecurityMonitor("/app/logs/security_audit.log")

            # 初始化数据分类器
            self.data_classifier = DataClassifier()

            # 初始化令牌保险库
            self.token_vault = TokenVault(
                self.encryption_manager,
                "/app/data/token_vault.json"
            )

            # 初始化访问验证器
            self.access_validator = AccessValidator("/app/config/ip_whitelist.json")

            # 初始化认证组件
            self.jwt_authenticator = JWTAuthenticator()
            self.user_manager = UserManager(
                mongodb_url="mongodb://localhost:27017",
                database_name="chess_robot_auth"
            )
            await self.user_manager.initialize()

            logger.info("安全服务初始化完成")

        except Exception as e:
            logger.error(f"安全服务初始化失败: {e}")
            raise

    async def cleanup(self):
        """清理资源"""
        try:
            if self.redis_client:
                await self.redis_client.close()
            if self.user_manager:
                await self.user_manager.close()
            logger.info("安全服务清理完成")
        except Exception as e:
            logger.error(f"安全服务清理失败: {e}")

    def create_app(self) -> FastAPI:
        """创建FastAPI应用"""
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """应用生命周期管理"""
            await self.initialize()
            yield
            await self.cleanup()

        app = FastAPI(
            title="智能象棋机器人安全服务",
            description="提供数据加密、安全监控、访问控制等功能",
            version="1.0.0",
            lifespan=lifespan
        )

        # 添加CORS中间件
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "https://localhost:3000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # 添加安全中间件
        @app.middleware("http")
        async def security_middleware(request: Request, call_next):
            """安全中间件"""
            start_time = datetime.utcnow()

            # 获取客户端IP
            client_ip = request.client.host
            if "x-forwarded-for" in request.headers:
                client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()

            # 准备请求信息
            request_info = {
                'method': request.method,
                'path': str(request.url.path),
                'user_agent': request.headers.get('user-agent', ''),
                'is_https': request.url.scheme == 'https',
                'content_length': int(request.headers.get('content-length', 0)),
                'headers': dict(request.headers),
                'params': dict(request.query_params)
            }

            # 访问验证
            access_result, access_details = self.access_validator.validate_access(
                ip_address=client_ip,
                resource=str(request.url.path),
                action=request.method,
                request_info=request_info
            )

            # 如果访问被拒绝
            if access_result != AccessResult.ALLOWED:
                # 记录安全事件
                self.security_monitor.log_security_event(
                    SecurityEventType.ACCESS_DENIED,
                    SecuritySeverity.MEDIUM,
                    client_ip,
                    details=access_details
                )

                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "access_denied",
                        "message": access_details.get('reason', '访问被拒绝'),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )

            # 分析请求安全性
            security_events = self.security_monitor.analyze_request({
                'source_ip': client_ip,
                'user_agent': request_info['user_agent'],
                **request_info
            })

            # 如果检测到严重威胁，阻止请求
            critical_events = [
                event for event in security_events
                if event.severity == SecuritySeverity.CRITICAL
            ]

            if critical_events:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "security_threat_detected",
                        "message": "检测到安全威胁，请求被阻止",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )

            # 执行请求
            response = await call_next(request)

            # 计算处理时间
            process_time = (datetime.utcnow() - start_time).total_seconds()
            response.headers["X-Process-Time"] = str(process_time)

            return response

        # 健康检查端点
        @app.get("/health")
        async def health_check():
            """健康检查"""
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "security_service",
                "version": "1.0.0"
            }

        # 加密相关端点
        @app.post("/api/security/encrypt")
        async def encrypt_data(request: EncryptionRequest):
            """加密数据"""
            try:
                data_bytes = request.data.encode('utf-8')
                encrypted_data = self.encryption_manager.encrypt_data(
                    data_bytes,
                    request.key_id,
                    request.algorithm
                )
                return {
                    "success": True,
                    "encrypted_data": encrypted_data,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"数据加密失败: {e}")
                raise HTTPException(status_code=500, detail=f"加密失败: {str(e)}")

        @app.post("/api/security/decrypt")
        async def decrypt_data(request: DecryptionRequest):
            """解密数据"""
            try:
                decrypted_bytes = self.encryption_manager.decrypt_data(request.encrypted_data)
                decrypted_text = decrypted_bytes.decode('utf-8')
                return {
                    "success": True,
                    "decrypted_data": decrypted_text,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"数据解密失败: {e}")
                raise HTTPException(status_code=500, detail=f"解密失败: {str(e)}")

        # 令牌保险库端点
        @app.post("/api/security/tokens")
        async def store_token(request: TokenStoreRequest):
            """存储令牌"""
            try:
                expires_at = None
                if request.expires_hours:
                    expires_at = datetime.utcnow() + timedelta(hours=request.expires_hours)

                success = self.token_vault.store_token(
                    request.token_id,
                    request.token_value,
                    request.token_type,
                    expires_at,
                    request.metadata
                )

                if success:
                    return {
                        "success": True,
                        "message": "令牌存储成功",
                        "token_id": request.token_id
                    }
                else:
                    raise HTTPException(status_code=500, detail="令牌存储失败")

            except Exception as e:
                logger.error(f"令牌存储失败: {e}")
                raise HTTPException(status_code=500, detail=f"存储失败: {str(e)}")

        @app.get("/api/security/tokens/{token_id}")
        async def retrieve_token(token_id: str):
            """检索令牌"""
            try:
                token_value = self.token_vault.retrieve_token(token_id)
                if token_value:
                    return {
                        "success": True,
                        "token_value": token_value
                    }
                else:
                    raise HTTPException(status_code=404, detail="令牌不存在或已过期")

            except Exception as e:
                logger.error(f"令牌检索失败: {e}")
                raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")

        @app.get("/api/security/tokens")
        async def list_tokens(token_type: Optional[str] = None):
            """列出令牌"""
            try:
                tokens = self.token_vault.list_tokens(token_type)
                return {
                    "success": True,
                    "tokens": tokens,
                    "count": len(tokens)
                }
            except Exception as e:
                logger.error(f"令牌列表获取失败: {e}")
                raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")

        @app.delete("/api/security/tokens/{token_id}")
        async def delete_token(token_id: str):
            """删除令牌"""
            try:
                success = self.token_vault.delete_token(token_id)
                if success:
                    return {
                        "success": True,
                        "message": "令牌删除成功"
                    }
                else:
                    raise HTTPException(status_code=404, detail="令牌不存在")

            except Exception as e:
                logger.error(f"令牌删除失败: {e}")
                raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

        # 数据分类端点
        @app.post("/api/security/classify")
        async def classify_data(data: Dict[str, Any]):
            """分类数据"""
            try:
                classifications = self.data_classifier.classify_document(data)
                highest_classification = self.data_classifier.get_highest_classification(data)

                return {
                    "success": True,
                    "classifications": {k: v.value for k, v in classifications.items()},
                    "highest_classification": highest_classification.value,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"数据分类失败: {e}")
                raise HTTPException(status_code=500, detail=f"分类失败: {str(e)}")

        # 安全事件端点
        @app.post("/api/security/events")
        async def log_security_event(request: SecurityEventRequest):
            """记录安全事件"""
            try:
                self.security_monitor.log_security_event(
                    SecurityEventType(request.event_type),
                    SecuritySeverity[request.severity.upper()],
                    request.source_ip,
                    request.user_id,
                    request.session_id,
                    request.resource,
                    request.action,
                    request.details,
                    request.user_agent
                )

                return {
                    "success": True,
                    "message": "安全事件记录成功",
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"安全事件记录失败: {e}")
                raise HTTPException(status_code=500, detail=f"记录失败: {str(e)}")

        @app.get("/api/security/events")
        async def query_security_events(
            hours: int = 24,
            event_type: Optional[str] = None,
            severity: Optional[str] = None,
            user_id: Optional[str] = None,
            source_ip: Optional[str] = None,
            limit: int = 100
        ):
            """查询安全事件"""
            try:
                start_time = datetime.utcnow() - timedelta(hours=hours)
                event_types = [SecurityEventType(event_type)] if event_type else None
                severity_level = SecuritySeverity[severity.upper()] if severity else None

                events = self.security_monitor.audit_logger.query_events(
                    start_time=start_time,
                    event_types=event_types,
                    severity=severity_level,
                    user_id=user_id,
                    source_ip=source_ip,
                    limit=limit
                )

                return {
                    "success": True,
                    "events": [event.to_dict() for event in events],
                    "count": len(events)
                }
            except Exception as e:
                logger.error(f"安全事件查询失败: {e}")
                raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

        # 访问控制端点
        @app.post("/api/security/validate-access")
        async def validate_access(request: AccessValidationRequest):
            """验证访问权限"""
            try:
                access_result, details = self.access_validator.validate_access(
                    request.ip_address,
                    request.user_id,
                    request.resource,
                    request.action,
                    request.request_info
                )

                return {
                    "success": True,
                    "access_result": access_result.value,
                    "details": details,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"访问验证失败: {e}")
                raise HTTPException(status_code=500, detail=f"验证失败: {str(e)}")

        @app.get("/api/security/dashboard")
        async def get_security_dashboard():
            """获取安全仪表板"""
            try:
                dashboard_data = self.security_monitor.get_security_dashboard()

                # 添加额外的统计信息
                dashboard_data.update({
                    'vault_statistics': self.token_vault.get_vault_statistics(),
                    'access_statistics': self.access_validator.get_access_statistics(),
                    'encryption_info': self.encryption_manager.get_key_info()
                })

                return {
                    "success": True,
                    "dashboard": dashboard_data,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"获取安全仪表板失败: {e}")
                raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")

        # 背景任务
        @app.post("/api/security/cleanup")
        async def cleanup_expired_data(background_tasks: BackgroundTasks):
            """清理过期数据"""
            async def cleanup_task():
                try:
                    # 清理过期令牌
                    cleaned_tokens = self.token_vault.cleanup_expired_tokens()
                    logger.info(f"清理了 {cleaned_tokens} 个过期令牌")

                    # 这里可以添加其他清理任务

                except Exception as e:
                    logger.error(f"清理任务失败: {e}")

            background_tasks.add_task(cleanup_task)
            return {
                "success": True,
                "message": "清理任务已启动",
                "timestamp": datetime.utcnow().isoformat()
            }

        self.app = app
        return app

    def run(self, host: str = "0.0.0.0", port: int = 8007, **kwargs):
        """运行服务"""
        if not self.app:
            self.app = self.create_app()

        logger.info(f"启动安全服务在 {host}:{port}")
        uvicorn.run(self.app, host=host, port=port, **kwargs)


# 创建应用实例
security_service = SecurityServiceApp()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="智能象棋机器人安全服务")
    parser.add_argument("--host", default="0.0.0.0", help="服务主机地址")
    parser.add_argument("--port", type=int, default=8007, help="服务端口")
    parser.add_argument("--reload", action="store_true", help="启用自动重载")

    args = parser.parse_args()

    try:
        security_service.run(
            host=args.host,
            port=args.port,
            reload=args.reload
        )
    except KeyboardInterrupt:
        logger.info("安全服务停止")
    except Exception as e:
        logger.error(f"安全服务运行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()