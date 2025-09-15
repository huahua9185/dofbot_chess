"""
系统事件类型定义
定义系统中所有事件类型和频道模式
"""
from enum import Enum
from typing import Dict, List


class EventType(Enum):
    """事件类型枚举"""

    # 系统事件
    SERVICE_STARTED = "service.started"
    SERVICE_STOPPED = "service.stopped"
    SERVICE_ERROR = "service.error"
    SERVICE_HEALTH_CHECK = "service.health_check"

    # 游戏管理事件
    GAME_CREATED = "game.created"
    GAME_STARTED = "game.started"
    GAME_PAUSED = "game.paused"
    GAME_RESUMED = "game.resumed"
    GAME_FINISHED = "game.finished"
    GAME_ABANDONED = "game.abandoned"
    GAME_ERROR = "game.error"

    # 游戏移动事件
    MOVE_REQUESTED = "game.move.requested"
    MOVE_VALIDATED = "game.move.validated"
    MOVE_EXECUTED = "game.move.executed"
    MOVE_COMPLETED = "game.move.completed"
    MOVE_FAILED = "game.move.failed"

    # AI引擎事件
    AI_MOVE_REQUEST = "ai.move.request"
    AI_MOVE_RESULT = "ai.move.result"
    AI_ANALYSIS_REQUEST = "ai.analysis.request"
    AI_ANALYSIS_RESULT = "ai.analysis.result"
    AI_ENGINE_READY = "ai.engine.ready"
    AI_ENGINE_BUSY = "ai.engine.busy"
    AI_ENGINE_ERROR = "ai.engine.error"

    # 视觉系统事件
    VISION_BOARD_DETECTED = "vision.board.detected"
    VISION_MOVE_DETECTED = "vision.move.detected"
    VISION_PIECE_DETECTED = "vision.piece.detected"
    VISION_CALIBRATION_STARTED = "vision.calibration.started"
    VISION_CALIBRATION_COMPLETED = "vision.calibration.completed"
    VISION_ERROR = "vision.error"

    # 机器人控制事件
    ROBOT_MOVE_COMMAND = "robot.move.command"
    ROBOT_MOVE_STARTED = "robot.move.started"
    ROBOT_MOVE_COMPLETED = "robot.move.completed"
    ROBOT_MOVE_FAILED = "robot.move.failed"
    ROBOT_CALIBRATION_STARTED = "robot.calibration.started"
    ROBOT_CALIBRATION_COMPLETED = "robot.calibration.completed"
    ROBOT_ERROR = "robot.error"
    ROBOT_STATUS_CHANGED = "robot.status.changed"

    # Web网关事件
    WEB_CLIENT_CONNECTED = "web.client.connected"
    WEB_CLIENT_DISCONNECTED = "web.client.disconnected"
    WEB_MESSAGE_RECEIVED = "web.message.received"
    WEB_MESSAGE_SENT = "web.message.sent"

    # 硬件标定事件
    CALIBRATION_STEP_STARTED = "calibration.step.started"
    CALIBRATION_STEP_COMPLETED = "calibration.step.completed"
    CALIBRATION_STEP_FAILED = "calibration.step.failed"
    CALIBRATION_COMPLETED = "calibration.completed"
    CALIBRATION_FAILED = "calibration.failed"

    # 监控和指标事件
    METRICS_UPDATED = "metrics.updated"
    ALERT_TRIGGERED = "alert.triggered"
    HEALTH_CHECK_FAILED = "health.check.failed"


class ChannelPattern:
    """频道模式定义"""

    # 服务频道
    SERVICE_STATUS = "service.*.status"
    SERVICE_EVENTS = "service.*.events"
    SERVICE_METRICS = "service.*.metrics"
    SERVICE_LOGS = "service.*.logs"

    # 游戏频道
    GAME_EVENTS = "game.*"
    GAME_MOVES = "game.*.moves"
    GAME_STATUS = "game.*.status"

    # AI频道
    AI_REQUESTS = "ai.requests"
    AI_RESPONSES = "ai.responses"
    AI_ANALYSIS = "ai.analysis"

    # 视觉频道
    VISION_DETECTION = "vision.detection"
    VISION_ANALYSIS = "vision.analysis"
    VISION_CALIBRATION = "vision.calibration"

    # 机器人频道
    ROBOT_COMMANDS = "robot.commands"
    ROBOT_STATUS = "robot.status"
    ROBOT_MOVES = "robot.moves"

    # Web频道
    WEB_CLIENTS = "web.clients.*"
    WEB_BROADCASTS = "web.broadcasts"

    # 系统频道
    SYSTEM_ALERTS = "system.alerts"
    SYSTEM_METRICS = "system.metrics"
    SYSTEM_HEALTH = "system.health"


class EventPriority(Enum):
    """事件优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class EventCategory(Enum):
    """事件分类"""
    SYSTEM = "system"
    GAME = "game"
    HARDWARE = "hardware"
    NETWORK = "network"
    USER = "user"
    ERROR = "error"


# 事件类型映射
EVENT_CATEGORY_MAPPING = {
    # 系统事件
    EventType.SERVICE_STARTED: EventCategory.SYSTEM,
    EventType.SERVICE_STOPPED: EventCategory.SYSTEM,
    EventType.SERVICE_ERROR: EventCategory.ERROR,
    EventType.SERVICE_HEALTH_CHECK: EventCategory.SYSTEM,

    # 游戏事件
    EventType.GAME_CREATED: EventCategory.GAME,
    EventType.GAME_STARTED: EventCategory.GAME,
    EventType.GAME_PAUSED: EventCategory.GAME,
    EventType.GAME_RESUMED: EventCategory.GAME,
    EventType.GAME_FINISHED: EventCategory.GAME,
    EventType.GAME_ABANDONED: EventCategory.GAME,
    EventType.GAME_ERROR: EventCategory.ERROR,

    # 移动事件
    EventType.MOVE_REQUESTED: EventCategory.GAME,
    EventType.MOVE_VALIDATED: EventCategory.GAME,
    EventType.MOVE_EXECUTED: EventCategory.GAME,
    EventType.MOVE_COMPLETED: EventCategory.GAME,
    EventType.MOVE_FAILED: EventCategory.ERROR,

    # AI事件
    EventType.AI_MOVE_REQUEST: EventCategory.SYSTEM,
    EventType.AI_MOVE_RESULT: EventCategory.SYSTEM,
    EventType.AI_ANALYSIS_REQUEST: EventCategory.SYSTEM,
    EventType.AI_ANALYSIS_RESULT: EventCategory.SYSTEM,
    EventType.AI_ENGINE_READY: EventCategory.SYSTEM,
    EventType.AI_ENGINE_BUSY: EventCategory.SYSTEM,
    EventType.AI_ENGINE_ERROR: EventCategory.ERROR,

    # 硬件事件
    EventType.VISION_BOARD_DETECTED: EventCategory.HARDWARE,
    EventType.VISION_MOVE_DETECTED: EventCategory.HARDWARE,
    EventType.VISION_PIECE_DETECTED: EventCategory.HARDWARE,
    EventType.VISION_CALIBRATION_STARTED: EventCategory.HARDWARE,
    EventType.VISION_CALIBRATION_COMPLETED: EventCategory.HARDWARE,
    EventType.VISION_ERROR: EventCategory.ERROR,

    EventType.ROBOT_MOVE_COMMAND: EventCategory.HARDWARE,
    EventType.ROBOT_MOVE_STARTED: EventCategory.HARDWARE,
    EventType.ROBOT_MOVE_COMPLETED: EventCategory.HARDWARE,
    EventType.ROBOT_MOVE_FAILED: EventCategory.ERROR,
    EventType.ROBOT_CALIBRATION_STARTED: EventCategory.HARDWARE,
    EventType.ROBOT_CALIBRATION_COMPLETED: EventCategory.HARDWARE,
    EventType.ROBOT_ERROR: EventCategory.ERROR,
    EventType.ROBOT_STATUS_CHANGED: EventCategory.HARDWARE,

    # 网络事件
    EventType.WEB_CLIENT_CONNECTED: EventCategory.NETWORK,
    EventType.WEB_CLIENT_DISCONNECTED: EventCategory.NETWORK,
    EventType.WEB_MESSAGE_RECEIVED: EventCategory.NETWORK,
    EventType.WEB_MESSAGE_SENT: EventCategory.NETWORK,

    # 监控事件
    EventType.METRICS_UPDATED: EventCategory.SYSTEM,
    EventType.ALERT_TRIGGERED: EventCategory.SYSTEM,
    EventType.HEALTH_CHECK_FAILED: EventCategory.ERROR,
}

# 事件优先级映射
EVENT_PRIORITY_MAPPING = {
    # 系统相关
    EventType.SERVICE_STARTED: EventPriority.NORMAL,
    EventType.SERVICE_STOPPED: EventPriority.HIGH,
    EventType.SERVICE_ERROR: EventPriority.CRITICAL,
    EventType.SERVICE_HEALTH_CHECK: EventPriority.LOW,

    # 游戏相关
    EventType.GAME_CREATED: EventPriority.NORMAL,
    EventType.GAME_STARTED: EventPriority.NORMAL,
    EventType.GAME_PAUSED: EventPriority.NORMAL,
    EventType.GAME_RESUMED: EventPriority.NORMAL,
    EventType.GAME_FINISHED: EventPriority.NORMAL,
    EventType.GAME_ABANDONED: EventPriority.HIGH,
    EventType.GAME_ERROR: EventPriority.HIGH,

    # 移动相关
    EventType.MOVE_REQUESTED: EventPriority.HIGH,
    EventType.MOVE_VALIDATED: EventPriority.HIGH,
    EventType.MOVE_EXECUTED: EventPriority.HIGH,
    EventType.MOVE_COMPLETED: EventPriority.NORMAL,
    EventType.MOVE_FAILED: EventPriority.HIGH,

    # AI相关
    EventType.AI_MOVE_REQUEST: EventPriority.HIGH,
    EventType.AI_MOVE_RESULT: EventPriority.HIGH,
    EventType.AI_ANALYSIS_REQUEST: EventPriority.NORMAL,
    EventType.AI_ANALYSIS_RESULT: EventPriority.NORMAL,
    EventType.AI_ENGINE_READY: EventPriority.NORMAL,
    EventType.AI_ENGINE_BUSY: EventPriority.NORMAL,
    EventType.AI_ENGINE_ERROR: EventPriority.CRITICAL,

    # 硬件相关
    EventType.VISION_BOARD_DETECTED: EventPriority.HIGH,
    EventType.VISION_MOVE_DETECTED: EventPriority.HIGH,
    EventType.VISION_PIECE_DETECTED: EventPriority.NORMAL,
    EventType.VISION_CALIBRATION_STARTED: EventPriority.NORMAL,
    EventType.VISION_CALIBRATION_COMPLETED: EventPriority.NORMAL,
    EventType.VISION_ERROR: EventPriority.CRITICAL,

    EventType.ROBOT_MOVE_COMMAND: EventPriority.HIGH,
    EventType.ROBOT_MOVE_STARTED: EventPriority.HIGH,
    EventType.ROBOT_MOVE_COMPLETED: EventPriority.NORMAL,
    EventType.ROBOT_MOVE_FAILED: EventPriority.CRITICAL,
    EventType.ROBOT_CALIBRATION_STARTED: EventPriority.NORMAL,
    EventType.ROBOT_CALIBRATION_COMPLETED: EventPriority.NORMAL,
    EventType.ROBOT_ERROR: EventPriority.CRITICAL,
    EventType.ROBOT_STATUS_CHANGED: EventPriority.NORMAL,

    # 网络相关
    EventType.WEB_CLIENT_CONNECTED: EventPriority.LOW,
    EventType.WEB_CLIENT_DISCONNECTED: EventPriority.LOW,
    EventType.WEB_MESSAGE_RECEIVED: EventPriority.NORMAL,
    EventType.WEB_MESSAGE_SENT: EventPriority.NORMAL,

    # 标定相关
    EventType.CALIBRATION_STEP_STARTED: EventPriority.NORMAL,
    EventType.CALIBRATION_STEP_COMPLETED: EventPriority.NORMAL,
    EventType.CALIBRATION_STEP_FAILED: EventPriority.HIGH,
    EventType.CALIBRATION_COMPLETED: EventPriority.HIGH,
    EventType.CALIBRATION_FAILED: EventPriority.HIGH,

    # 监控相关
    EventType.METRICS_UPDATED: EventPriority.LOW,
    EventType.ALERT_TRIGGERED: EventPriority.HIGH,
    EventType.HEALTH_CHECK_FAILED: EventPriority.HIGH,
}


def get_event_category(event_type: EventType) -> EventCategory:
    """获取事件分类"""
    return EVENT_CATEGORY_MAPPING.get(event_type, EventCategory.SYSTEM)


def get_event_priority(event_type: EventType) -> EventPriority:
    """获取事件优先级"""
    return EVENT_PRIORITY_MAPPING.get(event_type, EventPriority.NORMAL)


def get_channel_for_event(event_type: EventType, service_name: str = None, game_id: str = None) -> str:
    """根据事件类型获取建议的频道名"""

    # 服务相关事件
    if event_type in [EventType.SERVICE_STARTED, EventType.SERVICE_STOPPED, EventType.SERVICE_ERROR]:
        return f"service.{service_name}.status" if service_name else "service.status"

    # 游戏相关事件
    if event_type in [EventType.GAME_CREATED, EventType.GAME_STARTED, EventType.GAME_FINISHED]:
        return f"game.{game_id}.status" if game_id else "game.status"

    # 移动相关事件
    if event_type in [EventType.MOVE_REQUESTED, EventType.MOVE_EXECUTED, EventType.MOVE_COMPLETED]:
        return f"game.{game_id}.moves" if game_id else "game.moves"

    # AI相关事件
    if event_type in [EventType.AI_MOVE_REQUEST, EventType.AI_MOVE_RESULT]:
        return "ai.moves"

    if event_type in [EventType.AI_ANALYSIS_REQUEST, EventType.AI_ANALYSIS_RESULT]:
        return "ai.analysis"

    # 硬件相关事件
    if event_type.value.startswith("vision"):
        return "vision.events"

    if event_type.value.startswith("robot"):
        return "robot.events"

    # 网络相关事件
    if event_type.value.startswith("web"):
        return "web.events"

    # 监控相关事件
    if event_type in [EventType.METRICS_UPDATED, EventType.ALERT_TRIGGERED]:
        return "system.monitoring"

    # 默认频道
    return "system.events"


# 预定义频道订阅模式
SUBSCRIPTION_PATTERNS = {
    "all_events": "*",
    "system_events": "system.*",
    "service_events": "service.*",
    "game_events": "game.*",
    "hardware_events": ["vision.*", "robot.*"],
    "network_events": "web.*",
    "error_events": "*.error",
    "high_priority_events": ["*.critical", "*.error", "game.*.moves"],
}


def get_subscription_patterns(categories: List[str] = None) -> List[str]:
    """获取订阅模式"""
    if not categories:
        return ["*"]

    patterns = []
    for category in categories:
        if category in SUBSCRIPTION_PATTERNS:
            pattern = SUBSCRIPTION_PATTERNS[category]
            if isinstance(pattern, list):
                patterns.extend(pattern)
            else:
                patterns.append(pattern)

    return patterns