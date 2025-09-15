"""
游戏协调器 - 协调各个服务的交互
"""
import asyncio
import uuid
import time
from typing import Dict, Optional, List, Any
from dataclasses import asdict

from shared.models.chess_models import (
    GameState, GameStatus, PieceColor, ChessBoard, ChessMove,
    RobotCommand, RobotStatus, VisionDetection, SystemMetrics, AIAnalysis
)
from shared.utils.redis_client import RedisEventBus, Event
from shared.utils.logger import get_logger
from shared.config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class GameCoordinator:
    """游戏协调器"""

    def __init__(self):
        self.event_bus: Optional[RedisEventBus] = None
        self.active_games: Dict[str, GameState] = {}
        self.robot_status: Optional[RobotStatus] = None
        self.system_metrics: Optional[SystemMetrics] = None
        self.ai_analysis_cache: Dict[str, AIAnalysis] = {}
        self.is_running = False

    async def initialize(self) -> bool:
        """初始化协调器"""
        try:
            logger.info("初始化游戏协调器")

            # 连接Redis事件总线
            self.event_bus = RedisEventBus()
            if not await self.event_bus.connect():
                logger.error("连接Redis失败")
                return False

            # 订阅事件
            await self._setup_event_subscriptions()

            self.is_running = True
            logger.info("游戏协调器初始化完成")
            return True

        except Exception as e:
            logger.error(f"初始化游戏协调器失败: {str(e)}")
            return False

    async def _setup_event_subscriptions(self):
        """设置事件订阅"""
        await self.event_bus.subscribe("chess_robot:move_made", self._handle_move_made)
        await self.event_bus.subscribe("chess_robot:ai_move_result", self._handle_ai_move_result)
        await self.event_bus.subscribe("chess_robot:robot_status_update", self._handle_robot_status)
        await self.event_bus.subscribe("chess_robot:vision_detection", self._handle_vision_detection)
        await self.event_bus.subscribe("chess_robot:system_metrics", self._handle_system_metrics)
        await self.event_bus.subscribe("chess_robot:game_over", self._handle_game_over)
        logger.info("游戏协调器事件订阅设置完成")

    async def create_game(self, human_color: str, ai_difficulty: int,
                         time_control: Optional[Dict[str, Any]] = None) -> str:
        """创建新游戏"""
        try:
            game_id = str(uuid.uuid4())

            # 创建游戏状态
            game_state = GameState(
                game_id=game_id,
                status=GameStatus.WAITING,
                board=ChessBoard(
                    pieces={},
                    timestamp=time.time(),
                    fen_string="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                    move_count=0
                ),
                current_player=PieceColor.WHITE,
                human_color=PieceColor(human_color),
                ai_color=PieceColor.BLACK if human_color == "white" else PieceColor.WHITE,
                move_history=[],
                start_time=time.time(),
                last_update=time.time(),
                ai_difficulty=ai_difficulty,
                time_control=time_control
            )

            self.active_games[game_id] = game_state
            logger.info(f"创建游戏: {game_id}, 人类:{human_color}, AI难度:{ai_difficulty}")

            return game_id

        except Exception as e:
            logger.error(f"创建游戏失败: {str(e)}")
            raise

    async def start_game(self, game_id: str) -> bool:
        """开始游戏"""
        try:
            if game_id not in self.active_games:
                return False

            game_state = self.active_games[game_id]
            game_state.status = GameStatus.PLAYING
            game_state.last_update = time.time()

            # 发布游戏开始事件
            await self._publish_game_event("game_started", game_id, {
                "ai_difficulty": game_state.ai_difficulty,
                "human_color": game_state.human_color.value,
                "ai_color": game_state.ai_color.value
            })

            logger.info(f"游戏开始: {game_id}")
            return True

        except Exception as e:
            logger.error(f"开始游戏失败: {str(e)}")
            return False

    async def make_move(self, game_id: str, move: str, player: str) -> bool:
        """执行移动"""
        try:
            if game_id not in self.active_games:
                return False

            game_state = self.active_games[game_id]

            # 创建移动对象
            chess_move = ChessMove(
                from_square=move[:2],
                to_square=move[2:4],
                piece=None,  # 将由视觉服务确定
                notation=move
            )

            # 添加到移动历史
            game_state.move_history.append(chess_move)
            game_state.last_update = time.time()

            # 切换当前玩家
            game_state.current_player = (
                PieceColor.BLACK if game_state.current_player == PieceColor.WHITE
                else PieceColor.WHITE
            )

            # 发布移动事件
            await self._publish_game_event("move_made", game_id, {
                "move": move,
                "player": player,
                "current_player": game_state.current_player.value
            })

            # 如果是人类移动且下一步是AI回合，请求AI移动
            if player == "human" and game_state.current_player == game_state.ai_color:
                await self._request_ai_move(game_id)

            logger.info(f"移动执行: {game_id}, {move}, 玩家:{player}")
            return True

        except Exception as e:
            logger.error(f"执行移动失败: {str(e)}")
            return False

    async def pause_game(self, game_id: str) -> bool:
        """暂停游戏"""
        try:
            if game_id not in self.active_games:
                return False

            game_state = self.active_games[game_id]
            game_state.status = GameStatus.PAUSED
            game_state.last_update = time.time()

            await self._publish_game_event("game_paused", game_id, {})
            logger.info(f"游戏暂停: {game_id}")
            return True

        except Exception as e:
            logger.error(f"暂停游戏失败: {str(e)}")
            return False

    async def end_game(self, game_id: str) -> bool:
        """结束游戏"""
        try:
            if game_id not in self.active_games:
                return False

            game_state = self.active_games[game_id]
            game_state.status = GameStatus.FINISHED
            game_state.last_update = time.time()

            await self._publish_game_event("game_ended", game_id, {})

            # 从活跃游戏中移除
            del self.active_games[game_id]

            logger.info(f"游戏结束: {game_id}")
            return True

        except Exception as e:
            logger.error(f"结束游戏失败: {str(e)}")
            return False

    async def get_game_state(self, game_id: str) -> Optional[GameState]:
        """获取游戏状态"""
        return self.active_games.get(game_id)

    async def set_ai_difficulty(self, game_id: str, difficulty: int) -> bool:
        """设置AI难度"""
        try:
            if game_id not in self.active_games:
                return False

            game_state = self.active_games[game_id]
            game_state.ai_difficulty = difficulty

            # 发布难度变更事件
            await self._publish_event("difficulty_changed", {
                "game_id": game_id,
                "difficulty": difficulty
            })

            logger.info(f"设置AI难度: {game_id}, 难度:{difficulty}")
            return True

        except Exception as e:
            logger.error(f"设置AI难度失败: {str(e)}")
            return False

    async def request_ai_analysis(self, analysis_type: str, position_fen: Optional[str] = None,
                                 moves: Optional[List[str]] = None, depth: Optional[int] = None) -> Dict[str, Any]:
        """请求AI分析"""
        try:
            # 发布分析请求事件
            await self._publish_event("analysis_request", {
                "type": analysis_type,
                "position_fen": position_fen,
                "moves": moves,
                "depth": depth
            })

            # 等待分析结果（简化实现，实际应该使用回调）
            await asyncio.sleep(2)

            # 返回模拟分析结果
            return {
                "analysis_type": analysis_type,
                "result": "分析完成",
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"AI分析失败: {str(e)}")
            raise

    async def send_robot_command(self, command: RobotCommand) -> bool:
        """发送机器人控制命令"""
        try:
            await self._publish_event("robot_command", asdict(command))
            logger.info(f"发送机器人命令: {command.command_type}")
            return True

        except Exception as e:
            logger.error(f"发送机器人命令失败: {str(e)}")
            return False

    async def emergency_stop_robot(self) -> bool:
        """机器人紧急停止"""
        try:
            await self._publish_event("emergency_stop", {})
            logger.info("机器人紧急停止")
            return True

        except Exception as e:
            logger.error(f"机器人紧急停止失败: {str(e)}")
            return False

    async def get_robot_status(self) -> Optional[RobotStatus]:
        """获取机器人状态"""
        return self.robot_status

    async def get_vision_status(self) -> Dict[str, Any]:
        """获取视觉系统状态"""
        return {
            "status": "running",
            "camera_connected": True,
            "detection_active": True,
            "last_detection": time.time()
        }

    async def calibrate_vision(self) -> bool:
        """标定视觉系统"""
        try:
            await self._publish_event("vision_calibrate", {})
            logger.info("视觉系统标定请求已发送")
            return True

        except Exception as e:
            logger.error(f"视觉标定失败: {str(e)}")
            return False

    async def get_system_metrics(self) -> Optional[SystemMetrics]:
        """获取系统指标"""
        return self.system_metrics

    async def get_system_logs(self, lines: int, service: Optional[str] = None) -> List[str]:
        """获取系统日志"""
        # 模拟日志返回
        return [
            f"[INFO] 服务运行正常 - {time.time()}",
            f"[INFO] 游戏协调器活跃游戏数: {len(self.active_games)}",
            f"[INFO] Redis连接状态: 正常"
        ][-lines:]

    async def _request_ai_move(self, game_id: str):
        """请求AI移动"""
        try:
            game_state = self.active_games[game_id]

            await self._publish_event("ai_move_request", {
                "game_id": game_id,
                "time_limit": 5.0,
                "difficulty": game_state.ai_difficulty
            })

        except Exception as e:
            logger.error(f"请求AI移动失败: {str(e)}")

    async def _handle_move_made(self, event_data: Dict[str, Any]):
        """处理移动执行事件"""
        try:
            logger.info(f"处理移动事件: {event_data}")
            # 更新游戏状态，通知客户端等
        except Exception as e:
            logger.error(f"处理移动事件失败: {str(e)}")

    async def _handle_ai_move_result(self, event_data: Dict[str, Any]):
        """处理AI移动结果"""
        try:
            payload = event_data.get("payload", {})
            game_id = payload.get("game_id")
            analysis = payload.get("analysis", {})

            if game_id and game_id in self.active_games:
                # 缓存AI分析结果
                self.ai_analysis_cache[game_id] = analysis
                logger.info(f"收到AI移动结果: {game_id}")

        except Exception as e:
            logger.error(f"处理AI移动结果失败: {str(e)}")

    async def _handle_robot_status(self, event_data: Dict[str, Any]):
        """处理机器人状态更新"""
        try:
            payload = event_data.get("payload", {})
            self.robot_status = RobotStatus(**payload)

        except Exception as e:
            logger.error(f"处理机器人状态失败: {str(e)}")

    async def _handle_vision_detection(self, event_data: Dict[str, Any]):
        """处理视觉检测结果"""
        try:
            logger.info(f"处理视觉检测: {event_data}")
            # 处理棋子移动检测结果
        except Exception as e:
            logger.error(f"处理视觉检测失败: {str(e)}")

    async def _handle_system_metrics(self, event_data: Dict[str, Any]):
        """处理系统指标更新"""
        try:
            payload = event_data.get("payload", {})
            self.system_metrics = SystemMetrics(**payload)

        except Exception as e:
            logger.error(f"处理系统指标失败: {str(e)}")

    async def _handle_game_over(self, event_data: Dict[str, Any]):
        """处理游戏结束事件"""
        try:
            payload = event_data.get("payload", {})
            game_id = payload.get("game_id")

            if game_id and game_id in self.active_games:
                game_state = self.active_games[game_id]
                game_state.status = GameStatus.FINISHED
                game_state.last_update = time.time()

                logger.info(f"游戏结束: {game_id}")

        except Exception as e:
            logger.error(f"处理游戏结束事件失败: {str(e)}")

    async def _publish_event(self, event_type: str, data: Dict[str, Any]):
        """发布事件"""
        if self.event_bus:
            event = Event(
                event_type=event_type,
                payload=data,
                source="web_gateway",
                timestamp=time.time()
            )
            await self.event_bus.publish(event)

    async def _publish_game_event(self, event_type: str, game_id: str, data: Dict[str, Any]):
        """发布游戏相关事件"""
        data["game_id"] = game_id
        await self._publish_event(event_type, data)

    async def shutdown(self):
        """关闭协调器"""
        logger.info("正在关闭游戏协调器")
        self.is_running = False

        try:
            if self.event_bus:
                await self.event_bus.disconnect()
            logger.info("游戏协调器已关闭")

        except Exception as e:
            logger.error(f"关闭协调器时出错: {str(e)}")