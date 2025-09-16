"""
Web网关服务单元测试
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from services.web_gateway.src.api.routes import create_app
from shared.models.chess_models import GameState, Player


class TestWebGatewayAPI:
    """Web网关API测试类"""

    @pytest.fixture
    def app(self):
        """创建FastAPI应用"""
        return create_app()

    @pytest.fixture
    def client(self, app):
        """创建测试客户端"""
        return TestClient(app)

    @pytest.fixture
    def mock_event_bus(self):
        """模拟事件总线"""
        event_bus = Mock()
        event_bus.connect = AsyncMock(return_value=True)
        event_bus.disconnect = AsyncMock()
        event_bus.publish = AsyncMock()
        event_bus.subscribe = AsyncMock()
        return event_bus

    @pytest.fixture
    def mock_database(self):
        """模拟数据库"""
        db = Mock()
        db.connect = AsyncMock(return_value=True)
        db.get_game = AsyncMock(return_value={
            "id": "game-123",
            "status": "playing",
            "white_player": "human",
            "black_player": "ai",
            "current_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "moves": []
        })
        db.get_games = AsyncMock(return_value=[])
        db.create_game = AsyncMock(return_value="game-123")
        return db

    def test_health_check(self, client):
        """测试健康检查"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_api_info(self, client):
        """测试API信息"""
        response = client.get("/api/v1/info")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["name"] == "Chess Robot Web Gateway"

    def test_create_game_success(self, client):
        """测试创建游戏成功"""
        game_data = {
            "white_player": "human",
            "black_player": "ai",
            "ai_difficulty": 3,
            "time_limit": 600
        }

        with patch('services.web_gateway.src.api.routes.game_manager') as mock_gm:
            mock_gm.create_game = AsyncMock(return_value="game-123")

            response = client.post("/api/v1/games", json=game_data)

            assert response.status_code == 201
            data = response.json()
            assert data["game_id"] == "game-123"
            assert data["status"] == "created"

    def test_create_game_invalid_data(self, client):
        """测试创建游戏数据无效"""
        invalid_data = {
            "white_player": "human"
            # 缺少 black_player
        }

        response = client.post("/api/v1/games", json=invalid_data)

        assert response.status_code == 422  # Validation error

    def test_get_game_success(self, client, mock_database):
        """测试获取游戏信息成功"""
        with patch('services.web_gateway.src.api.routes.database', mock_database):
            response = client.get("/api/v1/games/game-123")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "game-123"
            assert data["status"] == "playing"

    def test_get_game_not_found(self, client):
        """测试获取不存在的游戏"""
        with patch('services.web_gateway.src.api.routes.database') as mock_db:
            mock_db.get_game = AsyncMock(return_value=None)

            response = client.get("/api/v1/games/nonexistent")

            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"].lower()

    def test_list_games(self, client, mock_database):
        """测试获取游戏列表"""
        mock_database.get_games.return_value = [
            {"id": "game-1", "status": "playing"},
            {"id": "game-2", "status": "finished"}
        ]

        with patch('services.web_gateway.src.api.routes.database', mock_database):
            response = client.get("/api/v1/games")

            assert response.status_code == 200
            data = response.json()
            assert len(data["games"]) == 2

    def test_start_game_success(self, client):
        """测试开始游戏成功"""
        with patch('services.web_gateway.src.api.routes.game_manager') as mock_gm:
            mock_gm.start_game = AsyncMock(return_value=True)

            response = client.post("/api/v1/games/game-123/start")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_start_game_failure(self, client):
        """测试开始游戏失败"""
        with patch('services.web_gateway.src.api.routes.game_manager') as mock_gm:
            mock_gm.start_game = AsyncMock(return_value=False)

            response = client.post("/api/v1/games/game-123/start")

            assert response.status_code == 400
            data = response.json()
            assert data["success"] is False

    def test_make_move_success(self, client):
        """测试下棋成功"""
        move_data = {
            "from_square": "e2",
            "to_square": "e4",
            "piece_type": "pawn"
        }

        with patch('services.web_gateway.src.api.routes.game_manager') as mock_gm:
            mock_gm.make_move = AsyncMock(return_value={
                "success": True,
                "move": "e2e4",
                "new_fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
            })

            response = client.post("/api/v1/games/game-123/moves", json=move_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["move"] == "e2e4"

    def test_make_move_invalid(self, client):
        """测试无效下棋"""
        move_data = {
            "from_square": "e2",
            "to_square": "e5",  # 无效移动
            "piece_type": "pawn"
        }

        with patch('services.web_gateway.src.api.routes.game_manager') as mock_gm:
            mock_gm.make_move = AsyncMock(return_value={
                "success": False,
                "error": "Invalid move"
            })

            response = client.post("/api/v1/games/game-123/moves", json=move_data)

            assert response.status_code == 400
            data = response.json()
            assert data["success"] is False

    def test_pause_game(self, client):
        """测试暂停游戏"""
        with patch('services.web_gateway.src.api.routes.game_manager') as mock_gm:
            mock_gm.pause_game = AsyncMock(return_value=True)

            response = client.post("/api/v1/games/game-123/pause")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_resume_game(self, client):
        """测试恢复游戏"""
        with patch('services.web_gateway.src.api.routes.game_manager') as mock_gm:
            mock_gm.resume_game = AsyncMock(return_value=True)

            response = client.post("/api/v1/games/game-123/resume")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_end_game(self, client):
        """测试结束游戏"""
        end_data = {
            "result": "white_wins",
            "reason": "checkmate"
        }

        with patch('services.web_gateway.src.api.routes.game_manager') as mock_gm:
            mock_gm.end_game = AsyncMock(return_value=True)

            response = client.post("/api/v1/games/game-123/end", json=end_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_get_system_status(self, client):
        """测试获取系统状态"""
        with patch('services.web_gateway.src.api.routes.system_monitor') as mock_monitor:
            mock_monitor.get_status = AsyncMock(return_value={
                "overall_status": "healthy",
                "services": {
                    "game_manager": {"status": "running", "health": "good"},
                    "vision_service": {"status": "running", "health": "good"},
                    "robot_service": {"status": "running", "health": "good"},
                    "ai_service": {"status": "running", "health": "good"}
                }
            })

            response = client.get("/api/v1/system/status")

            assert response.status_code == 200
            data = response.json()
            assert data["overall_status"] == "healthy"
            assert "services" in data

    def test_trigger_calibration(self, client):
        """测试触发标定"""
        calibration_data = {
            "type": "camera",
            "parameters": {
                "board_size": [9, 6],
                "square_size": 25.0
            }
        }

        with patch('services.web_gateway.src.api.routes.calibration_service') as mock_cal:
            mock_cal.start_calibration = AsyncMock(return_value={
                "success": True,
                "calibration_id": "cal-123"
            })

            response = client.post("/api/v1/calibration/start", json=calibration_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "calibration_id" in data

    def test_get_calibration_status(self, client):
        """测试获取标定状态"""
        with patch('services.web_gateway.src.api.routes.calibration_service') as mock_cal:
            mock_cal.get_calibration_status = AsyncMock(return_value={
                "id": "cal-123",
                "type": "camera",
                "status": "completed",
                "progress": 100,
                "results": {
                    "reprojection_error": 0.5,
                    "success": True
                }
            })

            response = client.get("/api/v1/calibration/cal-123/status")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["progress"] == 100

    def test_download_calibration_data(self, client):
        """测试下载标定数据"""
        mock_data = b'{"camera_matrix": [[1,0,0],[0,1,0],[0,0,1]]}'

        with patch('services.web_gateway.src.api.routes.calibration_service') as mock_cal:
            mock_cal.get_calibration_data = AsyncMock(return_value=mock_data)

            response = client.get("/api/v1/calibration/cal-123/download")

            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"

    def test_request_vision_analysis(self, client):
        """测试请求视觉分析"""
        analysis_request = {
            "type": "board_detection",
            "parameters": {
                "save_image": True
            }
        }

        with patch('services.web_gateway.src.api.routes.vision_service') as mock_vision:
            mock_vision.request_analysis = AsyncMock(return_value={
                "success": True,
                "request_id": "vision-123"
            })

            response = client.post("/api/v1/vision/analyze", json=analysis_request)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "request_id" in data

    def test_get_vision_results(self, client):
        """测试获取视觉分析结果"""
        with patch('services.web_gateway.src.api.routes.vision_service') as mock_vision:
            mock_vision.get_analysis_result = AsyncMock(return_value={
                "request_id": "vision-123",
                "status": "completed",
                "results": {
                    "board_detected": True,
                    "pieces": [
                        {"type": "king", "color": "white", "position": "e1"},
                        {"type": "pawn", "color": "white", "position": "e2"}
                    ]
                }
            })

            response = client.get("/api/v1/vision/results/vision-123")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert "results" in data

    def test_robot_command(self, client):
        """测试机器人命令"""
        command_data = {
            "command": "move",
            "parameters": {
                "from_position": "e2",
                "to_position": "e4",
                "speed": 50
            }
        }

        with patch('services.web_gateway.src.api.routes.robot_service') as mock_robot:
            mock_robot.send_command = AsyncMock(return_value={
                "success": True,
                "command_id": "robot-123"
            })

            response = client.post("/api/v1/robot/command", json=command_data)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "command_id" in data

    def test_get_robot_status(self, client):
        """测试获取机器人状态"""
        with patch('services.web_gateway.src.api.routes.robot_service') as mock_robot:
            mock_robot.get_status = AsyncMock(return_value={
                "is_connected": True,
                "is_moving": False,
                "current_position": {"x": 0, "y": 0, "z": 350},
                "joint_angles": [0, 0, 0, 0, 0, 0],
                "gripper_state": False
            })

            response = client.get("/api/v1/robot/status")

            assert response.status_code == 200
            data = response.json()
            assert data["is_connected"] is True
            assert "current_position" in data

    def test_emergency_stop(self, client):
        """测试紧急停止"""
        with patch('services.web_gateway.src.api.routes.robot_service') as mock_robot:
            mock_robot.emergency_stop = AsyncMock(return_value=True)

            response = client.post("/api/v1/robot/emergency_stop")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_cors_middleware(self, client):
        """测试CORS中间件"""
        response = client.options("/api/v1/games", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST"
        })

        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers

    def test_error_handling_404(self, client):
        """测试404错误处理"""
        response = client.get("/api/v1/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_error_handling_500(self, client):
        """测试500错误处理"""
        with patch('services.web_gateway.src.api.routes.game_manager') as mock_gm:
            mock_gm.create_game = AsyncMock(side_effect=Exception("Internal error"))

            response = client.post("/api/v1/games", json={
                "white_player": "human",
                "black_player": "ai"
            })

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data

    def test_websocket_connection(self, client):
        """测试WebSocket连接"""
        with client.websocket_connect("/ws/game/game-123") as websocket:
            # 测试连接建立
            data = websocket.receive_json()
            assert data["type"] == "connection_established"

    def test_websocket_game_updates(self, client):
        """测试WebSocket游戏更新"""
        with patch('services.web_gateway.src.api.routes.websocket_manager') as mock_ws:
            with client.websocket_connect("/ws/game/game-123") as websocket:
                # 模拟游戏状态更新
                mock_update = {
                    "type": "game_state_update",
                    "data": {
                        "game_id": "game-123",
                        "status": "playing",
                        "current_player": "white"
                    }
                }

                # 发送更新
                websocket.send_json(mock_update)

                # 接收确认
                response = websocket.receive_json()
                assert "type" in response


class TestWebSocketManager:
    """WebSocket管理器测试类"""

    @pytest.fixture
    def ws_manager(self):
        """创建WebSocket管理器"""
        from services.web_gateway.src.api.websocket import WebSocketManager
        return WebSocketManager()

    def test_init(self, ws_manager):
        """测试初始化"""
        assert len(ws_manager.connections) == 0
        assert len(ws_manager.game_subscriptions) == 0

    @pytest.mark.asyncio
    async def test_connect_client(self, ws_manager):
        """测试客户端连接"""
        mock_websocket = Mock()
        client_id = "client-123"

        await ws_manager.connect_client(client_id, mock_websocket)

        assert client_id in ws_manager.connections
        assert ws_manager.connections[client_id] == mock_websocket

    @pytest.mark.asyncio
    async def test_disconnect_client(self, ws_manager):
        """测试客户端断开"""
        mock_websocket = Mock()
        client_id = "client-123"
        game_id = "game-123"

        # 先连接
        await ws_manager.connect_client(client_id, mock_websocket)
        await ws_manager.subscribe_to_game(client_id, game_id)

        # 然后断开
        await ws_manager.disconnect_client(client_id)

        assert client_id not in ws_manager.connections
        assert client_id not in ws_manager.game_subscriptions.get(game_id, [])

    @pytest.mark.asyncio
    async def test_subscribe_to_game(self, ws_manager):
        """测试订阅游戏"""
        client_id = "client-123"
        game_id = "game-123"

        await ws_manager.subscribe_to_game(client_id, game_id)

        assert game_id in ws_manager.game_subscriptions
        assert client_id in ws_manager.game_subscriptions[game_id]

    @pytest.mark.asyncio
    async def test_broadcast_to_game(self, ws_manager):
        """测试向游戏广播消息"""
        mock_websocket = Mock()
        mock_websocket.send_json = AsyncMock()

        client_id = "client-123"
        game_id = "game-123"

        # 连接并订阅
        await ws_manager.connect_client(client_id, mock_websocket)
        await ws_manager.subscribe_to_game(client_id, game_id)

        # 广播消息
        message = {"type": "game_update", "data": {"status": "playing"}}
        await ws_manager.broadcast_to_game(game_id, message)

        mock_websocket.send_json.assert_called_once_with(message)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])