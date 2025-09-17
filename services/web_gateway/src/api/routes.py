"""
Web网关API路由
"""
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Dict, Any, Optional
import json
import asyncio
from dataclasses import asdict

from shared.models.chess_models import (
    GameState, ChessMove, AIAnalysis, RobotStatus,
    VisionDetection, SystemMetrics, RobotCommand
)
from shared.utils.redis_client import RedisEventBus, Event
from shared.utils.logger import get_logger
from shared.config.settings import get_settings
from models.api_models import (
    GameCreateRequest, GameCreateResponse, MoveRequest,
    GameStatusResponse, AIRequestModel, SystemStatusResponse
)
from services.game_coordinator import GameCoordinator
from services.websocket_manager import WebSocketManager

logger = get_logger(__name__)
settings = get_settings()
security = HTTPBearer()

# 路由器
api_router = APIRouter(prefix="/api/v1")
ws_router = APIRouter()

# 服务实例将在启动时从main模块获取
game_coordinator = None
websocket_manager = None


def initialize_services(gc, wm):
    """初始化服务实例"""
    global game_coordinator, websocket_manager
    game_coordinator = gc
    websocket_manager = wm


# 游戏管理路由
@api_router.post("/games", response_model=GameCreateResponse)
async def create_game(request: GameCreateRequest):
    """创建新游戏"""
    try:
        game_id = await game_coordinator.create_game(
            human_color=request.human_color,
            ai_difficulty=request.ai_difficulty,
            time_control=request.time_control
        )

        return GameCreateResponse(
            game_id=game_id,
            message="游戏创建成功",
            status="created"
        )

    except Exception as e:
        logger.error(f"创建游戏失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建游戏失败: {str(e)}")


@api_router.get("/games/{game_id}", response_model=GameStatusResponse)
async def get_game_status(game_id: str):
    """获取游戏状态"""
    try:
        game_state = await game_coordinator.get_game_state(game_id)
        if not game_state:
            raise HTTPException(status_code=404, detail="游戏未找到")

        return GameStatusResponse(
            game_id=game_id,
            status=game_state.status.value,
            current_player=game_state.current_player.value,
            board_fen=game_state.board.fen_string,
            move_count=len(game_state.move_history),
            last_move=game_state.move_history[-1].notation if game_state.move_history else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取游戏状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取游戏状态失败: {str(e)}")


@api_router.post("/games/{game_id}/moves")
async def make_move(game_id: str, move_request: MoveRequest):
    """执行移动"""
    try:
        result = await game_coordinator.make_move(
            game_id=game_id,
            move=move_request.move,
            player=move_request.player
        )

        if not result:
            raise HTTPException(status_code=400, detail="无效移动")

        return {"message": "移动执行成功", "status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"执行移动失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"执行移动失败: {str(e)}")


@api_router.post("/games/{game_id}/start")
async def start_game(game_id: str):
    """开始游戏"""
    try:
        success = await game_coordinator.start_game(game_id)
        if not success:
            raise HTTPException(status_code=404, detail="游戏未找到或无法启动")

        return {"message": "游戏已启动", "status": "started"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动游戏失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动游戏失败: {str(e)}")


@api_router.post("/games/{game_id}/pause")
async def pause_game(game_id: str):
    """暂停游戏"""
    try:
        success = await game_coordinator.pause_game(game_id)
        if not success:
            raise HTTPException(status_code=404, detail="游戏未找到或无法暂停")

        return {"message": "游戏已暂停", "status": "paused"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"暂停游戏失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"暂停游戏失败: {str(e)}")


@api_router.delete("/games/{game_id}")
async def end_game(game_id: str):
    """结束游戏"""
    try:
        success = await game_coordinator.end_game(game_id)
        if not success:
            raise HTTPException(status_code=404, detail="游戏未找到")

        return {"message": "游戏已结束", "status": "ended"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"结束游戏失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"结束游戏失败: {str(e)}")


# AI相关路由
@api_router.post("/ai/analyze")
async def request_ai_analysis(request: AIRequestModel):
    """请求AI分析"""
    try:
        result = await game_coordinator.request_ai_analysis(
            analysis_type=request.analysis_type,
            position_fen=request.position_fen,
            moves=request.moves,
            depth=request.depth
        )

        return {"analysis": result, "status": "completed"}

    except Exception as e:
        logger.error(f"AI分析失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI分析失败: {str(e)}")


@api_router.post("/ai/difficulty/{game_id}")
async def set_ai_difficulty(game_id: str, difficulty: int):
    """设置AI难度"""
    try:
        if not (1 <= difficulty <= 10):
            raise HTTPException(status_code=400, detail="难度必须在1-10之间")

        success = await game_coordinator.set_ai_difficulty(game_id, difficulty)
        if not success:
            raise HTTPException(status_code=404, detail="游戏未找到")

        return {"message": f"AI难度已设置为{difficulty}级", "difficulty": difficulty}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设置AI难度失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"设置AI难度失败: {str(e)}")


# 机器人控制路由
@api_router.post("/robot/command")
async def send_robot_command(command: dict):
    """发送机器人控制命令"""
    try:
        robot_command = RobotCommand(
            command_type=command.get("command_type"),
            from_position=command.get("from_position"),
            to_position=command.get("to_position"),
            speed=command.get("speed", 50),
            precision=command.get("precision", 1.0),
            timeout=command.get("timeout", 30.0)
        )

        success = await game_coordinator.send_robot_command(robot_command)
        if not success:
            raise HTTPException(status_code=500, detail="发送机器人命令失败")

        return {"message": "机器人命令已发送", "status": "sent"}

    except Exception as e:
        logger.error(f"发送机器人命令失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"发送机器人命令失败: {str(e)}")


@api_router.get("/robot/status")
async def get_robot_status():
    """获取机器人状态"""
    try:
        status = await game_coordinator.get_robot_status()
        return {"robot_status": asdict(status) if status else None}

    except Exception as e:
        logger.error(f"获取机器人状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取机器人状态失败: {str(e)}")


@api_router.post("/robot/emergency_stop")
async def emergency_stop():
    """机器人紧急停止"""
    try:
        success = await game_coordinator.emergency_stop_robot()
        if not success:
            raise HTTPException(status_code=500, detail="紧急停止失败")

        return {"message": "机器人已紧急停止", "status": "stopped"}

    except Exception as e:
        logger.error(f"紧急停止失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"紧急停止失败: {str(e)}")


# 视觉系统路由
@api_router.get("/vision/status")
async def get_vision_status():
    """获取视觉系统状态"""
    try:
        status = await game_coordinator.get_vision_status()
        return {"vision_status": status}

    except Exception as e:
        logger.error(f"获取视觉状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取视觉状态失败: {str(e)}")


@api_router.post("/vision/calibrate")
async def calibrate_vision():
    """标定视觉系统"""
    try:
        success = await game_coordinator.calibrate_vision()
        if not success:
            raise HTTPException(status_code=500, detail="视觉标定失败")

        return {"message": "视觉系统标定完成", "status": "calibrated"}

    except Exception as e:
        logger.error(f"视觉标定失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"视觉标定失败: {str(e)}")


# 系统监控路由
@api_router.get("/system/status", response_model=SystemStatusResponse)
async def get_system_status():
    """获取系统状态"""
    try:
        # 直接获取系统数据，不依赖GameCoordinator状态
        import psutil
        import time

        # CPU使用率
        cpu_usage = psutil.cpu_percent(interval=0.1)

        # 内存使用率
        memory = psutil.virtual_memory()
        memory_usage = memory.percent

        # 磁盘使用率
        disk = psutil.disk_usage('/')
        disk_usage = (disk.used / disk.total) * 100

        # GPU使用率（Jetson平台）
        gpu_usage = 0.0
        try:
            with open('/sys/devices/gpu.0/load', 'r') as f:
                gpu_usage = float(f.read().strip()) / 10  # Jetson GPU load in permille
        except:
            pass

        # 系统温度（Jetson平台）
        temperature = 0.0
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temperature = float(f.read().strip()) / 1000  # 转换为摄氏度
        except:
            pass

        return SystemStatusResponse(
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_usage=disk_usage,
            gpu_usage=gpu_usage,
            temperature=temperature,
            services_status={
                "vision_service": "running",
                "robot_service": "running",
                "ai_service": "running",
                "web_gateway": "running"
            }
        )

    except Exception as e:
        logger.error(f"获取系统状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取系统状态失败: {str(e)}")


@api_router.get("/system/logs")
async def get_system_logs(lines: int = 100, service: Optional[str] = None):
    """获取系统日志"""
    try:
        logs = await game_coordinator.get_system_logs(lines, service)
        return {"logs": logs, "lines": len(logs)}

    except Exception as e:
        logger.error(f"获取系统日志失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取系统日志失败: {str(e)}")


# WebSocket路由
@ws_router.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    """WebSocket连接端点"""
    await websocket.accept()
    await websocket_manager.connect(websocket, game_id)

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message = json.loads(data)

            # 处理客户端消息
            await websocket_manager.handle_client_message(game_id, message)

    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket, game_id)
    except Exception as e:
        logger.error(f"WebSocket错误: {str(e)}")
        await websocket_manager.disconnect(websocket, game_id)


@ws_router.websocket("/ws/system")
async def system_websocket(websocket: WebSocket):
    """系统监控WebSocket"""
    await websocket.accept()
    await websocket_manager.connect_system(websocket)

    try:
        while True:
            # 保持连接，定期发送系统状态
            await asyncio.sleep(5)

            # 获取系统状态并发送
            metrics = await game_coordinator.get_system_metrics()
            if metrics:
                await websocket.send_text(json.dumps({
                    "type": "system_metrics",
                    "data": asdict(metrics)
                }))

    except WebSocketDisconnect:
        await websocket_manager.disconnect_system(websocket)
    except Exception as e:
        logger.error(f"系统WebSocket错误: {str(e)}")
        await websocket_manager.disconnect_system(websocket)


# 健康检查
@api_router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": asyncio.get_event_loop().time(),
        "services": {
            "web_gateway": "running",
            "redis": "connected",
            "game_coordinator": "active"
        }
    }


# 测试端点
@api_router.get("/test/metrics")
async def test_metrics():
    """测试系统指标获取"""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        return {
            "test": "direct_psutil",
            "cpu": cpu,
            "memory": mem,
            "message": "API代码已更新"
        }
    except Exception as e:
        return {"error": str(e)}