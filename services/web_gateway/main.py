"""
Web网关服务主程序
集成结构化日志系统示例
"""

import os
import sys
import uvicorn
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.logging import (
    setup_logging, get_logger, LogContext,
    log_async_function_call, log_function_call
)
from shared.logging.middleware import FastAPILoggingMiddleware
from shared.logging.metrics import log_metrics_collector
from shared.logging.context import ContextualLoggerAdapter
from shared.auth import (
    JWTAuthenticator, UserManager, PermissionManager,
    AuthMiddleware, get_current_user, require_permissions,
    User
)
from shared.config import get_database_url


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("Web网关服务启动", extra={
        'event': 'application_startup',
        'service': 'web_gateway'
    })

    # 初始化认证组件（这里简化处理，实际应该从数据库初始化）
    app.state.jwt_auth = JWTAuthenticator()

    yield

    # 关闭时执行
    logger.info("Web网关服务关闭", extra={
        'event': 'application_shutdown',
        'service': 'web_gateway'
    })


# 设置结构化日志
logger = setup_logging(
    service_name="web_gateway",
    log_level=os.getenv("LOG_LEVEL", "INFO")
)

# 创建上下文感知的日志适配器
contextual_logger = ContextualLoggerAdapter(logger)

# 创建FastAPI应用
app = FastAPI(
    title="Chess Robot Web Gateway",
    description="智能象棋机器人Web网关服务",
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

# 添加结构化日志中间件
app.add_middleware(FastAPILoggingMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    contextual_logger.error(
        "未处理的异常",
        extra={
            'event': 'unhandled_exception',
            'path': request.url.path,
            'method': request.method,
            'error_type': type(exc).__name__,
            'error_message': str(exc)
        },
        exc_info=True
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "服务内部错误",
            "request_id": LogContext.get_request_id()
        }
    )


@app.get("/")
@log_function_call(log_duration=True)
async def root():
    """根路径"""
    with LogContext(operation="root_endpoint"):
        contextual_logger.info("访问根路径", extra={
            'event': 'root_endpoint_accessed',
            'response_type': 'welcome_message'
        })

        return {
            "message": "智能象棋机器人Web网关服务",
            "version": "1.0.0",
            "status": "running"
        }


@app.get("/health")
@log_function_call(log_duration=True)
async def health_check():
    """健康检查端点"""
    with LogContext(operation="health_check"):
        contextual_logger.info("健康检查", extra={
            'event': 'health_check_performed',
            'status': 'healthy'
        })

        return {
            "status": "healthy",
            "service": "web_gateway",
            "timestamp": LogContext.get_context().get('timestamp')
        }


@app.get("/metrics/logs")
@log_function_call(log_duration=True)
async def get_log_metrics():
    """获取日志指标"""
    with LogContext(operation="get_log_metrics"):
        try:
            metrics_summary = log_metrics_collector.get_summary()

            contextual_logger.info("获取日志指标", extra={
                'event': 'log_metrics_retrieved',
                'total_services': metrics_summary['total_services']
            })

            return {
                "status": "success",
                "data": metrics_summary
            }

        except Exception as e:
            contextual_logger.error("获取日志指标失败", extra={
                'event': 'log_metrics_retrieval_failed',
                'error_type': type(e).__name__,
                'error_message': str(e)
            }, exc_info=True)

            raise HTTPException(status_code=500, detail="获取指标失败")


@app.get("/metrics/prometheus")
@log_function_call(log_duration=True)
async def get_prometheus_metrics():
    """获取Prometheus格式的日志指标"""
    with LogContext(operation="get_prometheus_metrics"):
        try:
            prometheus_metrics = log_metrics_collector.export_prometheus_metrics()

            contextual_logger.debug("导出Prometheus指标", extra={
                'event': 'prometheus_metrics_exported',
                'format': 'prometheus'
            })

            return Response(
                content=prometheus_metrics,
                media_type="text/plain"
            )

        except Exception as e:
            contextual_logger.error("导出Prometheus指标失败", extra={
                'event': 'prometheus_metrics_export_failed',
                'error_type': type(e).__name__,
                'error_message': str(e)
            }, exc_info=True)

            raise HTTPException(status_code=500, detail="导出指标失败")


@app.post("/api/games")
@log_async_function_call(log_duration=True, log_args=True)
async def create_game(request: Request, current_user: User = Depends(require_permissions(['games:create']))):
    """创建新游戏（需要games:create权限）"""
    with LogContext(operation="create_game", user_id=current_user.username):
        try:
            # 模拟游戏创建逻辑
            game_data = await request.json()

            contextual_logger.info("创建新游戏", extra={
                'event': 'game_creation_requested',
                'game_type': game_data.get('type', 'standard'),
                'difficulty': game_data.get('difficulty', 'medium'),
                'username': current_user.username
            })

            # 这里应该调用游戏管理服务
            # game_service = get_game_service()
            # game_id = await game_service.create_game(game_data)

            game_id = "game_123456"  # 模拟游戏ID

            contextual_logger.info("游戏创建成功", extra={
                'event': 'game_created',
                'game_id': game_id,
                'status': 'created',
                'created_by': current_user.username
            })

            return {
                "status": "success",
                "game_id": game_id,
                "message": "游戏创建成功",
                "created_by": current_user.username
            }

        except Exception as e:
            contextual_logger.error("创建游戏失败", extra={
                'event': 'game_creation_failed',
                'error_type': type(e).__name__,
                'error_message': str(e),
                'username': current_user.username
            }, exc_info=True)

            raise HTTPException(status_code=500, detail="创建游戏失败")


@app.get("/api/games/{game_id}")
@log_async_function_call(log_duration=True)
async def get_game_status(game_id: str):
    """获取游戏状态"""
    with LogContext(game_id=game_id, operation="get_game_status"):
        try:
            contextual_logger.info("获取游戏状态", extra={
                'event': 'game_status_requested',
                'game_id': game_id
            })

            # 模拟游戏状态
            game_status = {
                "game_id": game_id,
                "status": "active",
                "current_player": "human",
                "move_count": 15,
                "last_move": "e2-e4"
            }

            contextual_logger.info("游戏状态获取成功", extra={
                'event': 'game_status_retrieved',
                'game_id': game_id,
                'status': game_status['status'],
                'move_count': game_status['move_count']
            })

            return {
                "status": "success",
                "data": game_status
            }

        except Exception as e:
            contextual_logger.error("获取游戏状态失败", extra={
                'event': 'game_status_retrieval_failed',
                'game_id': game_id,
                'error_type': type(e).__name__,
                'error_message': str(e)
            }, exc_info=True)

            raise HTTPException(status_code=404, detail="游戏未找到")


if __name__ == "__main__":
    # 启动服务
    with LogContext(service_name="web_gateway", operation="service_startup"):
        contextual_logger.info("启动Web网关服务", extra={
            'event': 'service_startup_initiated',
            'host': '0.0.0.0',
            'port': 8000,
            'log_level': os.getenv("LOG_LEVEL", "INFO")
        })

        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            log_level="info",
            reload=False
        )