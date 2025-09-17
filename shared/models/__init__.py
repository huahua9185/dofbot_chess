# Shared Data Models

from .chess_models import *
from .database_models import *
from ..utils.redis_client import Event
from enum import Enum

class ServiceStatus(Enum):
    """服务状态枚举"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    UNKNOWN = "unknown"