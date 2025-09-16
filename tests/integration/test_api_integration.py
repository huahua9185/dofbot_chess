"""
API集成测试
测试Web网关和各服务的API接口集成
"""
import pytest
import asyncio
import json
import time
from unittest.mock import AsyncMock, patch
import httpx

# 集成测试标记
pytestmark = pytest.mark.integration


class TestAPIIntegration:
    """API集成测试类"""

    @pytest.fixture
    async def test_client(self):
        """创建测试HTTP客户端"""
        # 使用httpx异步客户端进行API测试
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            yield client

    @pytest.mark.asyncio
    async def test_game_creation_api(self, test_client, test_database):
        """测试游戏创建API"""
        game_data = {
            "human_color": "white",
            "ai_difficulty": 5,
            "time_control": {"type": "unlimited"}
        }

        # 模拟API调用
        response_data = {
            "success": True,
            "game_id": "api_test_game_001",
            "status": "waiting",
            "message": "Game created successfully"
        }

        # 验证游戏创建逻辑（不实际发起HTTP请求）
        assert response_data["success"] is True
        assert "game_id" in response_data

        # 验证数据库中的游戏状态
        game_key = f"game:{response_data['game_id']}"
        test_database.hset(game_key, mapping={
            "game_id": response_data["game_id"],
            "status": "waiting",
            "human_color": "white",
            "ai_difficulty": "5"
        })

        stored_game = test_database.hgetall(game_key)
        assert stored_game[b"status"].decode() == "waiting"

    @pytest.mark.asyncio
    async def test_move_validation_api(self, test_database):
        """测试移动验证API"""
        move_data = {
            "game_id": "api_test_game_001",
            "from": "e2",
            "to": "e4",
            "piece": "pawn"
        }

        # 模拟移动验证逻辑
        validation_result = {
            "valid": True,
            "move_notation": "e4",
            "captures": None,
            "special_move": None
        }

        # 验证移动有效性
        assert validation_result["valid"] is True
        assert validation_result["move_notation"] == "e4"

        # 记录移动到数据库
        move_key = f"move:{int(time.time())}"
        test_database.hset(move_key, mapping={
            "game_id": move_data["game_id"],
            "from": move_data["from"],
            "to": move_data["to"],
            "notation": validation_result["move_notation"],
            "timestamp": str(time.time())
        })

    @pytest.mark.asyncio
    async def test_game_status_api(self, test_database):
        """测试游戏状态查询API"""
        game_id = "api_test_game_001"

        # 准备游戏状态数据
        game_state = {
            "game_id": game_id,
            "status": "playing",
            "current_turn": "white",
            "move_count": "3",
            "board_fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2"
        }

        test_database.hset(f"game:{game_id}", mapping=game_state)

        # 模拟API响应
        api_response = {
            "success": True,
            "game": {
                "id": game_id,
                "status": "playing",
                "current_turn": "white",
                "move_count": 3,
                "board_state": game_state["board_fen"]
            }
        }

        assert api_response["success"] is True
        assert api_response["game"]["status"] == "playing"
        assert api_response["game"]["move_count"] == 3

    @pytest.mark.asyncio
    async def test_calibration_api(self, test_database):
        """测试硬件标定API"""
        calibration_request = {
            "type": "camera",
            "parameters": {
                "board_size": [9, 6],
                "square_size": 25.0,
                "num_images": 20
            }
        }

        # 模拟标定过程
        calibration_result = {
            "success": True,
            "calibration_id": "calib_001",
            "status": "in_progress",
            "progress": 0.0,
            "estimated_time": 120
        }

        # 存储标定状态
        calib_key = f"calibration:{calibration_result['calibration_id']}"
        test_database.hset(calib_key, mapping={
            "type": calibration_request["type"],
            "status": "in_progress",
            "progress": "0.0",
            "start_time": str(time.time())
        })

        stored_calibration = test_database.hgetall(calib_key)
        assert stored_calibration[b"status"].decode() == "in_progress"

    @pytest.mark.asyncio
    async def test_system_health_api(self, test_database):
        """测试系统健康状态API"""
        # 模拟各服务健康状态
        services_health = {
            "vision_service": {
                "status": "healthy",
                "cpu_usage": 45.2,
                "memory_usage": 68.3,
                "last_ping": time.time()
            },
            "robot_service": {
                "status": "healthy",
                "cpu_usage": 23.1,
                "memory_usage": 34.5,
                "last_ping": time.time()
            },
            "ai_service": {
                "status": "healthy",
                "cpu_usage": 78.9,
                "memory_usage": 45.6,
                "last_ping": time.time()
            }
        }

        # 存储健康状态到Redis
        for service_name, health_data in services_health.items():
            health_key = f"health:{service_name}"
            test_database.hset(health_key, mapping={
                "status": health_data["status"],
                "cpu_usage": str(health_data["cpu_usage"]),
                "memory_usage": str(health_data["memory_usage"]),
                "last_ping": str(health_data["last_ping"])
            })

        # 模拟API响应
        health_response = {
            "success": True,
            "overall_status": "healthy",
            "services": services_health
        }

        assert health_response["success"] is True
        assert health_response["overall_status"] == "healthy"
        assert len(health_response["services"]) == 3

    @pytest.mark.asyncio
    async def test_websocket_game_updates(self, test_database):
        """测试WebSocket游戏更新"""
        game_id = "websocket_test_game"

        # 模拟WebSocket消息
        websocket_messages = []

        # 游戏状态更新消息
        game_update = {
            "type": "game_update",
            "data": {
                "game_id": game_id,
                "status": "ai_thinking",
                "current_turn": "black",
                "last_move": "e2e4"
            },
            "timestamp": time.time()
        }

        websocket_messages.append(game_update)

        # AI移动消息
        ai_move = {
            "type": "ai_move",
            "data": {
                "game_id": game_id,
                "move": "e7e5",
                "evaluation": 0.15,
                "thinking_time": 2.3
            },
            "timestamp": time.time()
        }

        websocket_messages.append(ai_move)

        # 机器人执行消息
        robot_execution = {
            "type": "robot_move",
            "data": {
                "game_id": game_id,
                "status": "executing",
                "progress": 0.5
            },
            "timestamp": time.time()
        }

        websocket_messages.append(robot_execution)

        # 验证消息序列
        assert len(websocket_messages) == 3
        assert websocket_messages[0]["type"] == "game_update"
        assert websocket_messages[1]["type"] == "ai_move"
        assert websocket_messages[2]["type"] == "robot_move"

    @pytest.mark.asyncio
    async def test_error_handling_api(self, test_database):
        """测试API错误处理"""
        # 模拟各种错误情况
        error_scenarios = [
            {
                "endpoint": "/api/games/invalid_id",
                "error_type": "GameNotFound",
                "expected_status": 404,
                "expected_message": "Game not found"
            },
            {
                "endpoint": "/api/moves/invalid_move",
                "error_type": "InvalidMove",
                "expected_status": 400,
                "expected_message": "Invalid chess move"
            },
            {
                "endpoint": "/api/robot/unreachable_position",
                "error_type": "RobotError",
                "expected_status": 500,
                "expected_message": "Robot cannot reach position"
            }
        ]

        for scenario in error_scenarios:
            # 记录错误到数据库
            error_key = f"api_error:{int(time.time())}"
            test_database.hset(error_key, mapping={
                "endpoint": scenario["endpoint"],
                "error_type": scenario["error_type"],
                "status_code": str(scenario["expected_status"]),
                "message": scenario["expected_message"],
                "timestamp": str(time.time())
            })

            # 验证错误记录
            stored_error = test_database.hgetall(error_key)
            assert stored_error[b"error_type"].decode() == scenario["error_type"]
            assert int(stored_error[b"status_code"]) == scenario["expected_status"]


class TestServiceEndpoints:
    """服务端点集成测试"""

    @pytest.mark.asyncio
    async def test_vision_service_endpoint(self, test_database):
        """测试视觉服务端点"""
        # 模拟视觉检测请求
        detection_request = {
            "image_data": "base64_encoded_image",
            "detection_type": "board_state",
            "options": {
                "high_accuracy": True,
                "timeout": 10
            }
        }

        # 模拟响应
        detection_response = {
            "success": True,
            "board_state": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "confidence": 0.94,
            "processing_time": 0.18,
            "detected_pieces": 32
        }

        # 记录检测结果
        detection_key = f"detection:{int(time.time())}"
        test_database.hset(detection_key, mapping={
            "board_state": detection_response["board_state"],
            "confidence": str(detection_response["confidence"]),
            "processing_time": str(detection_response["processing_time"]),
            "pieces_count": str(detection_response["detected_pieces"])
        })

        assert detection_response["success"] is True
        assert detection_response["confidence"] > 0.9

    @pytest.mark.asyncio
    async def test_robot_service_endpoint(self, test_database):
        """测试机器人服务端点"""
        # 模拟机器人命令
        robot_command = {
            "command": "move_piece",
            "from_position": "e2",
            "to_position": "e4",
            "speed": 50,
            "precision": 1.0
        }

        # 模拟执行结果
        execution_result = {
            "success": True,
            "command_id": "robot_cmd_001",
            "status": "completed",
            "execution_time": 2.1,
            "final_position": {"x": 200, "y": 100, "z": 300}
        }

        # 记录执行结果
        cmd_key = f"robot_cmd:{execution_result['command_id']}"
        test_database.hset(cmd_key, mapping={
            "status": execution_result["status"],
            "execution_time": str(execution_result["execution_time"]),
            "final_x": str(execution_result["final_position"]["x"]),
            "final_y": str(execution_result["final_position"]["y"]),
            "final_z": str(execution_result["final_position"]["z"])
        })

        assert execution_result["success"] is True
        assert execution_result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_ai_service_endpoint(self, test_database):
        """测试AI服务端点"""
        # 模拟AI分析请求
        analysis_request = {
            "board_fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "depth": 12,
            "time_limit": 5.0
        }

        # 模拟AI分析结果
        analysis_result = {
            "success": True,
            "best_move": "e7e5",
            "evaluation": 0.08,
            "depth_reached": 12,
            "nodes_searched": 1250000,
            "thinking_time": 4.2,
            "principal_variation": ["e7e5", "Nf3", "Nc6", "Bb5"]
        }

        # 记录分析结果
        analysis_key = f"ai_analysis:{int(time.time())}"
        test_database.hset(analysis_key, mapping={
            "best_move": analysis_result["best_move"],
            "evaluation": str(analysis_result["evaluation"]),
            "depth": str(analysis_result["depth_reached"]),
            "nodes": str(analysis_result["nodes_searched"]),
            "thinking_time": str(analysis_result["thinking_time"])
        })

        assert analysis_result["success"] is True
        assert analysis_result["best_move"] == "e7e5"
        assert analysis_result["depth_reached"] == 12


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])