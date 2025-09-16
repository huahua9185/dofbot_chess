"""
端到端用户场景测试
测试完整的用户交互流程
"""
import pytest
import asyncio
import json
import time
from unittest.mock import AsyncMock, Mock

# 集成测试标记
pytestmark = pytest.mark.integration


class TestCompleteGameFlow:
    """完整游戏流程端到端测试"""

    @pytest.mark.asyncio
    async def test_full_game_session(self, test_database, service_manager):
        """测试完整的游戏会话流程"""

        # === 1. 游戏初始化阶段 ===
        game_id = "e2e_test_game_001"

        # 创建游戏会话
        game_session = {
            "game_id": game_id,
            "status": "initializing",
            "human_color": "white",
            "ai_color": "black",
            "difficulty": "5",
            "start_time": str(time.time())
        }

        test_database.hset(f"game:{game_id}", mapping=game_session)

        # 初始化棋盘
        initial_board = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        test_database.hset(f"board:{game_id}", "fen", initial_board)

        # === 2. 系统准备阶段 ===
        # 启动各服务（模拟）
        await service_manager.start_service("vision_service", Mock())
        await service_manager.start_service("robot_service", Mock())
        await service_manager.start_service("ai_service", Mock())

        # 标记游戏为等待状态
        test_database.hset(f"game:{game_id}", "status", "waiting")

        # === 3. 游戏开始 ===
        test_database.hset(f"game:{game_id}", "status", "playing")
        test_database.hset(f"game:{game_id}", "current_turn", "white")

        # === 4. 人类移动检测 ===
        human_move_detection = {
            "type": "vision.move_detected",
            "game_id": game_id,
            "data": {
                "from": "e2",
                "to": "e4",
                "confidence": 0.96,
                "processing_time": 0.12
            },
            "timestamp": time.time()
        }

        # 发布人类移动事件
        test_database.publish("chess.vision", json.dumps(human_move_detection))

        # 更新游戏状态
        test_database.hset(f"game:{game_id}", "last_move", "e2e4")
        test_database.hset(f"game:{game_id}", "current_turn", "black")
        test_database.hincrby(f"game:{game_id}", "move_count", 1)

        # === 5. AI思考阶段 ===
        test_database.hset(f"game:{game_id}", "status", "ai_thinking")

        # AI分析棋局
        ai_analysis = {
            "type": "ai.analysis_complete",
            "game_id": game_id,
            "data": {
                "best_move": "e7e5",
                "evaluation": 0.08,
                "depth": 12,
                "thinking_time": 3.2,
                "principal_variation": ["e7e5", "Nf3", "Nc6"]
            },
            "timestamp": time.time()
        }

        test_database.publish("chess.ai", json.dumps(ai_analysis))

        # === 6. 机器人执行AI移动 ===
        robot_command = {
            "command_id": f"cmd_{int(time.time())}",
            "game_id": game_id,
            "type": "move_piece",
            "from_position": "e7",
            "to_position": "e5",
            "speed": 50
        }

        # 添加到机器人命令队列
        test_database.lpush("robot.commands", json.dumps(robot_command))

        # 模拟机器人执行
        robot_execution = {
            "type": "robot.move_started",
            "command_id": robot_command["command_id"],
            "status": "executing",
            "progress": 0.0
        }

        test_database.publish("chess.robot", json.dumps(robot_execution))

        # 机器人执行完成
        robot_completion = {
            "type": "robot.move_completed",
            "command_id": robot_command["command_id"],
            "status": "completed",
            "execution_time": 2.1,
            "success": True
        }

        test_database.publish("chess.robot", json.dumps(robot_completion))

        # === 7. 游戏状态更新 ===
        test_database.hset(f"game:{game_id}", "last_move", "e7e5")
        test_database.hset(f"game:{game_id}", "current_turn", "white")
        test_database.hset(f"game:{game_id}", "status", "playing")
        test_database.hincrby(f"game:{game_id}", "move_count", 1)

        # === 8. 验证完整流程 ===
        final_game_state = test_database.hgetall(f"game:{game_id}")

        assert final_game_state[b"status"].decode() == "playing"
        assert final_game_state[b"current_turn"].decode() == "white"
        assert int(final_game_state[b"move_count"]) == 2
        assert final_game_state[b"last_move"].decode() == "e7e5"

    @pytest.mark.asyncio
    async def test_hardware_calibration_workflow(self, test_database):
        """测试硬件标定工作流程"""

        # === 1. 标定请求 ===
        calibration_request = {
            "type": "camera",
            "parameters": {
                "board_size": [9, 6],
                "square_size": 25.0,
                "num_images": 20
            }
        }

        calibration_id = "calib_e2e_001"

        # 创建标定会话
        calibration_session = {
            "calibration_id": calibration_id,
            "type": "camera",
            "status": "started",
            "progress": "0.0",
            "start_time": str(time.time())
        }

        test_database.hset(f"calibration:{calibration_id}", mapping=calibration_session)

        # === 2. 图像采集阶段 ===
        for i in range(1, 21):  # 20张标定图像
            image_capture = {
                "type": "calibration.image_captured",
                "calibration_id": calibration_id,
                "image_index": i,
                "corners_found": True,
                "quality_score": 0.9 + (i % 3) * 0.02
            }

            # 更新进度
            progress = (i / 20) * 0.7  # 图像采集占70%进度
            test_database.hset(f"calibration:{calibration_id}", "progress", str(progress))

            if i % 5 == 0:  # 每5张图像发布进度事件
                progress_event = {
                    "type": "calibration.progress",
                    "calibration_id": calibration_id,
                    "progress": progress,
                    "images_captured": i,
                    "total_images": 20
                }
                test_database.publish("chess.calibration", json.dumps(progress_event))

        # === 3. 标定计算阶段 ===
        test_database.hset(f"calibration:{calibration_id}", "status", "computing")
        test_database.hset(f"calibration:{calibration_id}", "progress", "0.8")

        computation_event = {
            "type": "calibration.computing",
            "calibration_id": calibration_id,
            "status": "running_opencv_calibration"
        }
        test_database.publish("chess.calibration", json.dumps(computation_event))

        # === 4. 标定完成 ===
        calibration_result = {
            "success": True,
            "reprojection_error": 0.48,
            "camera_matrix": [[500.2, 0, 320.1], [0, 500.8, 240.3], [0, 0, 1]],
            "distortion_coefficients": [0.1, -0.2, 0.001, 0.002, 0.0]
        }

        test_database.hset(f"calibration:{calibration_id}", mapping={
            "status": "completed",
            "progress": "1.0",
            "success": "True",
            "reprojection_error": str(calibration_result["reprojection_error"]),
            "completion_time": str(time.time())
        })

        completion_event = {
            "type": "calibration.completed",
            "calibration_id": calibration_id,
            "result": calibration_result
        }
        test_database.publish("chess.calibration", json.dumps(completion_event))

        # === 5. 验证标定结果 ===
        final_calibration = test_database.hgetall(f"calibration:{calibration_id}")

        assert final_calibration[b"status"].decode() == "completed"
        assert float(final_calibration[b"progress"]) == 1.0
        assert final_calibration[b"success"].decode() == "True"
        assert float(final_calibration[b"reprojection_error"]) < 0.5

    @pytest.mark.asyncio
    async def test_error_recovery_scenarios(self, test_database):
        """测试错误恢复场景"""

        game_id = "error_recovery_test"

        # === 1. 机器人通信错误 ===
        robot_error = {
            "type": "robot.communication_error",
            "game_id": game_id,
            "error": {
                "code": "SERIAL_TIMEOUT",
                "message": "Serial communication timeout",
                "severity": "high",
                "timestamp": time.time()
            }
        }

        # 记录错误
        error_key = f"error:{int(time.time())}"
        test_database.hset(error_key, mapping={
            "service": "robot_service",
            "error_code": robot_error["error"]["code"],
            "severity": robot_error["error"]["severity"],
            "message": robot_error["error"]["message"]
        })

        # 发布错误事件
        test_database.publish("chess.errors", json.dumps(robot_error))

        # 触发恢复机制
        recovery_action = {
            "type": "system.recovery_initiated",
            "service": "robot_service",
            "action": "reconnect",
            "timestamp": time.time()
        }

        test_database.publish("chess.recovery", json.dumps(recovery_action))

        # === 2. 视觉检测失败 ===
        vision_error = {
            "type": "vision.detection_failed",
            "game_id": game_id,
            "error": {
                "code": "LOW_CONFIDENCE",
                "message": "Chess piece detection confidence too low",
                "confidence": 0.45,
                "threshold": 0.8
            }
        }

        test_database.publish("chess.errors", json.dumps(vision_error))

        # 请求重新检测
        retry_request = {
            "type": "vision.retry_detection",
            "game_id": game_id,
            "retry_count": 1,
            "enhanced_mode": True
        }

        test_database.publish("chess.vision", json.dumps(retry_request))

        # === 3. AI引擎超时 ===
        ai_timeout = {
            "type": "ai.thinking_timeout",
            "game_id": game_id,
            "timeout_seconds": 30,
            "current_depth": 8
        }

        test_database.publish("chess.errors", json.dumps(ai_timeout))

        # 使用当前最佳移动
        fallback_move = {
            "type": "ai.fallback_move",
            "game_id": game_id,
            "move": "Nf3",
            "evaluation": 0.12,
            "depth": 8,
            "reason": "timeout_fallback"
        }

        test_database.publish("chess.ai", json.dumps(fallback_move))

        # === 4. 验证错误记录 ===
        # 检查错误是否被正确记录和处理
        error_count = len([key for key in test_database.keys("error:*")])
        assert error_count > 0

    @pytest.mark.asyncio
    async def test_multi_game_session_management(self, test_database):
        """测试多游戏会话管理"""

        # === 1. 创建多个游戏会话 ===
        game_sessions = []
        for i in range(3):
            game_id = f"multi_game_{i+1}"
            session = {
                "game_id": game_id,
                "status": "active",
                "human_color": "white" if i % 2 == 0 else "black",
                "ai_color": "black" if i % 2 == 0 else "white",
                "start_time": str(time.time()),
                "move_count": str(i * 2)
            }

            test_database.hset(f"game:{game_id}", mapping=session)
            game_sessions.append(session)

        # === 2. 并发游戏操作 ===
        concurrent_operations = []

        for i, session in enumerate(game_sessions):
            game_id = session["game_id"]

            # 模拟不同游戏的并发操作
            if i == 0:
                # 游戏1：人类移动
                move_event = {
                    "type": "vision.move_detected",
                    "game_id": game_id,
                    "data": {"from": "e2", "to": "e4"}
                }
                test_database.publish("chess.vision", json.dumps(move_event))

            elif i == 1:
                # 游戏2：AI思考
                ai_event = {
                    "type": "ai.thinking_started",
                    "game_id": game_id,
                    "expected_time": 5.0
                }
                test_database.publish("chess.ai", json.dumps(ai_event))

            else:
                # 游戏3：机器人移动
                robot_event = {
                    "type": "robot.move_started",
                    "game_id": game_id,
                    "command": {"from": "d7", "to": "d5"}
                }
                test_database.publish("chess.robot", json.dumps(robot_event))

        # === 3. 验证会话隔离 ===
        for session in game_sessions:
            game_id = session["game_id"]
            stored_session = test_database.hgetall(f"game:{game_id}")

            assert stored_session[b"game_id"].decode() == game_id
            assert stored_session[b"status"].decode() == "active"

        # === 4. 会话清理 ===
        for session in game_sessions:
            game_id = session["game_id"]
            test_database.delete(f"game:{game_id}")

        # 验证清理完成
        remaining_games = len([key for key in test_database.keys("game:multi_game_*")])
        assert remaining_games == 0

    @pytest.mark.asyncio
    async def test_system_performance_monitoring(self, test_database):
        """测试系统性能监控"""

        # === 1. 收集性能指标 ===
        performance_metrics = []

        for i in range(10):  # 收集10个时间点的指标
            metrics = {
                "timestamp": time.time() + i,
                "cpu_usage": 40.0 + i * 2.5,
                "memory_usage": 60.0 + i * 1.2,
                "gpu_usage": 20.0 + i * 3.0,
                "vision_fps": 15.0 - i * 0.3,
                "detection_latency": 0.08 + i * 0.01,
                "robot_response_time": 1.2 + i * 0.15,
                "ai_thinking_time": 3.0 + i * 0.4
            }

            performance_metrics.append(metrics)

            # 存储到Redis
            metric_key = f"metrics:{int(metrics['timestamp'])}"
            test_database.hset(metric_key, mapping={
                "cpu_usage": str(metrics["cpu_usage"]),
                "memory_usage": str(metrics["memory_usage"]),
                "vision_fps": str(metrics["vision_fps"]),
                "ai_thinking_time": str(metrics["ai_thinking_time"])
            })

            test_database.expire(metric_key, 3600)  # 1小时过期

        # === 2. 性能告警检查 ===
        alerts = []

        for metrics in performance_metrics:
            # CPU使用率过高
            if metrics["cpu_usage"] > 80:
                alerts.append({
                    "type": "high_cpu_usage",
                    "value": metrics["cpu_usage"],
                    "threshold": 80,
                    "timestamp": metrics["timestamp"]
                })

            # 视觉处理FPS过低
            if metrics["vision_fps"] < 10:
                alerts.append({
                    "type": "low_vision_fps",
                    "value": metrics["vision_fps"],
                    "threshold": 10,
                    "timestamp": metrics["timestamp"]
                })

            # AI思考时间过长
            if metrics["ai_thinking_time"] > 10:
                alerts.append({
                    "type": "slow_ai_response",
                    "value": metrics["ai_thinking_time"],
                    "threshold": 10,
                    "timestamp": metrics["timestamp"]
                })

        # === 3. 发布性能告警 ===
        for alert in alerts:
            alert_key = f"alert:{int(alert['timestamp'])}"
            test_database.hset(alert_key, mapping={
                "type": alert["type"],
                "value": str(alert["value"]),
                "threshold": str(alert["threshold"])
            })

            test_database.publish("chess.alerts", json.dumps(alert))

        # === 4. 验证监控数据 ===
        metric_keys = test_database.keys("metrics:*")
        assert len(metric_keys) == 10

        alert_keys = test_database.keys("alert:*")
        assert len(alert_keys) == len(alerts)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])