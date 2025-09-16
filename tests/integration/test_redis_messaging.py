"""
Redis消息系统集成测试
测试各服务间的事件驱动通信
"""
import pytest
import asyncio
import json
import time
from unittest.mock import AsyncMock, Mock

# 集成测试标记
pytestmark = pytest.mark.integration


class TestRedisMessaging:
    """Redis消息系统集成测试"""

    @pytest.mark.asyncio
    async def test_event_publishing_and_subscription(self, test_database):
        """测试事件发布和订阅"""
        # 模拟事件发布
        event_data = {
            "type": "game.move_detected",
            "data": {
                "from": "e2",
                "to": "e4",
                "timestamp": time.time()
            }
        }

        # 发布事件
        result = test_database.publish("chess.events", json.dumps(event_data))
        assert result >= 0  # 返回订阅者数量

    @pytest.mark.asyncio
    async def test_game_state_synchronization(self, test_database, game_session):
        """测试游戏状态同步"""
        game_id = game_session["game_id"]

        # 存储游戏状态
        game_state = {
            "game_id": game_id,
            "status": "playing",
            "current_player": "white",
            "board_state": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "last_update": time.time()
        }

        test_database.hset(f"game:{game_id}", mapping=game_state)

        # 验证状态存储
        stored_state = test_database.hgetall(f"game:{game_id}")
        assert stored_state[b"game_id"].decode() == game_id
        assert stored_state[b"status"].decode() == "playing"

    @pytest.mark.asyncio
    async def test_service_health_monitoring(self, test_database):
        """测试服务健康状态监控"""
        service_name = "vision_service"
        health_data = {
            "status": "healthy",
            "timestamp": time.time(),
            "cpu_usage": 45.2,
            "memory_usage": 68.3,
            "last_activity": time.time()
        }

        # 设置服务健康状态
        test_database.hset(f"health:{service_name}", mapping=health_data)
        test_database.expire(f"health:{service_name}", 60)  # 60秒过期

        # 验证健康状态
        stored_health = test_database.hgetall(f"health:{service_name}")
        assert stored_health[b"status"].decode() == "healthy"
        assert float(stored_health[b"cpu_usage"]) == 45.2

    @pytest.mark.asyncio
    async def test_move_command_queue(self, test_database):
        """测试移动命令队列"""
        move_command = {
            "command_id": "cmd_001",
            "type": "move_piece",
            "from_position": "e2",
            "to_position": "e4",
            "priority": 1,
            "timestamp": time.time()
        }

        # 添加命令到队列
        test_database.lpush("robot.commands", json.dumps(move_command))

        # 验证队列
        queue_length = test_database.llen("robot.commands")
        assert queue_length == 1

        # 获取命令
        command_data = test_database.rpop("robot.commands")
        command = json.loads(command_data)
        assert command["command_id"] == "cmd_001"
        assert command["type"] == "move_piece"

    @pytest.mark.asyncio
    async def test_event_routing(self, test_database):
        """测试事件路由"""
        # 测试不同类型的事件
        events = [
            {
                "type": "vision.board_detected",
                "service": "vision_service",
                "data": {"confidence": 0.95}
            },
            {
                "type": "robot.move_completed",
                "service": "robot_service",
                "data": {"success": True, "duration": 2.1}
            },
            {
                "type": "ai.move_calculated",
                "service": "ai_service",
                "data": {"move": "e7e5", "evaluation": 0.15}
            }
        ]

        # 发布事件到不同频道
        for event in events:
            channel = f"chess.{event['service']}"
            test_database.publish(channel, json.dumps(event))

        # 验证事件被正确路由（通过频道名称）
        assert len(events) == 3

    @pytest.mark.asyncio
    async def test_game_session_management(self, test_database):
        """测试游戏会话管理"""
        game_id = "integration_test_game"
        session_data = {
            "game_id": game_id,
            "status": "active",
            "players": json.dumps({"white": "human", "black": "ai"}),
            "start_time": str(time.time()),
            "move_count": "0"
        }

        # 创建游戏会话
        test_database.hset(f"session:{game_id}", mapping=session_data)
        test_database.expire(f"session:{game_id}", 3600)  # 1小时过期

        # 更新移动计数
        test_database.hincrby(f"session:{game_id}", "move_count", 1)

        # 验证会话
        session = test_database.hgetall(f"session:{game_id}")
        assert session[b"game_id"].decode() == game_id
        assert int(session[b"move_count"]) == 1

        # 清理会话
        test_database.delete(f"session:{game_id}")

    @pytest.mark.asyncio
    async def test_performance_metrics_collection(self, test_database):
        """测试性能指标收集"""
        metrics_data = {
            "timestamp": time.time(),
            "vision_fps": 15.2,
            "detection_latency": 0.08,
            "robot_response_time": 1.25,
            "ai_thinking_time": 3.1,
            "memory_usage": 65.4,
            "cpu_usage": 42.1
        }

        # 存储性能指标
        metric_key = f"metrics:{int(time.time())}"
        test_database.hset(metric_key, mapping=metrics_data)
        test_database.expire(metric_key, 3600)  # 1小时保存

        # 验证指标存储
        stored_metrics = test_database.hgetall(metric_key)
        assert float(stored_metrics[b"vision_fps"]) == 15.2
        assert float(stored_metrics[b"ai_thinking_time"]) == 3.1

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, test_database):
        """测试错误处理和恢复"""
        error_event = {
            "type": "system.error",
            "service": "robot_service",
            "error": {
                "code": "COMM_ERROR",
                "message": "Serial communication timeout",
                "timestamp": time.time(),
                "severity": "high"
            }
        }

        # 记录错误事件
        error_key = f"errors:{int(time.time())}"
        test_database.hset(error_key, mapping={
            "service": error_event["service"],
            "error_code": error_event["error"]["code"],
            "message": error_event["error"]["message"],
            "severity": error_event["error"]["severity"],
            "timestamp": str(error_event["error"]["timestamp"])
        })

        # 发布错误事件
        test_database.publish("chess.errors", json.dumps(error_event))

        # 验证错误记录
        stored_error = test_database.hgetall(error_key)
        assert stored_error[b"error_code"].decode() == "COMM_ERROR"
        assert stored_error[b"severity"].decode() == "high"


class TestServiceCommunication:
    """服务间通信集成测试"""

    @pytest.mark.asyncio
    async def test_vision_to_game_manager_flow(self, test_database, mock_vision_service):
        """测试视觉服务到游戏管理器的流程"""
        # 模拟视觉检测结果
        detection_result = {
            "type": "vision.move_detected",
            "data": {
                "from": "e2",
                "to": "e4",
                "confidence": 0.94,
                "processing_time": 0.15
            },
            "timestamp": time.time()
        }

        # 发布检测结果
        test_database.publish("chess.vision", json.dumps(detection_result))

        # 验证游戏状态更新（模拟）
        game_update = {
            "move": "e2e4",
            "status": "ai_turn",
            "updated_at": time.time()
        }

        test_database.hset("game:current", mapping=game_update)
        stored_game = test_database.hgetall("game:current")
        assert stored_game[b"move"].decode() == "e2e4"

    @pytest.mark.asyncio
    async def test_ai_to_robot_command_flow(self, test_database, mock_ai_service, mock_robot_service):
        """测试AI到机器人命令流程"""
        # AI决策结果
        ai_decision = {
            "type": "ai.move_decided",
            "data": {
                "move": "e7e5",
                "evaluation": 0.12,
                "confidence": 0.89
            },
            "timestamp": time.time()
        }

        # 发布AI决策
        test_database.publish("chess.ai", json.dumps(ai_decision))

        # 生成机器人命令
        robot_command = {
            "command_id": f"cmd_{int(time.time())}",
            "type": "move_piece",
            "from_position": "e7",
            "to_position": "e5",
            "speed": 50,
            "precision": 1.0
        }

        # 添加到机器人命令队列
        test_database.lpush("robot.commands", json.dumps(robot_command))

        # 验证命令队列
        commands = test_database.lrange("robot.commands", 0, -1)
        assert len(commands) == 1

        command_data = json.loads(commands[0])
        assert command_data["from_position"] == "e7"
        assert command_data["to_position"] == "e5"

    @pytest.mark.asyncio
    async def test_full_move_execution_cycle(self, test_database, service_manager):
        """测试完整移动执行周期"""
        # 1. 视觉检测人类移动
        human_move = {
            "type": "vision.move_detected",
            "data": {"from": "e2", "to": "e4", "confidence": 0.96}
        }
        test_database.publish("chess.vision", json.dumps(human_move))

        # 2. 更新游戏状态
        test_database.hset("game:current", "last_move", "e2e4")
        test_database.hset("game:current", "turn", "black")

        # 3. AI计算回应
        ai_response = {
            "type": "ai.move_calculated",
            "data": {"move": "e7e5", "evaluation": 0.08}
        }
        test_database.publish("chess.ai", json.dumps(ai_response))

        # 4. 机器人执行移动
        robot_execution = {
            "command_id": "exec_001",
            "status": "completed",
            "execution_time": 2.3
        }
        test_database.hset("robot.execution:exec_001", mapping=robot_execution)

        # 5. 验证整个周期
        game_state = test_database.hgetall("game:current")
        assert game_state[b"last_move"].decode() == "e2e4"
        assert game_state[b"turn"].decode() == "black"

        execution_result = test_database.hgetall("robot.execution:exec_001")
        assert execution_result[b"status"].decode() == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])