"""
象棋游戏相关的数据模型
"""
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
import time


class PieceType(Enum):
    """棋子类型"""
    # 白方棋子
    WHITE_KING = "white_king"
    WHITE_QUEEN = "white_queen"
    WHITE_ROOK = "white_rook"
    WHITE_BISHOP = "white_bishop"
    WHITE_KNIGHT = "white_knight"
    WHITE_PAWN = "white_pawn"

    # 黑方棋子
    BLACK_KING = "black_king"
    BLACK_QUEEN = "black_queen"
    BLACK_ROOK = "black_rook"
    BLACK_BISHOP = "black_bishop"
    BLACK_KNIGHT = "black_knight"
    BLACK_PAWN = "black_pawn"

    # 空位
    EMPTY = "empty"


class PieceColor(Enum):
    """棋子颜色"""
    WHITE = "white"
    BLACK = "black"


class GameStatus(Enum):
    """游戏状态"""
    WAITING = "waiting"          # 等待开始
    PLAYING = "playing"          # 游戏中
    HUMAN_TURN = "human_turn"    # 人类回合
    AI_TURN = "ai_turn"          # AI回合
    PAUSED = "paused"            # 暂停
    FINISHED = "finished"        # 游戏结束
    ERROR = "error"              # 错误状态


@dataclass
class Position3D:
    """3D位置坐标"""
    x: float
    y: float
    z: float


@dataclass
class Position6D:
    """6D位姿（位置+姿态）"""
    x: float
    y: float
    z: float
    rx: float  # 绕X轴旋转
    ry: float  # 绕Y轴旋转
    rz: float  # 绕Z轴旋转


@dataclass
class ChessPiece:
    """棋子信息"""
    piece_type: PieceType
    position: str  # 棋盘坐标，如"e4"
    color: PieceColor
    confidence: float = 1.0  # 识别置信度
    physical_pos: Optional[Position3D] = None  # 物理3D坐标


@dataclass
class ChessBoard:
    """棋盘状态"""
    pieces: Dict[str, ChessPiece]  # 位置到棋子的映射
    timestamp: float
    fen_string: str  # FEN格式的棋盘状态
    move_count: int = 0


@dataclass
class ChessMove:
    """象棋移动"""
    from_square: str  # 起始位置
    to_square: str    # 目标位置
    piece: PieceType
    captured_piece: Optional[PieceType] = None
    promotion: Optional[PieceType] = None
    is_castling: bool = False
    is_en_passant: bool = False
    notation: str = ""  # 代数记谱法


@dataclass
class AIAnalysis:
    """AI分析结果"""
    best_move: str
    evaluation: float  # 局面评估分数
    depth: int        # 搜索深度
    nodes: int        # 搜索节点数
    thinking_time: float  # 思考时间
    principal_variation: List[str]  # 主变着法
    confidence: float = 1.0


@dataclass
class GameState:
    """游戏状态"""
    game_id: str
    status: GameStatus
    board: ChessBoard
    current_player: PieceColor
    human_color: PieceColor
    ai_color: PieceColor
    move_history: List[ChessMove]
    start_time: float
    last_update: float
    ai_difficulty: int = 3  # 1-10难度级别
    time_control: Optional[Dict[str, Any]] = None  # 时间控制


@dataclass
class VisionDetection:
    """视觉检测结果"""
    board_state: ChessBoard
    detected_move: Optional[ChessMove]
    detection_confidence: float
    processing_time: float
    image_timestamp: float
    camera_id: str = "main"


@dataclass
class RobotCommand:
    """机器人控制命令"""
    command_type: str  # "move", "pick", "place", "home", "stop"
    from_position: Optional[str] = None  # 起始位置
    to_position: Optional[str] = None    # 目标位置
    speed: int = 50  # 移动速度 1-100
    precision: float = 1.0  # 精度要求 mm
    timeout: float = 30.0   # 超时时间


@dataclass
class RobotStatus:
    """机器人状态"""
    is_connected: bool
    is_moving: bool
    current_position: Position6D
    joint_angles: List[float]
    gripper_state: bool  # True=夹紧, False=松开
    error_message: Optional[str] = None
    last_update: float = 0.0

    def __post_init__(self):
        if self.last_update == 0.0:
            self.last_update = time.time()


@dataclass
class SystemMetrics:
    """系统性能指标"""
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    gpu_usage: float = 0.0
    temperature: float = 0.0
    vision_fps: float = 0.0
    detection_latency: float = 0.0
    robot_response_time: float = 0.0
    ai_thinking_time: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


# 工具函数
def square_to_coords(square: str) -> Tuple[int, int]:
    """将棋盘坐标转换为数组索引"""
    if len(square) != 2:
        raise ValueError(f"Invalid square: {square}")

    col = ord(square[0].lower()) - ord('a')  # a-h => 0-7
    row = int(square[1]) - 1                 # 1-8 => 0-7

    if not (0 <= col <= 7) or not (0 <= row <= 7):
        raise ValueError(f"Invalid square: {square}")

    return col, row


def coords_to_square(col: int, row: int) -> str:
    """将数组索引转换为棋盘坐标"""
    if not (0 <= col <= 7) or not (0 <= row <= 7):
        raise ValueError(f"Invalid coordinates: ({col}, {row})")

    return chr(ord('a') + col) + str(row + 1)


def get_piece_color(piece_type: PieceType) -> Optional[PieceColor]:
    """获取棋子颜色"""
    if piece_type == PieceType.EMPTY:
        return None
    return PieceColor.WHITE if "white" in piece_type.value else PieceColor.BLACK


def is_valid_square(square: str) -> bool:
    """检查是否为有效的棋盘坐标"""
    try:
        square_to_coords(square)
        return True
    except ValueError:
        return False