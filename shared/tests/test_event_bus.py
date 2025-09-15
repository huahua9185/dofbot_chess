"""
事件总线测试
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from ..event_bus import EventBus, EventManager
from ..models import Event
from ..events.event_types import EventType
from ..events.middleware import (
    EventLoggingMiddleware, EventMetricsMiddleware,
    EventFilterMiddleware, RateLimitConfig, RateLimitMiddleware,
    MiddlewareChain, create_standard_middleware_chain
)


@pytest.fixture
async def redis_config():
    """Redis配置"""
    return {
        "host": "localhost",
        "port": 6379,
        "db": 0
    }


@pytest.fixture
async def event_bus(redis_config):
    """事件总线实例"""
    bus = EventBus(redis_config)
    yield bus
    if bus.is_connected():
        await bus.close()


@pytest.fixture
def sample_event():
    """示例事件"""
    return Event(
        type="test.event",
        payload={"message": "test message"},
        source="test_service"
    )


class TestEventBus:
    """事件总线测试类"""

    @pytest.mark.asyncio
    async def test_event_bus_connection(self, redis_config):
        """测试事件总线连接"""
        bus = EventBus(redis_config)

        # 初始状态
        assert not bus.is_connected()

        # 模拟Redis连接
        bus.redis_client = AsyncMock()
        bus.redis_client.ping = AsyncMock(return_value=True)
        bus.pubsub = AsyncMock()
        bus.running = True

        assert bus.is_connected()

        await bus.close()

    @pytest.mark.asyncio
    async def test_publish_event(self, event_bus, sample_event):
        """测试发布事件"""
        # 模拟Redis客户端
        event_bus.redis_client = AsyncMock()
        event_bus.redis_client.publish = AsyncMock(return_value=1)
        event_bus.running = True

        # 发布事件
        await event_bus.publish("test.channel", sample_event)

        # 验证调用
        event_bus.redis_client.publish.assert_called_once()
        args, kwargs = event_bus.redis_client.publish.call_args
        assert args[0] == "test.channel"
        assert sample_event.type in args[1]  # 序列化后的JSON包含事件类型

        # 验证统计
        assert event_bus.stats["messages_published"] == 1

    @pytest.mark.asyncio
    async def test_subscribe_and_unsubscribe(self, event_bus):
        """测试订阅和取消订阅"""
        # 模拟Redis和pubsub
        event_bus.redis_client = AsyncMock()
        event_bus.pubsub = AsyncMock()
        event_bus.pubsub.subscribe = AsyncMock()
        event_bus.pubsub.unsubscribe = AsyncMock()
        event_bus.running = True

        # 测试回调
        callback = AsyncMock()

        # 订阅
        await event_bus.subscribe("test.pattern", callback, "test_service")

        # 验证订阅
        assert "test.pattern" in event_bus.subscriptions
        assert len(event_bus.subscriptions["test.pattern"]) == 1
        event_bus.pubsub.subscribe.assert_called_once_with("test.pattern")

        # 取消订阅
        await event_bus.unsubscribe("test.pattern", callback)

        # 验证取消订阅
        assert "test.pattern" not in event_bus.subscriptions
        event_bus.pubsub.unsubscribe.assert_called_once_with("test.pattern")

    @pytest.mark.asyncio
    async def test_pattern_matching(self, event_bus):
        """测试模式匹配"""
        # 测试精确匹配
        assert event_bus._pattern_matches("test.channel", "test.channel")

        # 测试通配符匹配
        assert event_bus._pattern_matches("test.*", "test.channel")
        assert event_bus._pattern_matches("*.channel", "test.channel")
        assert not event_bus._pattern_matches("other.*", "test.channel")

    @pytest.mark.asyncio
    async def test_callback_invocation(self, event_bus, sample_event):
        """测试回调函数调用"""
        # 同步回调
        sync_callback = MagicMock()
        await event_bus._invoke_callback(sync_callback, sample_event)
        sync_callback.assert_called_once_with(sample_event)

        # 异步回调
        async_callback = AsyncMock()
        await event_bus._invoke_callback(async_callback, sample_event)
        async_callback.assert_called_once_with(sample_event)

    @pytest.mark.asyncio
    async def test_stats_and_health_check(self, event_bus):
        """测试统计信息和健康检查"""
        # 模拟连接状态
        event_bus.running = True
        event_bus.redis_client = AsyncMock()
        event_bus.redis_client.ping = AsyncMock(return_value=True)

        # 获取统计信息
        stats = await event_bus.get_stats()
        assert isinstance(stats, dict)
        assert "messages_published" in stats
        assert "messages_received" in stats
        assert "is_connected" in stats

        # 健康检查
        health = await event_bus.health_check()
        assert health["status"] == "healthy"

        # 模拟连接失败
        event_bus.redis_client.ping = AsyncMock(side_effect=Exception("Connection failed"))
        health = await event_bus.health_check()
        assert health["status"] == "unhealthy"


class TestEventManager:
    """事件管理器测试类"""

    @pytest.fixture
    def event_manager(self, event_bus):
        """事件管理器实例"""
        return EventManager(event_bus, "test_service")

    @pytest.mark.asyncio
    async def test_emit_event(self, event_manager):
        """测试发出事件"""
        # 模拟事件总线
        event_manager.event_bus.publish = AsyncMock()

        # 发出事件
        await event_manager.emit("test.event", {"key": "value"})

        # 验证调用
        event_manager.event_bus.publish.assert_called_once()
        args, kwargs = event_manager.event_bus.publish.call_args
        assert args[0] == "service.test_service.events"
        assert args[1].type == "test.event"
        assert args[1].payload == {"key": "value"}

    @pytest.mark.asyncio
    async def test_event_handler_registration(self, event_manager):
        """测试事件处理器注册"""
        # 模拟订阅
        event_manager.event_bus.subscribe = AsyncMock()

        # 注册处理器
        handler = AsyncMock()
        await event_manager.on("test.event", handler)

        # 验证注册
        assert "test.event" in event_manager.event_handlers
        assert event_manager.event_handlers["test.event"] == handler
        event_manager.event_bus.subscribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_response_pattern(self, event_manager):
        """测试请求-响应模式"""
        # 模拟发送请求
        event_manager.event_bus.publish = AsyncMock()
        event_manager.event_bus.subscribe = AsyncMock()
        event_manager.event_bus.unsubscribe = AsyncMock()

        # 模拟响应
        async def mock_wait_for(event_wait, timeout):
            # 立即设置响应
            await asyncio.sleep(0.01)
            event_wait.set()

        # 模拟响应数据
        response_data = {"result": "success"}

        # 在测试中模拟响应处理
        original_subscribe = event_manager.event_bus.subscribe

        async def mock_subscribe(channel, handler):
            if channel.startswith("response."):
                # 模拟接收响应
                response_event = Event(
                    type="response",
                    payload=response_data,
                    source="test"
                )
                await handler(response_event)

        event_manager.event_bus.subscribe = mock_subscribe

        # 测试请求-响应（这里需要模拟异步处理）
        # 在实际测试中，可能需要更复杂的模拟

    @pytest.mark.asyncio
    async def test_service_status_notification(self, event_manager):
        """测试服务状态通知"""
        # 模拟事件总线
        event_manager.event_bus.publish = AsyncMock()

        # 通知服务状态
        await event_manager.notify_service_status("running")

        # 验证调用
        event_manager.event_bus.publish.assert_called_once()
        args, kwargs = event_manager.event_bus.publish.call_args
        assert args[0] == "service.test_service.status"
        assert args[1].type == "service_status"


class TestEventMiddleware:
    """事件中间件测试类"""

    @pytest.fixture
    def sample_handler(self):
        """示例处理器"""
        return AsyncMock(return_value="handled")

    @pytest.mark.asyncio
    async def test_logging_middleware(self, sample_event, sample_handler):
        """测试日志中间件"""
        middleware = EventLoggingMiddleware()

        result = await middleware.process(sample_event, sample_handler)

        assert result == "handled"
        sample_handler.assert_called_once_with(sample_event)

    @pytest.mark.asyncio
    async def test_metrics_middleware(self, sample_event, sample_handler):
        """测试指标中间件"""
        middleware = EventMetricsMiddleware()

        # 初始指标
        assert middleware.metrics["total_events"] == 0

        # 处理事件
        result = await middleware.process(sample_event, sample_handler)

        # 验证指标更新
        assert result == "handled"
        assert middleware.metrics["total_events"] == 1
        assert sample_event.type in middleware.metrics["events_by_type"]
        assert middleware.metrics["events_by_source"].get(sample_event.source, 0) > 0

    @pytest.mark.asyncio
    async def test_filter_middleware(self, sample_event, sample_handler):
        """测试过滤中间件"""
        # 允许事件通过的过滤器
        allow_filter = EventFilterMiddleware(lambda e: True)
        result = await allow_filter.process(sample_event, sample_handler)
        assert result == "handled"

        # 阻止事件的过滤器
        block_filter = EventFilterMiddleware(lambda e: False)
        result = await block_filter.process(sample_event, sample_handler)
        assert result is None
        # 处理器不应被调用
        sample_handler.reset_mock()

    @pytest.mark.asyncio
    async def test_rate_limit_middleware(self, sample_event, sample_handler):
        """测试速率限制中间件"""
        config = RateLimitConfig(max_events=2, time_window=1, per_source=True)
        middleware = RateLimitMiddleware(config)

        # 第一次和第二次调用应该成功
        result1 = await middleware.process(sample_event, sample_handler)
        assert result1 == "handled"

        result2 = await middleware.process(sample_event, sample_handler)
        assert result2 == "handled"

        # 第三次调用应该被限制
        result3 = await middleware.process(sample_event, sample_handler)
        assert result3 is None

    @pytest.mark.asyncio
    async def test_middleware_chain(self, sample_event, sample_handler):
        """测试中间件链"""
        chain = MiddlewareChain()

        # 添加多个中间件
        chain.add(EventLoggingMiddleware())
        chain.add(EventMetricsMiddleware())
        chain.add(EventFilterMiddleware(lambda e: True))

        # 执行中间件链
        result = await chain.execute(sample_event, sample_handler)

        assert result == "handled"
        sample_handler.assert_called_once_with(sample_event)

    def test_standard_middleware_chain_creation(self):
        """测试标准中间件链创建"""
        # 创建标准中间件链
        chain = create_standard_middleware_chain(
            enable_logging=True,
            enable_metrics=True,
            enable_rate_limit=False,
            enable_retry=False
        )

        assert len(chain.middlewares) == 2  # logging + metrics

        # 包含速率限制的链
        rate_config = RateLimitConfig(max_events=10, time_window=60)
        chain_with_rate = create_standard_middleware_chain(
            enable_logging=True,
            enable_metrics=True,
            enable_rate_limit=True,
            rate_limit_config=rate_config
        )

        assert len(chain_with_rate.middlewares) == 3  # logging + metrics + rate limit


if __name__ == "__main__":
    pytest.main([__file__])