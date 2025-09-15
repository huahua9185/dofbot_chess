"""
API数据模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class PieceColor(str, Enum):
    WHITE = "white"
    BLACK = "black"


class GameCreateRequest(BaseModel):
    """创建游戏请求"""
    human_color: PieceColor = Field(..., description="人类玩家颜色")
    ai_difficulty: int = Field(3, ge=1, le=10, description="AI难度等级(1-10)")
    time_control: Optional[Dict[str, Any]] = Field(None, description="时间控制设置")


class GameCreateResponse(BaseModel):
    """创建游戏响应"""
    game_id: str = Field(..., description="游戏ID")
    message: str = Field(..., description="响应消息")
    status: str = Field(..., description="游戏状态")


class MoveRequest(BaseModel):
    """移动请求"""
    move: str = Field(..., description="移动字符串(如e2e4)")
    player: str = Field(..., description="玩家类型(human/ai)")


class GameStatusResponse(BaseModel):
    """游戏状态响应"""
    game_id: str = Field(..., description="游戏ID")
    status: str = Field(..., description="游戏状态")
    current_player: str = Field(..., description="当前玩家")
    board_fen: str = Field(..., description="棋盘FEN字符串")
    move_count: int = Field(..., description="移动数量")
    last_move: Optional[str] = Field(None, description="最后一步移动")


class AIRequestModel(BaseModel):
    """AI分析请求"""
    analysis_type: str = Field(..., description="分析类型(position/suggestions/game)")
    position_fen: Optional[str] = Field(None, description="棋盘FEN字符串")
    moves: Optional[List[str]] = Field(None, description="移动序列")
    depth: Optional[int] = Field(8, description="分析深度")


class SystemStatusResponse(BaseModel):
    """系统状态响应"""
    cpu_usage: float = Field(..., description="CPU使用率(%)")
    memory_usage: float = Field(..., description="内存使用率(%)")
    disk_usage: float = Field(..., description="磁盘使用率(%)")
    gpu_usage: float = Field(..., description="GPU使用率(%)")
    temperature: float = Field(..., description="系统温度(°C)")
    services_status: Dict[str, str] = Field(..., description="服务状态")


class WebSocketMessage(BaseModel):
    """WebSocket消息模型"""
    type: str = Field(..., description="消息类型")
    data: Dict[str, Any] = Field(..., description="消息数据")
    timestamp: Optional[float] = Field(None, description="时间戳")


class RobotCommandRequest(BaseModel):
    """机器人命令请求"""
    command_type: str = Field(..., description="命令类型(move/pick/place/home/stop)")
    from_position: Optional[str] = Field(None, description="起始位置")
    to_position: Optional[str] = Field(None, description="目标位置")
    speed: int = Field(50, ge=1, le=100, description="移动速度(1-100)")
    precision: float = Field(1.0, description="精度要求(mm)")
    timeout: float = Field(30.0, description="超时时间(秒)")


class VisionCalibrationRequest(BaseModel):
    """视觉标定请求"""
    calibration_type: str = Field("full", description="标定类型(full/quick)")
    reference_points: Optional[List[Dict[str, float]]] = Field(None, description="参考点坐标")


class UserPreferences(BaseModel):
    """用户偏好设置"""
    theme: str = Field("light", description="界面主题(light/dark)")
    sound_enabled: bool = Field(True, description="是否启用声音")
    animation_speed: str = Field("normal", description="动画速度(slow/normal/fast)")
    show_hints: bool = Field(True, description="是否显示提示")
    auto_promotion: bool = Field(False, description="是否自动升变")


class GameHistory(BaseModel):
    """游戏历史"""
    game_id: str = Field(..., description="游戏ID")
    start_time: float = Field(..., description="开始时间")
    end_time: Optional[float] = Field(None, description="结束时间")
    result: Optional[str] = Field(None, description="游戏结果")
    moves: List[str] = Field(..., description="移动记录")
    ai_difficulty: int = Field(..., description="AI难度")
    human_color: str = Field(..., description="人类玩家颜色")


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误消息")
    details: Optional[Dict[str, Any]] = Field(None, description="错误详情")
    timestamp: float = Field(..., description="错误时间戳")