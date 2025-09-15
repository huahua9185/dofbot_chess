"""
数据库模型定义
定义MongoDB和Redis中存储的数据结构
"""

from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Union
from enum import Enum
from pydantic import BaseModel, Field
from bson import ObjectId


class PyObjectId(ObjectId):
    """自定义ObjectId类型，用于Pydantic模型"""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


class GameStatus(str, Enum):
    """游戏状态枚举"""
    WAITING = "waiting"
    PLAYING = "playing"
    PAUSED = "paused"
    FINISHED = "finished"
    ABORTED = "aborted"


class PlayerColor(str, Enum):
    """玩家颜色枚举"""
    WHITE = "white"
    BLACK = "black"


class GameResult(str, Enum):
    """游戏结果枚举"""
    WHITE_WINS = "white_wins"
    BLACK_WINS = "black_wins"
    DRAW = "draw"
    ABORTED = "aborted"
    ONGOING = "ongoing"


class CalibrationStatus(str, Enum):
    """标定状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class CalibrationType(str, Enum):
    """标定类型枚举"""
    CAMERA_INTRINSIC = "camera_intrinsic"
    CAMERA_EXTRINSIC = "camera_extrinsic"
    ROBOT_WORKSPACE = "robot_workspace"
    PIECE_RECOGNITION = "piece_recognition"


class LogLevel(str, Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# 用户相关模型
class UserModel(BaseModel):
    """用户数据模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password_hash: str
    display_name: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False

    # 游戏统计
    games_played: int = 0
    games_won: int = 0
    games_drawn: int = 0
    current_rating: int = 1200

    # 时间戳
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class UserSession(BaseModel):
    """用户会话模型（存储在Redis中）"""
    user_id: str
    session_token: str
    username: str
    display_name: Optional[str] = None
    is_admin: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


# 游戏相关模型
class GameModel(BaseModel):
    """游戏数据模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    game_id: str = Field(..., unique=True)

    # 玩家信息
    player_id: Optional[str] = None
    player_color: PlayerColor = PlayerColor.WHITE
    ai_difficulty: int = Field(default=3, ge=1, le=10)

    # 游戏状态
    status: GameStatus = GameStatus.WAITING
    result: GameResult = GameResult.ONGOING
    current_player: PlayerColor = PlayerColor.WHITE
    move_count: int = 0

    # 棋盘状态
    board_fen: str = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    last_move: Optional[str] = None

    # 时间控制
    time_per_player: int = 1800  # 30分钟
    time_remaining_white: int = 1800
    time_remaining_black: int = 1800

    # 时间戳
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class GameState(BaseModel):
    """游戏状态模型（存储在Redis中，用于实时更新）"""
    game_id: str
    status: GameStatus
    current_player: PlayerColor
    board_fen: str
    last_move: Optional[str] = None
    move_count: int = 0
    check: bool = False
    checkmate: bool = False
    stalemate: bool = False
    draw: bool = False
    time_remaining_white: int
    time_remaining_black: int
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MoveModel(BaseModel):
    """移动记录模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    game_id: str
    move_number: int

    # 移动信息
    move_notation: str  # 标准代数记号法
    move_uci: str  # UCI格式
    from_square: str
    to_square: str
    piece: str
    captured_piece: Optional[str] = None
    promotion: Optional[str] = None

    # 棋盘状态
    board_fen_before: str
    board_fen_after: str

    # 移动分析
    is_check: bool = False
    is_checkmate: bool = False
    is_stalemate: bool = False
    is_capture: bool = False
    is_castling: bool = False
    is_en_passant: bool = False

    # 执行信息
    player: PlayerColor
    move_time: float  # 思考时间（秒）
    evaluation: Optional[float] = None  # 局面评估值

    # 时间戳
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# 标定相关模型
class CalibrationDataModel(BaseModel):
    """标定数据模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    calibration_type: CalibrationType
    status: CalibrationStatus = CalibrationStatus.PENDING

    # 标定参数
    parameters: Dict[str, Any] = Field(default_factory=dict)
    accuracy_metrics: Dict[str, float] = Field(default_factory=dict)

    # 标定图像/数据路径
    data_paths: List[str] = Field(default_factory=list)

    # 状态标记
    is_active: bool = False
    version: int = 1

    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # 时间戳
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# 相机内参标定数据
class CameraIntrinsicParams(BaseModel):
    """相机内参标定参数"""
    camera_matrix: List[List[float]]  # 3x3相机矩阵
    distortion_coefficients: List[float]  # 畸变系数
    image_size: List[int]  # [width, height]
    reprojection_error: float
    calibration_flags: int


# 相机外参标定数据
class CameraExtrinsicParams(BaseModel):
    """相机外参标定参数"""
    rotation_matrix: List[List[float]]  # 3x3旋转矩阵
    translation_vector: List[float]  # 3x1平移向量
    homography_matrix: List[List[float]]  # 3x3单应性矩阵
    reprojection_error: float
    reference_points: List[Dict[str, float]]  # 参考点坐标


# 机器人工作空间标定数据
class RobotWorkspaceParams(BaseModel):
    """机器人工作空间标定参数"""
    workspace_bounds: Dict[str, List[float]]  # 工作空间边界
    joint_limits: Dict[str, List[float]]  # 关节限位
    coordinate_transform: List[List[float]]  # 坐标变换矩阵
    accuracy_test_points: List[Dict[str, float]]  # 精度测试点
    positioning_accuracy: float  # 定位精度


# 系统日志模型
class SystemLogModel(BaseModel):
    """系统日志模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")

    # 日志基本信息
    service: str
    level: LogLevel
    message: str

    # 详细信息
    module: Optional[str] = None
    function: Optional[str] = None
    line_number: Optional[int] = None

    # 上下文信息
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    game_id: Optional[str] = None

    # 异常信息
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    stack_trace: Optional[str] = None

    # 性能信息
    duration: Optional[float] = None  # 执行时间（秒）
    memory_usage: Optional[float] = None  # 内存使用量（MB）
    cpu_usage: Optional[float] = None  # CPU使用率

    # 时间戳
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# 性能指标模型
class PerformanceMetricModel(BaseModel):
    """性能指标模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")

    # 指标基本信息
    service: str
    metric_type: str  # cpu, memory, disk, network, response_time, etc.
    metric_name: str

    # 指标值
    value: float
    unit: str

    # 标签和维度
    labels: Dict[str, str] = Field(default_factory=dict)

    # 时间戳
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# AI分析结果模型
class AIAnalysisModel(BaseModel):
    """AI分析结果模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    game_id: str
    move_number: int
    analysis_type: str  # position_evaluation, best_move, opening_book, endgame

    # 分析结果
    evaluation: Optional[float] = None  # 局面评估值
    best_move: Optional[str] = None  # 最佳着法
    principal_variation: List[str] = Field(default_factory=list)  # 主要变化

    # 候选着法
    candidate_moves: List[Dict[str, Any]] = Field(default_factory=list)

    # 分析深度和时间
    search_depth: int = 0
    search_time: float = 0.0  # 搜索时间（秒）
    nodes_searched: int = 0

    # 开局信息
    opening_name: Optional[str] = None
    opening_eco: Optional[str] = None  # ECO编码

    # 时间戳
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# 系统配置模型
class SystemConfigModel(BaseModel):
    """系统配置模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    config_key: str = Field(..., unique=True)
    config_value: Any
    description: Optional[str] = None
    category: str = "general"
    is_encrypted: bool = False

    # 时间戳
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


# Redis缓存键命名规范
class CacheKeys:
    """Redis缓存键命名规范"""

    # 游戏相关
    GAME_STATE = "game:state:{game_id}"
    GAME_MOVES = "game:moves:{game_id}"
    PLAYER_GAMES = "player:games:{player_id}"

    # 用户相关
    USER_SESSION = "user:session:{session_token}"
    USER_PROFILE = "user:profile:{user_id}"
    USER_ONLINE = "user:online"

    # 标定数据
    CALIBRATION_DATA = "calibration:{calibration_type}"
    CALIBRATION_STATUS = "calibration:status:{calibration_type}"

    # 系统状态
    SYSTEM_STATUS = "system:status"
    SERVICE_STATUS = "service:status:{service_name}"

    # 性能指标
    METRICS = "metrics:{service}:{metric_type}"

    # 实时通信
    GAME_CHANNEL = "game:channel:{game_id}"
    SYSTEM_EVENTS = "system:events"

    @staticmethod
    def format_key(template: str, **kwargs) -> str:
        """格式化缓存键"""
        return template.format(**kwargs)