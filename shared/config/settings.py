"""
系统配置管理
"""
import os
from typing import List, Optional, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings


class RedisSettings(BaseSettings):
    """Redis配置"""
    url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    max_connections: int = Field(default=10, env="REDIS_MAX_CONNECTIONS")
    timeout: float = Field(default=5.0, env="REDIS_TIMEOUT")

    class Config:
        env_prefix = "REDIS_"


class MongoSettings(BaseSettings):
    """MongoDB配置"""
    url: str = Field(default="mongodb://localhost:27017", env="MONGO_URL")
    database: str = Field(default="robot_chess", env="MONGO_DATABASE")
    username: Optional[str] = Field(default=None, env="MONGO_USERNAME")
    password: Optional[str] = Field(default=None, env="MONGO_PASSWORD")

    class Config:
        env_prefix = "MONGO_"


class CameraSettings(BaseSettings):
    """相机配置"""
    rgb_device_id: int = Field(default=0, env="CAMERA_RGB_ID")
    depth_device_id: int = Field(default=1, env="CAMERA_DEPTH_ID")
    rgb_width: int = Field(default=1920, env="CAMERA_RGB_WIDTH")
    rgb_height: int = Field(default=1080, env="CAMERA_RGB_HEIGHT")
    depth_width: int = Field(default=640, env="CAMERA_DEPTH_WIDTH")
    depth_height: int = Field(default=480, env="CAMERA_DEPTH_HEIGHT")
    fps: int = Field(default=30, env="CAMERA_FPS")
    calibration_file: str = Field(
        default="calibration/camera_params.json",
        env="CAMERA_CALIBRATION_FILE"
    )

    class Config:
        env_prefix = "CAMERA_"


class RobotSettings(BaseSettings):
    """机器人配置"""
    port: str = Field(default="/dev/ttyUSB0", env="ROBOT_PORT")
    baudrate: int = Field(default=115200, env="ROBOT_BAUDRATE")
    timeout: float = Field(default=2.0, env="ROBOT_TIMEOUT")
    default_speed: int = Field(default=50, env="ROBOT_DEFAULT_SPEED")
    safe_height: float = Field(default=50.0, env="ROBOT_SAFE_HEIGHT")
    calibration_file: str = Field(
        default="calibration/robot_params.json",
        env="ROBOT_CALIBRATION_FILE"
    )

    class Config:
        env_prefix = "ROBOT_"


class AISettings(BaseSettings):
    """AI引擎配置"""
    stockfish_path: str = Field(default="stockfish", env="STOCKFISH_PATH")
    default_difficulty: int = Field(default=3, env="AI_DEFAULT_DIFFICULTY")
    max_thinking_time: float = Field(default=10.0, env="AI_MAX_THINKING_TIME")
    hash_size: int = Field(default=128, env="AI_HASH_SIZE")  # MB
    threads: int = Field(default=2, env="AI_THREADS")

    class Config:
        env_prefix = "AI_"


class WebSettings(BaseSettings):
    """Web服务配置"""
    host: str = Field(default="0.0.0.0", env="WEB_HOST")
    port: int = Field(default=8080, env="WEB_PORT")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000"],
        env="CORS_ORIGINS"
    )
    jwt_secret: str = Field(default="default-jwt-secret-key-for-development", env="JWT_SECRET")
    jwt_expire_minutes: int = Field(default=30, env="JWT_EXPIRE_MINUTES")

    class Config:
        env_prefix = "WEB_"


class LogSettings(BaseSettings):
    """日志配置"""
    level: str = Field(default="INFO", env="LOG_LEVEL")
    dir: str = Field(default="/var/log/robot-chess", env="LOG_DIR")
    max_size: int = Field(default=100, env="LOG_MAX_SIZE")  # MB
    backup_count: int = Field(default=5, env="LOG_BACKUP_COUNT")

    class Config:
        env_prefix = "LOG_"


class MetricsSettings(BaseSettings):
    """监控配置"""
    enabled: bool = Field(default=True, env="METRICS_ENABLED")
    port: int = Field(default=9090, env="METRICS_PORT")
    update_interval: float = Field(default=5.0, env="METRICS_UPDATE_INTERVAL")
    health_check_interval: float = Field(
        default=30.0,
        env="HEALTH_CHECK_INTERVAL"
    )

    class Config:
        env_prefix = "METRICS_"


class SecuritySettings(BaseSettings):
    """安全配置"""
    encryption_key: str = Field(default="default-encryption-key-for-development", env="ENCRYPTION_KEY")
    max_login_attempts: int = Field(default=3, env="MAX_LOGIN_ATTEMPTS")
    lockout_duration: int = Field(default=300, env="LOCKOUT_DURATION")  # 秒
    api_rate_limit: int = Field(default=100, env="API_RATE_LIMIT")  # 每分钟

    class Config:
        env_prefix = "SECURITY_"


class Settings(BaseSettings):
    """主配置类"""
    # 环境
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")

    # 服务名称
    service_name: str = Field(default="robot_chess", env="SERVICE_NAME")

    # 子配置
    redis: RedisSettings = RedisSettings()
    mongo: MongoSettings = MongoSettings()
    camera: CameraSettings = CameraSettings()
    robot: RobotSettings = RobotSettings()
    ai: AISettings = AISettings()
    web: WebSettings = WebSettings()
    log: LogSettings = LogSettings()
    metrics: MetricsSettings = MetricsSettings()
    security: SecuritySettings = SecuritySettings()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
settings = Settings()


def get_settings() -> Settings:
    """获取配置实例"""
    return settings


def reload_settings():
    """重新加载配置"""
    global settings
    settings = Settings()