"""
游戏状态机定义
定义象棋游戏的所有状态和状态转换
"""
from enum import Enum
from typing import Dict, Set, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
import uuid


class GameStatus(Enum):
    """游戏状态枚举"""
    CREATED = "created"           # 游戏已创建
    WAITING = "waiting"           # 等待开始
    PLAYING = "playing"           # 游戏进行中
    PAUSED = "paused"             # 游戏暂停
    FINISHED = "finished"         # 游戏结束
    ERROR = "error"               # 游戏错误
    ABANDONED = "abandoned"       # 游戏被放弃


class Player(Enum):
    """玩家枚举"""
    HUMAN = "human"
    AI = "ai"
    WHITE = "white"
    BLACK = "black"


class GameEvent(Enum):
    """游戏事件枚举"""
    CREATE_GAME = "create_game"
    START_GAME = "start_game"
    MAKE_MOVE = "make_move"
    AI_MOVE = "ai_move"
    PAUSE_GAME = "pause_game"
    RESUME_GAME = "resume_game"
    END_GAME = "end_game"
    ABANDON_GAME = "abandon_game"
    GAME_ERROR = "game_error"
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    DRAW = "draw"
    TIMEOUT = "timeout"


@dataclass
class MoveInfo:
    """移动信息"""
    move: str
    player: Player
    timestamp: datetime
    fen: str
    san: str  # Standard Algebraic Notation
    uci: str  # Universal Chess Interface notation
    is_capture: bool = False
    is_check: bool = False
    is_checkmate: bool = False
    piece_moved: str = ""
    from_square: str = ""
    to_square: str = ""


@dataclass
class GameState:
    """游戏状态数据类"""
    game_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: GameStatus = GameStatus.CREATED
    current_player: Player = Player.WHITE
    human_player: Player = Player.WHITE
    ai_player: Player = Player.BLACK
    ai_difficulty: int = 3
    board_fen: str = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    move_history: list[MoveInfo] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    winner: Optional[Player] = None
    game_result: Optional[str] = None  # "checkmate", "stalemate", "draw", "timeout", "abandoned"
    error_message: Optional[str] = None
    is_thinking: bool = False
    last_move: Optional[MoveInfo] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "game_id": self.game_id,
            "status": self.status.value,
            "current_player": self.current_player.value,
            "human_player": self.human_player.value,
            "ai_player": self.ai_player.value,
            "ai_difficulty": self.ai_difficulty,
            "board_fen": self.board_fen,
            "move_history": [
                {
                    "move": move.move,
                    "player": move.player.value,
                    "timestamp": move.timestamp.isoformat(),
                    "fen": move.fen,
                    "san": move.san,
                    "uci": move.uci,
                    "is_capture": move.is_capture,
                    "is_check": move.is_check,
                    "is_checkmate": move.is_checkmate,
                    "piece_moved": move.piece_moved,
                    "from_square": move.from_square,
                    "to_square": move.to_square,
                }
                for move in self.move_history
            ],
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "winner": self.winner.value if self.winner else None,
            "game_result": self.game_result,
            "error_message": self.error_message,
            "is_thinking": self.is_thinking,
            "last_move": {
                "move": self.last_move.move,
                "player": self.last_move.player.value,
                "timestamp": self.last_move.timestamp.isoformat(),
                "fen": self.last_move.fen,
                "san": self.last_move.san,
                "uci": self.last_move.uci,
                "is_capture": self.last_move.is_capture,
                "is_check": self.last_move.is_check,
                "is_checkmate": self.last_move.is_checkmate,
                "piece_moved": self.last_move.piece_moved,
                "from_square": self.last_move.from_square,
                "to_square": self.last_move.to_square,
            } if self.last_move else None
        }


class GameStateMachine:
    """游戏状态机"""

    def __init__(self):
        """初始化状态机"""
        self.transitions: Dict[GameStatus, Dict[GameEvent, GameStatus]] = {
            GameStatus.CREATED: {
                GameEvent.START_GAME: GameStatus.WAITING,
                GameEvent.ABANDON_GAME: GameStatus.ABANDONED,
                GameEvent.GAME_ERROR: GameStatus.ERROR,
            },
            GameStatus.WAITING: {
                GameEvent.MAKE_MOVE: GameStatus.PLAYING,
                GameEvent.AI_MOVE: GameStatus.PLAYING,
                GameEvent.ABANDON_GAME: GameStatus.ABANDONED,
                GameEvent.GAME_ERROR: GameStatus.ERROR,
            },
            GameStatus.PLAYING: {
                GameEvent.MAKE_MOVE: GameStatus.PLAYING,
                GameEvent.AI_MOVE: GameStatus.PLAYING,
                GameEvent.PAUSE_GAME: GameStatus.PAUSED,
                GameEvent.END_GAME: GameStatus.FINISHED,
                GameEvent.CHECKMATE: GameStatus.FINISHED,
                GameEvent.STALEMATE: GameStatus.FINISHED,
                GameEvent.DRAW: GameStatus.FINISHED,
                GameEvent.TIMEOUT: GameStatus.FINISHED,
                GameEvent.ABANDON_GAME: GameStatus.ABANDONED,
                GameEvent.GAME_ERROR: GameStatus.ERROR,
            },
            GameStatus.PAUSED: {
                GameEvent.RESUME_GAME: GameStatus.PLAYING,
                GameEvent.END_GAME: GameStatus.FINISHED,
                GameEvent.ABANDON_GAME: GameStatus.ABANDONED,
                GameEvent.GAME_ERROR: GameStatus.ERROR,
            },
            GameStatus.FINISHED: {
                # 游戏结束后不能转换到其他状态
            },
            GameStatus.ERROR: {
                GameEvent.ABANDON_GAME: GameStatus.ABANDONED,
            },
            GameStatus.ABANDONED: {
                # 游戏被放弃后不能转换到其他状态
            }
        }

        # 状态处理回调函数
        self.state_handlers: Dict[GameStatus, Callable] = {}

        # 事件处理回调函数
        self.event_handlers: Dict[GameEvent, Callable] = {}

    def can_transition(self, current_status: GameStatus, event: GameEvent) -> bool:
        """检查是否可以进行状态转换"""
        return (current_status in self.transitions and
                event in self.transitions[current_status])

    def get_next_status(self, current_status: GameStatus, event: GameEvent) -> Optional[GameStatus]:
        """获取下一个状态"""
        if self.can_transition(current_status, event):
            return self.transitions[current_status][event]
        return None

    def get_valid_events(self, current_status: GameStatus) -> Set[GameEvent]:
        """获取当前状态下的有效事件"""
        if current_status in self.transitions:
            return set(self.transitions[current_status].keys())
        return set()

    def register_state_handler(self, status: GameStatus, handler: Callable):
        """注册状态处理器"""
        self.state_handlers[status] = handler

    def register_event_handler(self, event: GameEvent, handler: Callable):
        """注册事件处理器"""
        self.event_handlers[event] = handler

    def process_event(self, game_state: GameState, event: GameEvent, **kwargs) -> bool:
        """处理事件并更新游戏状态"""
        if not self.can_transition(game_state.status, event):
            return False

        # 获取下一个状态
        next_status = self.get_next_status(game_state.status, event)
        if next_status is None:
            return False

        # 执行事件处理器
        if event in self.event_handlers:
            try:
                self.event_handlers[event](game_state, **kwargs)
            except Exception as e:
                game_state.status = GameStatus.ERROR
                game_state.error_message = f"Event handler error: {str(e)}"
                return False

        # 更新状态
        old_status = game_state.status
        game_state.status = next_status

        # 执行状态处理器
        if next_status in self.state_handlers:
            try:
                self.state_handlers[next_status](game_state, old_status, **kwargs)
            except Exception as e:
                game_state.status = GameStatus.ERROR
                game_state.error_message = f"State handler error: {str(e)}"
                return False

        return True

    def is_game_active(self, status: GameStatus) -> bool:
        """检查游戏是否处于活跃状态"""
        return status in {GameStatus.WAITING, GameStatus.PLAYING, GameStatus.PAUSED}

    def is_game_finished(self, status: GameStatus) -> bool:
        """检查游戏是否已结束"""
        return status in {GameStatus.FINISHED, GameStatus.ABANDONED, GameStatus.ERROR}

    def get_status_description(self, status: GameStatus) -> str:
        """获取状态描述"""
        descriptions = {
            GameStatus.CREATED: "游戏已创建",
            GameStatus.WAITING: "等待开始",
            GameStatus.PLAYING: "游戏进行中",
            GameStatus.PAUSED: "游戏暂停",
            GameStatus.FINISHED: "游戏结束",
            GameStatus.ERROR: "游戏错误",
            GameStatus.ABANDONED: "游戏被放弃",
        }
        return descriptions.get(status, "未知状态")