"""
AI引擎服务主程序
"""
import asyncio
import json
from typing import Optional, Dict, Any, List
from dataclasses import asdict
import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from shared.models.chess_models import AIAnalysis, GameState, ChessMove
from shared.utils.redis_client import RedisEventBus, Event
from shared.utils.logger import get_logger
from shared.config.settings import get_settings
from ai.engine import StockfishEngine

settings = get_settings()
logger = get_logger(__name__)


class AIService:
    """AI引擎服务"""

    def __init__(self):
        self.service_name = "ai_service"
        self.engine = StockfishEngine()
        self.event_bus: Optional[RedisEventBus] = None
        self.is_running = False
        self.current_game_id: Optional[str] = None
        self.analysis_queue = asyncio.Queue()

    async def initialize(self) -> bool:
        """初始化服务"""
        try:
            logger.info(f"初始化{self.service_name}")

            # 连接Redis事件总线
            self.event_bus = RedisEventBus()
            if not await self.event_bus.connect():
                logger.error("连接Redis失败")
                return False

            # 初始化AI引擎
            if not await self.engine.initialize():
                logger.error("初始化AI引擎失败")
                return False

            # 订阅事件
            await self._setup_event_subscriptions()

            logger.info("AI服务初始化完成")
            return True

        except Exception as e:
            logger.error(f"初始化失败: {str(e)}")
            return False

    async def _setup_event_subscriptions(self):
        """设置事件订阅"""
        self.event_bus.subscribe("chess_robot:game_started", self._handle_game_started)
        self.event_bus.subscribe("chess_robot:move_made", self._handle_move_made)
        self.event_bus.subscribe("chess_robot:ai_move_request", self._handle_ai_move_request)
        self.event_bus.subscribe("chess_robot:game_state_changed", self._handle_game_state_change)
        self.event_bus.subscribe("chess_robot:difficulty_changed", self._handle_difficulty_change)
        self.event_bus.subscribe("chess_robot:analysis_request", self._handle_analysis_request)
        logger.info("AI服务事件订阅设置完成")

    async def _handle_game_started(self, event_data: Dict[str, Any]):
        """处理游戏开始事件"""
        try:
            logger.info(f"游戏开始: {event_data}")

            game_data = event_data.get("payload", {})
            self.current_game_id = game_data.get("game_id")

            # 重置引擎状态
            self.engine.current_board = self.engine.current_board.__class__()  # 重置为初始状态

            # 设置难度
            difficulty = game_data.get("ai_difficulty", self.engine.default_difficulty)
            self.engine.set_difficulty(difficulty)

            logger.info(f"AI准备就绪 - 游戏ID:{self.current_game_id}, 难度:{difficulty}")

        except Exception as e:
            logger.error(f"处理游戏开始失败: {str(e)}")

    async def _handle_move_made(self, event_data: Dict[str, Any]):
        """处理移动执行事件"""
        try:
            logger.info(f"收到移动: {event_data}")

            move_data = event_data.get("payload", {})
            move_uci = move_data.get("move")
            player = move_data.get("player")

            if move_uci and self.engine.is_move_legal(move_uci):
                # 在引擎中执行移动
                self.engine.make_move(move_uci)
                logger.info(f"{player}移动已更新: {move_uci}")

                # 检查游戏是否结束
                await self._check_game_over()

            else:
                logger.warning(f"无效移动: {move_uci}")

        except Exception as e:
            logger.error(f"处理移动失败: {str(e)}")

    async def _handle_ai_move_request(self, event_data: Dict[str, Any]):
        """处理AI移动请求"""
        try:
            logger.info("收到AI移动请求")

            request_data = event_data.get("payload", {})
            time_limit = request_data.get("time_limit")

            # 加入分析队列
            await self.analysis_queue.put({
                "type": "move_request",
                "time_limit": time_limit,
                "game_id": self.current_game_id
            })

        except Exception as e:
            logger.error(f"处理AI移动请求失败: {str(e)}")

    async def _handle_game_state_change(self, event_data: Dict[str, Any]):
        """处理游戏状态变化"""
        try:
            logger.info(f"游戏状态变化: {event_data}")

            state_data = event_data.get("payload", {})
            status = state_data.get("status")

            if status == "finished":
                logger.info(f"游戏结束: {self.current_game_id}")
                self.current_game_id = None

        except Exception as e:
            logger.error(f"处理游戏状态变化失败: {str(e)}")

    async def _handle_difficulty_change(self, event_data: Dict[str, Any]):
        """处理难度变化"""
        try:
            difficulty_data = event_data.get("payload", {})
            new_difficulty = difficulty_data.get("difficulty", self.engine.default_difficulty)

            self.engine.set_difficulty(new_difficulty)
            logger.info(f"AI难度已调整为: {new_difficulty}")

            # 发布难度变更确认
            await self._publish_difficulty_changed(new_difficulty)

        except Exception as e:
            logger.error(f"处理难度变化失败: {str(e)}")

    async def _handle_analysis_request(self, event_data: Dict[str, Any]):
        """处理分析请求"""
        try:
            analysis_data = event_data.get("payload", {})
            analysis_type = analysis_data.get("type", "position")

            # 加入分析队列
            await self.analysis_queue.put({
                "type": "analysis_request",
                "analysis_type": analysis_type,
                "data": analysis_data
            })

        except Exception as e:
            logger.error(f"处理分析请求失败: {str(e)}")

    async def _process_ai_move_request(self, request_data: Dict[str, Any]):
        """处理AI移动请求"""
        try:
            time_limit = request_data.get("time_limit")

            logger.info(f"AI开始思考...")

            # 获取最佳移动
            analysis = await self.engine.get_best_move(time_limit)

            if analysis:
                # 在引擎中执行移动
                self.engine.make_move(analysis.best_move)

                # 发布AI移动结果
                await self._publish_ai_move(analysis)

                # 检查游戏是否结束
                await self._check_game_over()

                logger.info(f"AI移动完成: {analysis.best_move}")
            else:
                logger.error("AI未能找到有效移动")
                await self._publish_ai_error("无法找到有效移动")

        except Exception as e:
            logger.error(f"处理AI移动失败: {str(e)}")
            await self._publish_ai_error(str(e))

    async def _process_analysis_request(self, request_data: Dict[str, Any]):
        """处理分析请求"""
        try:
            analysis_type = request_data.get("analysis_type")
            data = request_data.get("data", {})

            if analysis_type == "position":
                # 位置分析
                evaluation = await self.engine.evaluate_position()
                legal_moves = self.engine.get_legal_moves()

                result = {
                    "type": "position_analysis",
                    "evaluation": evaluation,
                    "legal_moves_count": len(legal_moves),
                    "fen": self.engine.get_board_fen()
                }

            elif analysis_type == "suggestions":
                # 移动建议
                count = data.get("count", 3)
                suggestions = await self.engine.suggest_moves(count)

                result = {
                    "type": "move_suggestions",
                    "suggestions": suggestions
                }

            elif analysis_type == "game":
                # 整局分析
                moves = data.get("moves", [])
                game_analysis = await self.engine.analyze_game(moves)

                result = {
                    "type": "game_analysis",
                    "analysis": game_analysis
                }

            else:
                result = {"type": "error", "message": f"未知的分析类型: {analysis_type}"}

            # 发布分析结果
            await self._publish_analysis_result(result)

        except Exception as e:
            logger.error(f"处理分析请求失败: {str(e)}")
            await self._publish_analysis_result({
                "type": "error",
                "message": str(e)
            })

    async def _check_game_over(self):
        """检查游戏是否结束"""
        try:
            is_over, result = await self.engine.is_game_over()

            if is_over:
                await self._publish_game_over(result)

        except Exception as e:
            logger.error(f"检查游戏结束状态失败: {str(e)}")

    async def _publish_ai_move(self, analysis: AIAnalysis):
        """发布AI移动结果"""
        try:
            event = Event(
                event_type="ai_move_result",
                payload={
                    "game_id": self.current_game_id,
                    "analysis": asdict(analysis),
                    "fen": self.engine.get_board_fen()
                },
                source=self.service_name,
                timestamp=asyncio.get_event_loop().time()
            )
            await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"发布AI移动失败: {str(e)}")

    async def _publish_ai_error(self, error_message: str):
        """发布AI错误"""
        try:
            event = Event(
                event_type="ai_error",
                payload={
                    "game_id": self.current_game_id,
                    "error": error_message
                },
                source=self.service_name,
                timestamp=asyncio.get_event_loop().time()
            )
            await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"发布AI错误失败: {str(e)}")

    async def _publish_game_over(self, result: str):
        """发布游戏结束事件"""
        try:
            event = Event(
                event_type="game_over",
                payload={
                    "game_id": self.current_game_id,
                    "result": result,
                    "final_fen": self.engine.get_board_fen(),
                    "move_count": len(self.engine.current_board.move_stack)
                },
                source=self.service_name,
                timestamp=asyncio.get_event_loop().time()
            )
            await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"发布游戏结束失败: {str(e)}")

    async def _publish_difficulty_changed(self, difficulty: int):
        """发布难度变更确认"""
        try:
            event = Event(
                event_type="ai_difficulty_changed",
                payload={
                    "difficulty": difficulty,
                    "config": self.engine.difficulty_configs[difficulty]
                },
                source=self.service_name,
                timestamp=asyncio.get_event_loop().time()
            )
            await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"发布难度变更失败: {str(e)}")

    async def _publish_analysis_result(self, result: Dict[str, Any]):
        """发布分析结果"""
        try:
            event = Event(
                event_type="ai_analysis_result",
                payload=result,
                source=self.service_name,
                timestamp=asyncio.get_event_loop().time()
            )
            await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"发布分析结果失败: {str(e)}")

    async def _analysis_processor(self):
        """分析处理协程"""
        while self.is_running:
            try:
                # 等待分析请求
                request = await asyncio.wait_for(
                    self.analysis_queue.get(),
                    timeout=1.0
                )

                if request["type"] == "move_request":
                    await self._process_ai_move_request(request)
                elif request["type"] == "analysis_request":
                    await self._process_analysis_request(request)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"分析处理器错误: {str(e)}")

    async def _status_reporter(self):
        """状态报告协程"""
        while self.is_running:
            try:
                # 发布AI引擎状态
                await self._publish_engine_status()
                await asyncio.sleep(10.0)  # 每10秒发送一次状态
            except Exception as e:
                logger.error(f"状态报告器错误: {str(e)}")

    async def _publish_engine_status(self):
        """发布引擎状态"""
        try:
            engine_info = self.engine.get_engine_info()

            event = Event(
                event_type="ai_status_update",
                payload=engine_info,
                source=self.service_name,
                timestamp=asyncio.get_event_loop().time()
            )
            await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"发布引擎状态失败: {str(e)}")

    async def run(self):
        """运行服务"""
        self.is_running = True
        logger.info("AI服务开始运行")

        try:
            # 启动所有协程
            tasks = [
                asyncio.create_task(self._analysis_processor()),
                asyncio.create_task(self._status_reporter()),
                asyncio.create_task(self.event_bus.start_listening())
            ]

            # 等待任务完成
            await asyncio.gather(*tasks)

        except KeyboardInterrupt:
            logger.info("收到停止信号")
        except Exception as e:
            logger.error(f"服务运行错误: {str(e)}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """关闭服务"""
        logger.info("正在关闭AI服务")
        self.is_running = False

        try:
            # 关闭AI引擎
            await self.engine.shutdown()

            # 断开Redis连接
            if self.event_bus:
                await self.event_bus.disconnect()

            logger.info("AI服务已关闭")

        except Exception as e:
            logger.error(f"关闭服务时出错: {str(e)}")


async def main():
    """主函数"""
    service = AIService()

    if not await service.initialize():
        logger.error("服务初始化失败")
        return

    await service.run()


if __name__ == "__main__":
    asyncio.run(main())