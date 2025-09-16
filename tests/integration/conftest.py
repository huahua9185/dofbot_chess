"""
集成测试配置文件
提供集成测试的fixtures和配置
"""
import pytest
import asyncio
import sys
import os
from typing import AsyncGenerator
import docker
from unittest.mock import Mock, AsyncMock
import redis
import time

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环用于异步集成测试"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def redis_server():
    """启动测试用的Redis服务器"""
    try:
        # 检查Redis是否运行
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        yield r
    except redis.ConnectionError:
        # 如果Redis未运行，尝试启动（仅用于测试）
        pytest.skip("Redis server not available for integration tests")


@pytest.fixture(scope="session")
def docker_client():
    """Docker客户端用于容器化测试"""
    try:
        client = docker.from_env()
        yield client
    except Exception:
        pytest.skip("Docker not available for integration tests")


@pytest.fixture(scope="function")
async def test_database(redis_server):
    """创建测试数据库环境"""
    # 使用测试专用的数据库索引
    test_redis = redis.Redis(host='localhost', port=6379, db=15)

    # 清空测试数据库
    test_redis.flushdb()

    yield test_redis

    # 测试后清理
    test_redis.flushdb()
    test_redis.close()


@pytest.fixture
def mock_vision_service():
    """模拟视觉识别服务"""
    service = AsyncMock()

    # 模拟检测方法
    service.detect_board = AsyncMock(return_value={
        "success": True,
        "board_state": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "confidence": 0.95,
        "processing_time": 0.12
    })

    service.detect_move = AsyncMock(return_value={
        "success": True,
        "move": {"from": "e2", "to": "e4"},
        "confidence": 0.92
    })

    return service


@pytest.fixture
def mock_robot_service():
    """模拟机器人控制服务"""
    service = AsyncMock()

    # 模拟机器人操作
    service.move_piece = AsyncMock(return_value={
        "success": True,
        "execution_time": 1.5,
        "final_position": {"x": 200, "y": 100, "z": 300}
    })

    service.get_status = AsyncMock(return_value={
        "connected": True,
        "moving": False,
        "position": {"x": 0, "y": 0, "z": 350}
    })

    service.home = AsyncMock(return_value={"success": True})

    return service


@pytest.fixture
def mock_ai_service():
    """模拟AI引擎服务"""
    service = AsyncMock()

    # 模拟AI思考
    service.get_best_move = AsyncMock(return_value={
        "success": True,
        "move": "e7e5",
        "evaluation": 0.15,
        "depth": 12,
        "thinking_time": 2.3
    })

    service.analyze_position = AsyncMock(return_value={
        "evaluation": 0.2,
        "best_line": ["e7e5", "Nf3", "Nc6"],
        "depth": 15
    })

    return service


@pytest.fixture
async def game_session():
    """创建测试游戏会话"""
    from shared.models.chess_models import GameState, GameStatus, PieceColor

    game_data = {
        "game_id": "test-integration-game",
        "status": GameStatus.WAITING,
        "human_color": PieceColor.WHITE,
        "ai_color": PieceColor.BLACK,
        "start_time": time.time()
    }

    yield game_data


@pytest.fixture
def integration_test_config():
    """集成测试配置"""
    return {
        "redis": {
            "host": "localhost",
            "port": 6379,
            "db": 15  # 测试专用数据库
        },
        "services": {
            "vision_service": {"port": 8001},
            "robot_service": {"port": 8002},
            "ai_service": {"port": 8003},
            "game_manager": {"port": 8004},
            "web_gateway": {"port": 8000}
        },
        "timeouts": {
            "service_startup": 30,
            "api_request": 10,
            "move_execution": 45
        }
    }


class TestServiceManager:
    """测试服务管理器"""

    def __init__(self):
        self.services = {}
        self.started_services = []

    async def start_service(self, service_name: str, mock_service):
        """启动模拟服务"""
        self.services[service_name] = mock_service
        self.started_services.append(service_name)
        return mock_service

    async def stop_all_services(self):
        """停止所有服务"""
        for service_name in self.started_services:
            # 模拟服务停止
            pass
        self.services.clear()
        self.started_services.clear()

    def get_service(self, service_name: str):
        """获取服务实例"""
        return self.services.get(service_name)


@pytest.fixture
async def service_manager():
    """服务管理器fixture"""
    manager = TestServiceManager()
    yield manager
    await manager.stop_all_services()


# 集成测试辅助函数
async def wait_for_service(host: str, port: int, timeout: int = 30):
    """等待服务启动"""
    import socket
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                return True

        except Exception:
            pass

        await asyncio.sleep(0.5)

    return False


async def send_test_message(redis_client, channel: str, message: dict):
    """发送测试消息到Redis频道"""
    import json
    return redis_client.publish(channel, json.dumps(message))


def assert_message_received(messages: list, expected_type: str, timeout: float = 5.0):
    """断言消息已接收"""
    start_time = time.time()

    while time.time() - start_time < timeout:
        for msg in messages:
            if msg.get("type") == expected_type:
                return msg
        time.sleep(0.1)

    raise AssertionError(f"Expected message type '{expected_type}' not received within {timeout}s")