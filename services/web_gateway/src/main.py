"""
Web网关服务主程序
"""
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os

from shared.config.settings import get_settings
from shared.utils.logger import get_logger
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from api.routes import api_router, ws_router, initialize_services
from services.game_coordinator import GameCoordinator
from services.websocket_manager import WebSocketManager

# 获取配置和日志
settings = get_settings()
logger = get_logger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="智能象棋机器人 API",
    description="基于 Jetson Orin Nano 的智能象棋机器人系统 Web API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.web.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 包含路由
app.include_router(api_router, tags=["API"])
app.include_router(ws_router, tags=["WebSocket"])

# 全局服务实例
game_coordinator = GameCoordinator()
websocket_manager = WebSocketManager()


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    try:
        logger.info("启动Web网关服务")

        # 初始化游戏协调器
        if not await game_coordinator.initialize():
            logger.error("游戏协调器初始化失败")
            raise RuntimeError("游戏协调器初始化失败")

        # 将初始化的服务实例传递给路由
        initialize_services(game_coordinator, websocket_manager)

        # 启动WebSocket心跳检查
        asyncio.create_task(websocket_manager.start_heartbeat())

        logger.info("Web网关服务启动完成")

    except Exception as e:
        logger.error(f"启动失败: {str(e)}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    try:
        logger.info("正在关闭Web网关服务")

        # 关闭游戏协调器
        await game_coordinator.shutdown()

        logger.info("Web网关服务已关闭")

    except Exception as e:
        logger.error(f"关闭失败: {str(e)}")


# 静态文件服务（前端资源）
static_path = os.path.join(os.path.dirname(__file__), "../static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

    # 前端路由处理（SPA支持）
    @app.get("/")
    async def serve_frontend():
        """服务前端首页"""
        index_path = os.path.join(static_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
            return {"message": "前端界面开发中", "api_docs": "/docs"}

    @app.get("/{path:path}")
    async def serve_frontend_routes(path: str):
        """处理前端路由（SPA）"""
        # 首先检查是否是静态资源
        file_path = os.path.join(static_path, path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)

        # 对于前端路由，返回index.html
        index_path = os.path.join(static_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
            raise HTTPException(status_code=404, detail="页面未找到")

else:
    @app.get("/")
    async def api_info():
        """API信息页面"""
        return {
            "message": "智能象棋机器人 Web API",
            "version": "1.0.0",
            "api_docs": "/docs",
            "websocket": "/ws/{game_id}",
            "health_check": "/api/v1/health"
        }


# 错误处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"未处理的异常: {str(exc)}")
    return HTTPException(status_code=500, detail="内部服务器错误")


def create_app():
    """创建应用工厂函数"""
    return app


async def main():
    """主函数"""
    # 配置服务器
    config = uvicorn.Config(
        app=app,
        host=settings.web.host,
        port=settings.web.port,
        log_level="info",
        access_log=True,
        reload=False  # 生产环境关闭热重载
    )

    # 启动服务器
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("服务被手动停止")
    except Exception as e:
        logger.error(f"服务运行错误: {str(e)}")
        raise