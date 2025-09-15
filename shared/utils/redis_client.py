"""
Redis客户端和事件驱动消息系统
"""
import asyncio
import json
import aioredis
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass, asdict
from shared.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Event:
    """事件数据结构"""
    event_type: str
    payload: Dict[str, Any]
    source: str
    timestamp: float
    correlation_id: Optional[str] = None


class RedisEventBus:
    """Redis事件总线"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis = None
        self.subscribers: Dict[str, List[Callable]] = {}
        self.running = False

    async def connect(self):
        """连接Redis"""
        try:
            self.redis = await aioredis.from_url(self.redis_url)
            await self.redis.ping()
            logger.info("Redis连接成功", redis_url=self.redis_url)
        except Exception as e:
            logger.error("Redis连接失败", error=str(e))
            raise

    async def disconnect(self):
        """断开Redis连接"""
        if self.redis:
            await self.redis.close()
            logger.info("Redis连接已关闭")

    async def publish(self, event: Event) -> bool:
        """发布事件"""
        if not self.redis:
            logger.error("Redis未连接")
            return False

        try:
            channel = f"chess_robot:{event.event_type}"
            message = json.dumps(asdict(event))
            result = await self.redis.publish(channel, message)
            logger.debug("事件发布成功",
                        event_type=event.event_type,
                        channel=channel,
                        subscribers=result)
            return result > 0
        except Exception as e:
            logger.error("事件发布失败",
                        event_type=event.event_type,
                        error=str(e))
            return False

    def subscribe(self, event_type: str, handler: Callable[[Event], None]):
        """订阅事件"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        logger.info("订阅事件", event_type=event_type, handler=handler.__name__)

    async def start_listening(self):
        """开始监听事件"""
        if not self.redis:
            await self.connect()

        self.running = True
        pubsub = self.redis.pubsub()

        # 订阅所有注册的事件类型
        for event_type in self.subscribers.keys():
            channel = f"chess_robot:{event_type}"
            await pubsub.subscribe(channel)
            logger.info("开始监听频道", channel=channel)

        logger.info("事件监听器启动")

        try:
            while self.running:
                message = await pubsub.get_message(timeout=1.0)
                if message and message['type'] == 'message':
                    await self._handle_message(message)
        except Exception as e:
            logger.error("事件监听错误", error=str(e))
        finally:
            await pubsub.unsubscribe()
            await pubsub.close()

    async def stop_listening(self):
        """停止监听"""
        self.running = False
        logger.info("事件监听器停止")

    async def _handle_message(self, message: Dict[str, Any]):
        """处理收到的消息"""
        try:
            channel = message['channel'].decode()
            event_type = channel.split(':')[-1]
            data = json.loads(message['data'])
            event = Event(**data)

            # 调用所有订阅者的处理函数
            if event_type in self.subscribers:
                for handler in self.subscribers[event_type]:
                    try:
                        await handler(event)
                    except Exception as e:
                        logger.error("事件处理器异常",
                                   event_type=event_type,
                                   handler=handler.__name__,
                                   error=str(e))
        except Exception as e:
            logger.error("消息处理失败", error=str(e))


class RedisCache:
    """Redis缓存客户端"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis = None

    async def connect(self):
        """连接Redis"""
        try:
            self.redis = await aioredis.from_url(self.redis_url)
            await self.redis.ping()
            logger.info("Redis缓存连接成功")
        except Exception as e:
            logger.error("Redis缓存连接失败", error=str(e))
            raise

    async def disconnect(self):
        """断开连接"""
        if self.redis:
            await self.redis.close()

    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """设置缓存"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            elif not isinstance(value, str):
                value = str(value)

            result = await self.redis.set(key, value, ex=expire)
            return result
        except Exception as e:
            logger.error("设置缓存失败", key=key, error=str(e))
            return False

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        try:
            value = await self.redis.get(key)
            if value is None:
                return None

            value = value.decode() if isinstance(value, bytes) else value

            # 尝试解析JSON
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            logger.error("获取缓存失败", key=key, error=str(e))
            return None

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            result = await self.redis.delete(key)
            return result > 0
        except Exception as e:
            logger.error("删除缓存失败", key=key, error=str(e))
            return False

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            result = await self.redis.exists(key)
            return result > 0
        except Exception as e:
            logger.error("检查缓存存在性失败", key=key, error=str(e))
            return False