"""
Redis事件总线实现
提供基于Redis Pub/Sub的事件驱动消息系统
"""
import asyncio
import json
import logging
from typing import Dict, Callable, Any, Optional, Set, List
from datetime import datetime
import redis.asyncio as redis
from redis.asyncio import Redis
from dataclasses import asdict

from .models import Event


logger = logging.getLogger(__name__)


class EventSubscription:
    """事件订阅信息"""

    def __init__(self, pattern: str, callback: Callable, service_name: str = ""):
        self.pattern = pattern
        self.callback = callback
        self.service_name = service_name
        self.created_at = datetime.now()
        self.message_count = 0


class EventBus:
    """Redis事件总线"""

    def __init__(self, redis_config: Dict[str, Any]):
        """初始化事件总线"""
        self.redis_config = redis_config
        self.redis_client: Optional[Redis] = None
        self.pubsub = None
        self.subscriptions: Dict[str, List[EventSubscription]] = {}
        self.running = False
        self.service_name = "event_bus"

        # 事件统计
        self.stats = {
            "messages_published": 0,
            "messages_received": 0,
            "subscriptions_count": 0,
            "errors_count": 0,
            "started_at": None,
        }

    async def connect(self):
        """连接Redis"""
        try:
            # 创建Redis连接
            self.redis_client = redis.Redis(
                host=self.redis_config.get("host", "localhost"),
                port=self.redis_config.get("port", 6379),
                db=self.redis_config.get("db", 0),
                password=self.redis_config.get("password"),
                decode_responses=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30,
            )

            # 测试连接
            await self.redis_client.ping()

            # 创建pub/sub对象
            self.pubsub = self.redis_client.pubsub()

            self.running = True
            self.stats["started_at"] = datetime.now()

            logger.info("EventBus connected to Redis successfully")

            # 启动消息监听任务
            asyncio.create_task(self._listen_messages())

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def close(self):
        """关闭连接"""
        logger.info("Closing EventBus connection...")
        self.running = False

        if self.pubsub:
            await self.pubsub.close()

        if self.redis_client:
            await self.redis_client.close()

        logger.info("EventBus connection closed")

    def is_connected(self) -> bool:
        """检查是否连接"""
        return self.running and self.redis_client is not None

    async def publish(self, channel: str, event: Event):
        """发布事件"""
        if not self.is_connected():
            raise RuntimeError("EventBus is not connected")

        try:
            # 添加元数据
            event.published_at = datetime.now()
            if not event.event_id:
                event.event_id = f"{channel}_{int(datetime.now().timestamp() * 1000)}"

            # 序列化事件
            message = json.dumps(asdict(event), default=self._json_serializer)

            # 发布到Redis
            await self.redis_client.publish(channel, message)

            self.stats["messages_published"] += 1

            logger.debug(f"Published event to {channel}: {event.type}")

        except Exception as e:
            self.stats["errors_count"] += 1
            logger.error(f"Failed to publish event to {channel}: {e}")
            raise

    async def subscribe(self, pattern: str, callback: Callable, service_name: str = ""):
        """订阅事件"""
        if not self.is_connected():
            raise RuntimeError("EventBus is not connected")

        try:
            # 创建订阅信息
            subscription = EventSubscription(pattern, callback, service_name)

            # 添加到订阅列表
            if pattern not in self.subscriptions:
                self.subscriptions[pattern] = []
                # 订阅Redis频道
                if "*" in pattern or "?" in pattern:
                    await self.pubsub.psubscribe(pattern)
                else:
                    await self.pubsub.subscribe(pattern)

            self.subscriptions[pattern].append(subscription)
            self.stats["subscriptions_count"] += 1

            logger.info(f"Subscribed to pattern: {pattern} (service: {service_name})")

        except Exception as e:
            self.stats["errors_count"] += 1
            logger.error(f"Failed to subscribe to {pattern}: {e}")
            raise

    async def unsubscribe(self, pattern: str, callback: Callable = None):
        """取消订阅"""
        if pattern not in self.subscriptions:
            return

        try:
            if callback:
                # 移除特定回调
                self.subscriptions[pattern] = [
                    sub for sub in self.subscriptions[pattern]
                    if sub.callback != callback
                ]
            else:
                # 移除所有回调
                self.subscriptions[pattern] = []

            # 如果没有更多订阅者，取消Redis订阅
            if not self.subscriptions[pattern]:
                if "*" in pattern or "?" in pattern:
                    await self.pubsub.punsubscribe(pattern)
                else:
                    await self.pubsub.unsubscribe(pattern)
                del self.subscriptions[pattern]
                self.stats["subscriptions_count"] -= 1

            logger.info(f"Unsubscribed from pattern: {pattern}")

        except Exception as e:
            self.stats["errors_count"] += 1
            logger.error(f"Failed to unsubscribe from {pattern}: {e}")
            raise

    async def _listen_messages(self):
        """监听消息循环"""
        logger.info("Started EventBus message listener")

        try:
            while self.running:
                try:
                    # 获取消息（超时1秒）
                    message = await asyncio.wait_for(
                        self.pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=1.0
                    )

                    if message:
                        await self._handle_message(message)

                except asyncio.TimeoutError:
                    # 超时是正常的，继续监听
                    continue

                except Exception as e:
                    logger.error(f"Error in message listener: {e}")
                    self.stats["errors_count"] += 1
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Message listener crashed: {e}")
        finally:
            logger.info("EventBus message listener stopped")

    async def _handle_message(self, message):
        """处理接收到的消息"""
        try:
            channel = message.get("channel", "")
            data = message.get("data", "")

            if not data:
                return

            # 反序列化事件
            event_data = json.loads(data)
            event = Event(**event_data)

            self.stats["messages_received"] += 1

            # 查找匹配的订阅
            matching_subscriptions = self._find_matching_subscriptions(channel)

            # 调用回调函数
            for subscription in matching_subscriptions:
                try:
                    subscription.message_count += 1
                    await self._invoke_callback(subscription.callback, event)
                except Exception as e:
                    logger.error(f"Error in callback for {subscription.pattern}: {e}")
                    self.stats["errors_count"] += 1

            logger.debug(f"Handled message from {channel}: {event.type}")

        except Exception as e:
            logger.error(f"Failed to handle message: {e}")
            self.stats["errors_count"] += 1

    def _find_matching_subscriptions(self, channel: str) -> List[EventSubscription]:
        """查找匹配的订阅"""
        matching = []

        for pattern, subscriptions in self.subscriptions.items():
            if self._pattern_matches(pattern, channel):
                matching.extend(subscriptions)

        return matching

    def _pattern_matches(self, pattern: str, channel: str) -> bool:
        """检查模式是否匹配频道"""
        if pattern == channel:
            return True

        # 简单的通配符匹配
        if "*" in pattern:
            import fnmatch
            return fnmatch.fnmatch(channel, pattern)

        return False

    async def _invoke_callback(self, callback: Callable, event: Event):
        """调用回调函数"""
        if asyncio.iscoroutinefunction(callback):
            await callback(event)
        else:
            callback(event)

    def _json_serializer(self, obj):
        """JSON序列化器"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "is_connected": self.is_connected(),
            "subscriptions": {
                pattern: len(subs) for pattern, subs in self.subscriptions.items()
            },
            "uptime_seconds": (
                (datetime.now() - self.stats["started_at"]).total_seconds()
                if self.stats["started_at"] else 0
            )
        }

    async def get_subscription_info(self) -> List[Dict[str, Any]]:
        """获取订阅信息"""
        info = []
        for pattern, subscriptions in self.subscriptions.items():
            for sub in subscriptions:
                info.append({
                    "pattern": sub.pattern,
                    "service_name": sub.service_name,
                    "created_at": sub.created_at.isoformat(),
                    "message_count": sub.message_count
                })
        return info

    async def clear_stats(self):
        """清除统计信息"""
        self.stats.update({
            "messages_published": 0,
            "messages_received": 0,
            "errors_count": 0,
        })

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            if not self.is_connected():
                return {"status": "unhealthy", "reason": "not_connected"}

            # 测试Redis连接
            await self.redis_client.ping()

            return {
                "status": "healthy",
                "stats": await self.get_stats()
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "reason": str(e)
            }


class EventManager:
    """事件管理器 - 提供更高级的事件管理功能"""

    def __init__(self, event_bus: EventBus, service_name: str):
        self.event_bus = event_bus
        self.service_name = service_name
        self.event_handlers: Dict[str, Callable] = {}

    async def emit(self, event_type: str, payload: Dict[str, Any], channel: str = None):
        """发出事件"""
        if not channel:
            channel = f"service.{self.service_name}.events"

        event = Event(
            type=event_type,
            payload=payload,
            source=self.service_name
        )

        await self.event_bus.publish(channel, event)

    async def on(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        self.event_handlers[event_type] = handler

        # 订阅相关频道
        await self.event_bus.subscribe(
            f"*{event_type}*",
            self._handle_event,
            self.service_name
        )

    async def _handle_event(self, event: Event):
        """处理事件"""
        if event.type in self.event_handlers:
            handler = self.event_handlers[event.type]
            await self._invoke_handler(handler, event)

    async def _invoke_handler(self, handler: Callable, event: Event):
        """调用事件处理器"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            logger.error(f"Error in event handler for {event.type}: {e}")

    async def notify_service_status(self, status: str):
        """通知服务状态"""
        await self.emit("service_status", {
            "service": self.service_name,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }, f"service.{self.service_name}.status")

    async def request_response(self, request_type: str, payload: Dict[str, Any],
                             timeout: float = 30.0) -> Dict[str, Any]:
        """请求-响应模式"""
        request_id = f"{request_type}_{int(datetime.now().timestamp() * 1000)}"
        response_channel = f"response.{request_id}"

        # 订阅响应频道
        response_event = asyncio.Event()
        response_data = {}

        async def response_handler(event: Event):
            nonlocal response_data
            response_data = event.payload
            response_event.set()

        await self.event_bus.subscribe(response_channel, response_handler)

        try:
            # 发送请求
            await self.emit(request_type, {
                "request_id": request_id,
                "response_channel": response_channel,
                **payload
            })

            # 等待响应
            await asyncio.wait_for(response_event.wait(), timeout=timeout)
            return response_data

        except asyncio.TimeoutError:
            raise TimeoutError(f"Request {request_type} timed out after {timeout}s")
        finally:
            # 清理订阅
            await self.event_bus.unsubscribe(response_channel, response_handler)


# 全局事件总线实例
_global_event_bus: Optional[EventBus] = None


async def get_event_bus(redis_config: Dict[str, Any] = None) -> EventBus:
    """获取全局事件总线实例"""
    global _global_event_bus

    if _global_event_bus is None:
        if redis_config is None:
            redis_config = {
                "host": "localhost",
                "port": 6379,
                "db": 0
            }

        _global_event_bus = EventBus(redis_config)
        await _global_event_bus.connect()

    return _global_event_bus


async def close_event_bus():
    """关闭全局事件总线"""
    global _global_event_bus
    if _global_event_bus:
        await _global_event_bus.close()
        _global_event_bus = None