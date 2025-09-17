"""
游戏管理器核心模块
协调各个微服务，管理游戏生命周期
"""
import asyncio
import logging
from typing import Dict, Optional, Callable, Any
from datetime import datetime
import chess
import chess.engine

from shared.event_bus import EventBus
from shared.models import Event, ServiceStatus
from game_state import (
    GameState, GameStateMachine, GameStatus, GameEvent,
    Player, MoveInfo
)


logger = logging.getLogger(__name__)


class GameManager:
    """游戏管理器类"""

    def __init__(self, event_bus: EventBus):
        """初始化游戏管理器"""
        self.event_bus = event_bus
        self.state_machine = GameStateMachine()
        self.active_games: Dict[str, GameState] = {}
        self.running = False

        # 服务状态
        self.services_status = {
            "vision": ServiceStatus.STOPPED,
            "robot": ServiceStatus.STOPPED,
            "ai_engine": ServiceStatus.STOPPED,
            "web_gateway": ServiceStatus.STOPPED,
        }

        # 注册状态和事件处理器
        self._setup_handlers()

        # 棋盘引擎
        self.chess_board = chess.Board()

    def _setup_handlers(self):
        """设置状态机处理器"""

        # 状态处理器
        self.state_machine.register_state_handler(
            GameStatus.WAITING, self._handle_waiting_state
        )
        self.state_machine.register_state_handler(
            GameStatus.PLAYING, self._handle_playing_state
        )
        self.state_machine.register_state_handler(
            GameStatus.PAUSED, self._handle_paused_state
        )
        self.state_machine.register_state_handler(
            GameStatus.FINISHED, self._handle_finished_state
        )
        self.state_machine.register_state_handler(
            GameStatus.ERROR, self._handle_error_state
        )

        # 事件处理器
        self.state_machine.register_event_handler(
            GameEvent.CREATE_GAME, self._handle_create_game
        )
        self.state_machine.register_event_handler(
            GameEvent.START_GAME, self._handle_start_game
        )
        self.state_machine.register_event_handler(
            GameEvent.MAKE_MOVE, self._handle_make_move
        )
        self.state_machine.register_event_handler(
            GameEvent.AI_MOVE, self._handle_ai_move
        )
        self.state_machine.register_event_handler(
            GameEvent.PAUSE_GAME, self._handle_pause_game
        )
        self.state_machine.register_event_handler(
            GameEvent.RESUME_GAME, self._handle_resume_game
        )
        self.state_machine.register_event_handler(
            GameEvent.END_GAME, self._handle_end_game
        )

    async def start(self):
        """启动游戏管理器"""
        logger.info("Starting Game Manager...")
        self.running = True

        # 订阅事件
        await self._subscribe_events()

        # 启动主循环
        asyncio.create_task(self._main_loop())

        logger.info("Game Manager started successfully")

    async def stop(self):
        """停止游戏管理器"""
        logger.info("Stopping Game Manager...")
        self.running = False

    async def _subscribe_events(self):
        """订阅事件总线事件"""

        # 订阅各服务的状态更新
        await self.event_bus.subscribe("service.vision.status", self._on_service_status)
        await self.event_bus.subscribe("service.robot.status", self._on_service_status)
        await self.event_bus.subscribe("service.ai_engine.status", self._on_service_status)
        await self.event_bus.subscribe("service.web_gateway.status", self._on_service_status)

        # 订阅游戏相关事件
        await self.event_bus.subscribe("game.create", self._on_game_create)
        await self.event_bus.subscribe("game.start", self._on_game_start)
        await self.event_bus.subscribe("game.move", self._on_game_move)
        await self.event_bus.subscribe("game.pause", self._on_game_pause)
        await self.event_bus.subscribe("game.resume", self._on_game_resume)
        await self.event_bus.subscribe("game.end", self._on_game_end)
        await self.event_bus.subscribe("game.abandon", self._on_game_abandon)

        # 订阅AI引擎响应
        await self.event_bus.subscribe("ai.move_result", self._on_ai_move_result)
        await self.event_bus.subscribe("ai.analysis_result", self._on_ai_analysis_result)

        # 订阅视觉系统检测结果
        await self.event_bus.subscribe("vision.board_detected", self._on_board_detected)
        await self.event_bus.subscribe("vision.move_detected", self._on_move_detected)

        # 订阅机器人动作完成
        await self.event_bus.subscribe("robot.move_completed", self._on_robot_move_completed)
        await self.event_bus.subscribe("robot.error", self._on_robot_error)

    async def _main_loop(self):
        """主循环，处理定期任务"""
        while self.running:
            try:
                # 检查超时的游戏
                await self._check_game_timeouts()

                # 清理已完成的游戏
                await self._cleanup_finished_games()

                # 监控服务状态
                await self._monitor_services()

                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(5)

    async def create_game(self, human_color: str, ai_difficulty: int) -> str:
        """创建新游戏"""
        game_state = GameState(
            human_player=Player.WHITE if human_color == "white" else Player.BLACK,
            ai_player=Player.BLACK if human_color == "white" else Player.WHITE,
            ai_difficulty=ai_difficulty
        )

        # 处理创建游戏事件
        success = self.state_machine.process_event(
            game_state, GameEvent.CREATE_GAME,
            human_color=human_color, ai_difficulty=ai_difficulty
        )

        if success:
            self.active_games[game_state.game_id] = game_state

            # 发布游戏创建事件
            await self.event_bus.publish("game.created", Event(
                type="game.created",
                payload={
                    "game_id": game_state.game_id,
                    "game_state": game_state.to_dict()
                }
            ))

            logger.info(f"Game created: {game_state.game_id}")
            return game_state.game_id
        else:
            raise RuntimeError("Failed to create game")

    async def start_game(self, game_id: str) -> bool:
        """开始游戏"""
        if game_id not in self.active_games:
            return False

        game_state = self.active_games[game_id]
        success = self.state_machine.process_event(game_state, GameEvent.START_GAME)

        if success:
            await self.event_bus.publish("game.started", Event(
                type="game.started",
                payload={
                    "game_id": game_id,
                    "game_state": game_state.to_dict()
                }
            ))

            # 如果AI先手，触发AI移动
            if game_state.current_player == game_state.ai_player:
                await self._request_ai_move(game_id)

            logger.info(f"Game started: {game_id}")

        return success

    async def make_move(self, game_id: str, move: str, player: Player) -> bool:
        """执行移动"""
        if game_id not in self.active_games:
            return False

        game_state = self.active_games[game_id]

        # 验证移动是否合法
        if not self._validate_move(game_state, move, player):
            return False

        success = self.state_machine.process_event(
            game_state, GameEvent.MAKE_MOVE,
            move=move, player=player
        )

        return success

    async def pause_game(self, game_id: str) -> bool:
        """暂停游戏"""
        if game_id not in self.active_games:
            return False

        game_state = self.active_games[game_id]
        return self.state_machine.process_event(game_state, GameEvent.PAUSE_GAME)

    async def resume_game(self, game_id: str) -> bool:
        """恢复游戏"""
        if game_id not in self.active_games:
            return False

        game_state = self.active_games[game_id]
        return self.state_machine.process_event(game_state, GameEvent.RESUME_GAME)

    async def end_game(self, game_id: str, reason: str = "manual") -> bool:
        """结束游戏"""
        if game_id not in self.active_games:
            return False

        game_state = self.active_games[game_id]
        return self.state_machine.process_event(
            game_state, GameEvent.END_GAME, reason=reason
        )

    async def get_game_state(self, game_id: str) -> Optional[Dict[str, Any]]:
        """获取游戏状态"""
        if game_id in self.active_games:
            return self.active_games[game_id].to_dict()
        return None

    async def list_games(self) -> Dict[str, Dict[str, Any]]:
        """列出所有游戏"""
        return {
            game_id: game_state.to_dict()
            for game_id, game_state in self.active_games.items()
        }

    # ==================== 状态处理器 ====================

    async def _handle_waiting_state(self, game_state: GameState, old_status: GameStatus, **kwargs):
        """处理等待状态"""
        game_state.started_at = datetime.now()
        logger.info(f"Game {game_state.game_id} is waiting to start")

    async def _handle_playing_state(self, game_state: GameState, old_status: GameStatus, **kwargs):
        """处理游戏进行状态"""
        logger.info(f"Game {game_state.game_id} is now playing")

    async def _handle_paused_state(self, game_state: GameState, old_status: GameStatus, **kwargs):
        """处理暂停状态"""
        logger.info(f"Game {game_state.game_id} is paused")

    async def _handle_finished_state(self, game_state: GameState, old_status: GameStatus, **kwargs):
        """处理完成状态"""
        game_state.finished_at = datetime.now()
        reason = kwargs.get("reason", "unknown")
        game_state.game_result = reason

        logger.info(f"Game {game_state.game_id} finished: {reason}")

        # 发布游戏完成事件
        await self.event_bus.publish("game.finished", Event(
            type="game.finished",
            payload={
                "game_id": game_state.game_id,
                "result": reason,
                "winner": game_state.winner.value if game_state.winner else None,
                "game_state": game_state.to_dict()
            }
        ))

    async def _handle_error_state(self, game_state: GameState, old_status: GameStatus, **kwargs):
        """处理错误状态"""
        logger.error(f"Game {game_state.game_id} encountered error: {game_state.error_message}")

    # ==================== 事件处理器 ====================

    async def _handle_create_game(self, game_state: GameState, **kwargs):
        """处理创建游戏事件"""
        logger.info(f"Creating game {game_state.game_id}")

    async def _handle_start_game(self, game_state: GameState, **kwargs):
        """处理开始游戏事件"""
        game_state.started_at = datetime.now()

    async def _handle_make_move(self, game_state: GameState, **kwargs):
        """处理移动事件"""
        move = kwargs.get("move")
        player = kwargs.get("player")

        # 创建移动信息
        move_info = await self._create_move_info(game_state, move, player)
        game_state.move_history.append(move_info)
        game_state.last_move = move_info

        # 更新棋盘状态
        self._update_board_state(game_state, move)

        # 切换玩家
        game_state.current_player = (
            game_state.ai_player if player == game_state.human_player
            else game_state.human_player
        )

        # 检查游戏是否结束
        await self._check_game_end_conditions(game_state)

        # 发布移动事件
        await self.event_bus.publish("game.move_made", Event(
            type="game.move_made",
            payload={
                "game_id": game_state.game_id,
                "move": move_info.__dict__,
                "game_state": game_state.to_dict()
            }
        ))

        # 如果轮到AI，请求AI移动
        if (game_state.status == GameStatus.PLAYING and
            game_state.current_player == game_state.ai_player):
            await self._request_ai_move(game_state.game_id)

    async def _handle_ai_move(self, game_state: GameState, **kwargs):
        """处理AI移动事件"""
        await self._handle_make_move(game_state, **kwargs)

    async def _handle_pause_game(self, game_state: GameState, **kwargs):
        """处理暂停游戏事件"""
        pass

    async def _handle_resume_game(self, game_state: GameState, **kwargs):
        """处理恢复游戏事件"""
        # 如果轮到AI且游戏恢复，触发AI移动
        if game_state.current_player == game_state.ai_player:
            await self._request_ai_move(game_state.game_id)

    async def _handle_end_game(self, game_state: GameState, **kwargs):
        """处理结束游戏事件"""
        reason = kwargs.get("reason", "manual")
        game_state.game_result = reason

    # ==================== 事件总线回调 ====================

    async def _on_service_status(self, event: Event):
        """处理服务状态更新"""
        service_name = event.payload.get("service")
        status = event.payload.get("status")

        if service_name in self.services_status:
            self.services_status[service_name] = ServiceStatus(status)
            logger.info(f"Service {service_name} status: {status}")

    async def _on_game_create(self, event: Event):
        """处理游戏创建请求"""
        payload = event.payload
        try:
            game_id = await self.create_game(
                payload.get("human_color", "white"),
                payload.get("ai_difficulty", 3)
            )
            # 返回结果通过事件总线
            await self.event_bus.publish("game.create_result", Event(
                type="game.create_result",
                payload={"success": True, "game_id": game_id}
            ))
        except Exception as e:
            await self.event_bus.publish("game.create_result", Event(
                type="game.create_result",
                payload={"success": False, "error": str(e)}
            ))

    async def _on_game_start(self, event: Event):
        """处理游戏开始请求"""
        game_id = event.payload.get("game_id")
        success = await self.start_game(game_id)

        await self.event_bus.publish("game.start_result", Event(
            type="game.start_result",
            payload={"success": success, "game_id": game_id}
        ))

    async def _on_game_move(self, event: Event):
        """处理移动请求"""
        payload = event.payload
        game_id = payload.get("game_id")
        move = payload.get("move")
        player = Player(payload.get("player", "human"))

        success = await self.make_move(game_id, move, player)

        await self.event_bus.publish("game.move_result", Event(
            type="game.move_result",
            payload={"success": success, "game_id": game_id, "move": move}
        ))

    async def _on_game_pause(self, event: Event):
        """处理暂停请求"""
        game_id = event.payload.get("game_id")
        success = await self.pause_game(game_id)

        await self.event_bus.publish("game.pause_result", Event(
            type="game.pause_result",
            payload={"success": success, "game_id": game_id}
        ))

    async def _on_game_resume(self, event: Event):
        """处理恢复请求"""
        game_id = event.payload.get("game_id")
        success = await self.resume_game(game_id)

        await self.event_bus.publish("game.resume_result", Event(
            type="game.resume_result",
            payload={"success": success, "game_id": game_id}
        ))

    async def _on_game_end(self, event: Event):
        """处理结束游戏请求"""
        payload = event.payload
        game_id = payload.get("game_id")
        reason = payload.get("reason", "manual")

        success = await self.end_game(game_id, reason)

        await self.event_bus.publish("game.end_result", Event(
            type="game.end_result",
            payload={"success": success, "game_id": game_id, "reason": reason}
        ))

    async def _on_game_abandon(self, event: Event):
        """处理放弃游戏请求"""
        game_id = event.payload.get("game_id")
        if game_id in self.active_games:
            game_state = self.active_games[game_id]
            self.state_machine.process_event(game_state, GameEvent.ABANDON_GAME)

    async def _on_ai_move_result(self, event: Event):
        """处理AI移动结果"""
        payload = event.payload
        game_id = payload.get("game_id")
        move = payload.get("best_move")

        if game_id in self.active_games and move:
            await self.make_move(game_id, move, Player.AI)

    async def _on_ai_analysis_result(self, event: Event):
        """处理AI分析结果"""
        # 可以用于显示AI的思考过程
        pass

    async def _on_board_detected(self, event: Event):
        """处理棋盘检测结果"""
        payload = event.payload
        game_id = payload.get("game_id")
        board_fen = payload.get("board_fen")

        if game_id in self.active_games:
            game_state = self.active_games[game_id]
            if board_fen != game_state.board_fen:
                # 棋盘状态发生变化，可能是玩家移动了棋子
                logger.info(f"Board state changed in game {game_id}")

    async def _on_move_detected(self, event: Event):
        """处理移动检测结果"""
        payload = event.payload
        game_id = payload.get("game_id")
        move = payload.get("move")

        if game_id in self.active_games:
            # 处理检测到的移动
            await self.make_move(game_id, move, Player.HUMAN)

    async def _on_robot_move_completed(self, event: Event):
        """处理机器人移动完成"""
        payload = event.payload
        game_id = payload.get("game_id")
        move = payload.get("move")

        logger.info(f"Robot completed move {move} in game {game_id}")

    async def _on_robot_error(self, event: Event):
        """处理机器人错误"""
        payload = event.payload
        game_id = payload.get("game_id")
        error = payload.get("error")

        if game_id in self.active_games:
            game_state = self.active_games[game_id]
            game_state.error_message = f"Robot error: {error}"
            self.state_machine.process_event(game_state, GameEvent.GAME_ERROR)

    # ==================== 辅助方法 ====================

    async def _request_ai_move(self, game_id: str):
        """请求AI移动"""
        if game_id not in self.active_games:
            return

        game_state = self.active_games[game_id]
        game_state.is_thinking = True

        # 发布AI移动请求
        await self.event_bus.publish("ai.move_request", Event(
            type="ai.move_request",
            payload={
                "game_id": game_id,
                "board_fen": game_state.board_fen,
                "difficulty": game_state.ai_difficulty,
                "time_limit": 30  # 秒
            }
        ))

    def _validate_move(self, game_state: GameState, move: str, player: Player) -> bool:
        """验证移动是否合法"""
        # 检查是否轮到该玩家
        if player != game_state.current_player:
            return False

        # 使用python-chess验证移动
        try:
            board = chess.Board(game_state.board_fen)
            chess_move = chess.Move.from_uci(move)
            return chess_move in board.legal_moves
        except:
            return False

    async def _create_move_info(self, game_state: GameState, move: str, player: Player) -> MoveInfo:
        """创建移动信息"""
        board = chess.Board(game_state.board_fen)
        chess_move = chess.Move.from_uci(move)

        # 执行移动以获取详细信息
        board.push(chess_move)

        return MoveInfo(
            move=move,
            player=player,
            timestamp=datetime.now(),
            fen=board.fen(),
            san=board.san(chess_move),
            uci=move,
            is_capture=board.is_capture(chess_move),
            is_check=board.is_check(),
            is_checkmate=board.is_checkmate(),
            piece_moved=str(board.piece_at(chess_move.from_square)),
            from_square=chess.square_name(chess_move.from_square),
            to_square=chess.square_name(chess_move.to_square)
        )

    def _update_board_state(self, game_state: GameState, move: str):
        """更新棋盘状态"""
        board = chess.Board(game_state.board_fen)
        chess_move = chess.Move.from_uci(move)
        board.push(chess_move)
        game_state.board_fen = board.fen()

    async def _check_game_end_conditions(self, game_state: GameState):
        """检查游戏结束条件"""
        board = chess.Board(game_state.board_fen)

        if board.is_checkmate():
            game_state.winner = (
                game_state.human_player if game_state.current_player == game_state.ai_player
                else game_state.ai_player
            )
            self.state_machine.process_event(game_state, GameEvent.CHECKMATE)
        elif board.is_stalemate():
            self.state_machine.process_event(game_state, GameEvent.STALEMATE)
        elif board.is_insufficient_material() or board.is_seventyfive_moves() or board.is_fivefold_repetition():
            self.state_machine.process_event(game_state, GameEvent.DRAW)

    async def _check_game_timeouts(self):
        """检查游戏超时"""
        current_time = datetime.now()
        timeout_games = []

        for game_id, game_state in self.active_games.items():
            if (game_state.status == GameStatus.PLAYING and
                game_state.last_move and
                (current_time - game_state.last_move.timestamp).total_seconds() > 300):  # 5分钟超时
                timeout_games.append(game_id)

        for game_id in timeout_games:
            await self.end_game(game_id, "timeout")

    async def _cleanup_finished_games(self):
        """清理已完成的游戏"""
        current_time = datetime.now()
        games_to_remove = []

        for game_id, game_state in self.active_games.items():
            if (self.state_machine.is_game_finished(game_state.status) and
                game_state.finished_at and
                (current_time - game_state.finished_at).total_seconds() > 3600):  # 1小时后清理
                games_to_remove.append(game_id)

        for game_id in games_to_remove:
            del self.active_games[game_id]
            logger.info(f"Cleaned up finished game: {game_id}")

    async def _monitor_services(self):
        """监控服务状态"""
        # 检查关键服务是否在线
        offline_services = [
            service for service, status in self.services_status.items()
            if status != ServiceStatus.RUNNING
        ]

        if offline_services:
            logger.warning(f"Offline services: {offline_services}")

            # 如果有游戏正在进行且关键服务离线，暂停游戏
            for game_state in self.active_games.values():
                if (game_state.status == GameStatus.PLAYING and
                    ("ai_engine" in offline_services or "robot" in offline_services)):
                    self.state_machine.process_event(game_state, GameEvent.PAUSE_GAME)