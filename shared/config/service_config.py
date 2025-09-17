"""
象棋机器人系统 - 服务间通信配置
"""

import os
from typing import Dict, List, Optional
from pydantic import BaseSettings, Field


class ServiceEndpoint(BaseSettings):
    """服务端点配置"""
    host: str = "localhost"
    port: int
    protocol: str = "http"
    health_path: str = "/health"
    metrics_path: str = "/metrics"

    @property
    def base_url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def health_url(self) -> str:
        return f"{self.base_url}{self.health_path}"

    @property
    def metrics_url(self) -> str:
        return f"{self.base_url}{self.metrics_path}"


class RedisConfig(BaseSettings):
    """Redis配置"""
    host: str = Field(default="redis", env="REDIS_HOST")
    port: int = Field(default=6379, env="REDIS_PORT")
    db: int = Field(default=0, env="REDIS_DB")
    password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")

    # 连接池配置
    max_connections: int = Field(default=100, env="REDIS_MAX_CONNECTIONS")
    retry_on_timeout: bool = Field(default=True, env="REDIS_RETRY_ON_TIMEOUT")

    # 消息队列配置
    message_queue_prefix: str = Field(default="chess_robot", env="REDIS_QUEUE_PREFIX")

    @property
    def connection_url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class MongoDBConfig(BaseSettings):
    """MongoDB配置"""
    host: str = Field(default="mongodb", env="MONGODB_HOST")
    port: int = Field(default=27017, env="MONGODB_PORT")
    database: str = Field(default="chess_robot", env="MONGODB_DATABASE")
    username: Optional[str] = Field(default=None, env="MONGODB_USERNAME")
    password: Optional[str] = Field(default=None, env="MONGODB_PASSWORD")

    # 连接池配置
    max_pool_size: int = Field(default=100, env="MONGODB_MAX_POOL_SIZE")
    min_pool_size: int = Field(default=0, env="MONGODB_MIN_POOL_SIZE")
    max_idle_time_ms: int = Field(default=30000, env="MONGODB_MAX_IDLE_TIME")

    @property
    def connection_url(self) -> str:
        if self.username and self.password:
            return f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        return f"mongodb://{self.host}:{self.port}/{self.database}"


class ServiceRegistry(BaseSettings):
    """服务注册中心配置"""

    # 服务端点定义
    services = {
        "web_gateway": ServiceEndpoint(port=8000),
        "game_manager": ServiceEndpoint(port=8001),
        "ai_engine": ServiceEndpoint(port=8002),
        "vision_service": ServiceEndpoint(port=8003),
        "robot_service": ServiceEndpoint(port=8004),
    }

    # 监控服务
    monitoring_services = {
        "prometheus": ServiceEndpoint(port=9090),
        "grafana": ServiceEndpoint(port=3000),
        "alertmanager": ServiceEndpoint(port=9093),
    }

    @classmethod
    def get_service_url(cls, service_name: str) -> str:
        """获取服务URL"""
        if service_name in cls.services:
            return cls.services[service_name].base_url
        raise ValueError(f"Unknown service: {service_name}")

    @classmethod
    def get_health_url(cls, service_name: str) -> str:
        """获取服务健康检查URL"""
        if service_name in cls.services:
            return cls.services[service_name].health_url
        raise ValueError(f"Unknown service: {service_name}")

    @classmethod
    def list_services(cls) -> List[str]:
        """列出所有服务"""
        return list(cls.services.keys())


class MessageChannels:
    """消息通道定义"""

    # 游戏相关事件
    GAME_EVENTS = {
        "game_started": "chess_robot:events:game_started",
        "game_ended": "chess_robot:events:game_ended",
        "move_made": "chess_robot:events:move_made",
        "turn_changed": "chess_robot:events:turn_changed",
    }

    # 视觉识别事件
    VISION_EVENTS = {
        "board_detected": "chess_robot:events:board_detected",
        "piece_moved": "chess_robot:events:piece_moved",
        "detection_error": "chess_robot:events:detection_error",
    }

    # 机器人控制事件
    ROBOT_EVENTS = {
        "move_started": "chess_robot:events:robot_move_started",
        "move_completed": "chess_robot:events:robot_move_completed",
        "move_failed": "chess_robot:events:robot_move_failed",
        "robot_status": "chess_robot:events:robot_status",
    }

    # AI引擎事件
    AI_EVENTS = {
        "thinking_started": "chess_robot:events:ai_thinking_started",
        "move_calculated": "chess_robot:events:ai_move_calculated",
        "analysis_complete": "chess_robot:events:ai_analysis_complete",
    }

    # 系统事件
    SYSTEM_EVENTS = {
        "service_status": "chess_robot:events:service_status",
        "health_check": "chess_robot:events:health_check",
        "error_occurred": "chess_robot:events:error_occurred",
    }

    @classmethod
    def get_all_channels(cls) -> Dict[str, str]:
        """获取所有消息通道"""
        channels = {}
        for category in [cls.GAME_EVENTS, cls.VISION_EVENTS, cls.ROBOT_EVENTS,
                        cls.AI_EVENTS, cls.SYSTEM_EVENTS]:
            channels.update(category)
        return channels


class CommunicationConfig(BaseSettings):
    """通信配置"""

    # HTTP超时配置
    http_timeout: int = Field(default=30, env="HTTP_TIMEOUT")
    http_retries: int = Field(default=3, env="HTTP_RETRIES")
    http_backoff_factor: float = Field(default=0.3, env="HTTP_BACKOFF_FACTOR")

    # WebSocket配置
    websocket_ping_interval: int = Field(default=20, env="WS_PING_INTERVAL")
    websocket_ping_timeout: int = Field(default=10, env="WS_PING_TIMEOUT")
    websocket_close_timeout: int = Field(default=10, env="WS_CLOSE_TIMEOUT")

    # 消息队列配置
    message_queue_timeout: int = Field(default=5, env="MQ_TIMEOUT")
    message_queue_retries: int = Field(default=3, env="MQ_RETRIES")
    message_batch_size: int = Field(default=100, env="MQ_BATCH_SIZE")

    # 服务发现配置
    service_discovery_interval: int = Field(default=30, env="SERVICE_DISCOVERY_INTERVAL")
    health_check_interval: int = Field(default=10, env="HEALTH_CHECK_INTERVAL")

    # 安全配置
    api_key_header: str = Field(default="X-API-Key", env="API_KEY_HEADER")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=60, env="JWT_EXPIRE_MINUTES")


# 全局配置实例
redis_config = RedisConfig()
mongodb_config = MongoDBConfig()
service_registry = ServiceRegistry()
communication_config = CommunicationConfig()


def get_service_config() -> Dict:
    """获取完整的服务配置"""
    return {
        "redis": redis_config.dict(),
        "mongodb": mongodb_config.dict(),
        "services": service_registry.dict(),
        "communication": communication_config.dict(),
        "message_channels": MessageChannels.get_all_channels(),
    }