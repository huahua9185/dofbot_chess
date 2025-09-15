"""
事件中间件系统
提供事件过滤、转换、日志记录等功能
"""
import asyncio
import logging
from typing import Callable, List, Any, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from abc import ABC, abstractmethod

from ..models import Event
from .event_types import EventType, EventPriority, get_event_priority


logger = logging.getLogger(__name__)


class EventMiddleware(ABC):
    """事件中间件基类"""

    @abstractmethod
    async def process(self, event: Event, next_handler: Callable) -> Any:
        """处理事件"""
        pass


@dataclass
class RateLimitConfig:
    """速率限制配置"""
    max_events: int          # 最大事件数量
    time_window: int         # 时间窗口（秒）
    per_source: bool = True  # 是否按源限制


class RateLimitMiddleware(EventMiddleware):
    """速率限制中间件"""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.event_counts: Dict[str, List[datetime]] = {}

    async def process(self, event: Event, next_handler: Callable) -> Any:
        """处理事件并应用速率限制"""
        key = event.source if self.config.per_source else "global"
        current_time = datetime.now()

        # 初始化或获取事件计数
        if key not in self.event_counts:
            self.event_counts[key] = []

        # 清理过期的事件记录
        cutoff_time = current_time - timedelta(seconds=self.config.time_window)
        self.event_counts[key] = [
            ts for ts in self.event_counts[key] if ts > cutoff_time
        ]

        # 检查是否超过限制
        if len(self.event_counts[key]) >= self.config.max_events:
            logger.warning(
                f"Rate limit exceeded for {key}: "
                f"{len(self.event_counts[key])}/{self.config.max_events} "
                f"in {self.config.time_window}s"
            )
            # 可以选择丢弃事件或抛出异常
            return None

        # 记录当前事件
        self.event_counts[key].append(current_time)

        # 继续处理
        return await next_handler(event)


class EventFilterMiddleware(EventMiddleware):
    """事件过滤中间件"""

    def __init__(self, filter_func: Callable[[Event], bool]):
        self.filter_func = filter_func

    async def process(self, event: Event, next_handler: Callable) -> Any:
        """过滤事件"""
        if not self.filter_func(event):
            logger.debug(f"Event filtered: {event.type}")
            return None

        return await next_handler(event)


class EventTransformMiddleware(EventMiddleware):
    """事件转换中间件"""

    def __init__(self, transform_func: Callable[[Event], Event]):
        self.transform_func = transform_func

    async def process(self, event: Event, next_handler: Callable) -> Any:
        """转换事件"""
        try:
            transformed_event = self.transform_func(event)
            return await next_handler(transformed_event)
        except Exception as e:
            logger.error(f"Event transformation failed: {e}")
            return await next_handler(event)


class EventLoggingMiddleware(EventMiddleware):
    """事件日志中间件"""

    def __init__(self, log_level: str = "INFO", include_payload: bool = False):
        self.log_level = log_level.upper()
        self.include_payload = include_payload

    async def process(self, event: Event, next_handler: Callable) -> Any:
        """记录事件日志"""
        log_message = f"Event: {event.type} from {event.source}"

        if self.include_payload:
            log_message += f" payload={event.payload}"

        # 根据事件优先级调整日志级别
        priority = get_event_priority(EventType(event.type))
        if priority == EventPriority.CRITICAL:
            logger.critical(log_message)
        elif priority == EventPriority.HIGH:
            logger.warning(log_message)
        else:
            logger.info(log_message)

        return await next_handler(event)


class EventMetricsMiddleware(EventMiddleware):
    """事件指标中间件"""

    def __init__(self):
        self.metrics = {
            "total_events": 0,
            "events_by_type": {},
            "events_by_source": {},
            "events_by_priority": {},
            "processing_time": {},
        }

    async def process(self, event: Event, next_handler: Callable) -> Any:
        """收集事件指标"""
        start_time = datetime.now()

        try:
            # 更新指标
            self.metrics["total_events"] += 1

            # 按类型统计
            event_type = event.type
            self.metrics["events_by_type"][event_type] = (
                self.metrics["events_by_type"].get(event_type, 0) + 1
            )

            # 按源统计
            source = event.source or "unknown"
            self.metrics["events_by_source"][source] = (
                self.metrics["events_by_source"].get(source, 0) + 1
            )

            # 按优先级统计
            try:
                priority = get_event_priority(EventType(event_type))
                priority_name = priority.name
                self.metrics["events_by_priority"][priority_name] = (
                    self.metrics["events_by_priority"].get(priority_name, 0) + 1
                )
            except ValueError:
                pass

            # 处理事件
            result = await next_handler(event)

            # 记录处理时间
            processing_time = (datetime.now() - start_time).total_seconds()
            if event_type not in self.metrics["processing_time"]:
                self.metrics["processing_time"][event_type] = []

            # 只保留最近100次的处理时间
            self.metrics["processing_time"][event_type].append(processing_time)
            if len(self.metrics["processing_time"][event_type]) > 100:
                self.metrics["processing_time"][event_type].pop(0)

            return result

        except Exception as e:
            logger.error(f"Error in metrics middleware: {e}")
            return await next_handler(event)

    def get_metrics(self) -> Dict[str, Any]:
        """获取指标"""
        # 计算平均处理时间
        avg_processing_times = {}
        for event_type, times in self.metrics["processing_time"].items():
            if times:
                avg_processing_times[event_type] = sum(times) / len(times)

        return {
            **self.metrics,
            "avg_processing_time": avg_processing_times
        }

    def reset_metrics(self):
        """重置指标"""
        self.metrics = {
            "total_events": 0,
            "events_by_type": {},
            "events_by_source": {},
            "events_by_priority": {},
            "processing_time": {},
        }


class EventPriorityMiddleware(EventMiddleware):
    """事件优先级中间件"""

    def __init__(self, priority_queue_size: int = 1000):
        self.priority_queues = {
            EventPriority.CRITICAL: asyncio.Queue(maxsize=priority_queue_size),
            EventPriority.HIGH: asyncio.Queue(maxsize=priority_queue_size),
            EventPriority.NORMAL: asyncio.Queue(maxsize=priority_queue_size),
            EventPriority.LOW: asyncio.Queue(maxsize=priority_queue_size),
        }
        self.processing_task = None
        self.running = False

    async def process(self, event: Event, next_handler: Callable) -> Any:
        """按优先级排队处理事件"""
        try:
            priority = get_event_priority(EventType(event.type))
        except ValueError:
            priority = EventPriority.NORMAL

        # 将事件和处理器放入相应的优先级队列
        try:
            await self.priority_queues[priority].put((event, next_handler))
        except asyncio.QueueFull:
            logger.warning(f"Priority queue {priority.name} is full, dropping event {event.type}")

    async def start_processing(self):
        """启动优先级处理任务"""
        if not self.running:
            self.running = True
            self.processing_task = asyncio.create_task(self._process_queues())

    async def stop_processing(self):
        """停止优先级处理任务"""
        self.running = False
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass

    async def _process_queues(self):
        """处理优先级队列"""
        while self.running:
            try:
                # 按优先级顺序处理
                for priority in [EventPriority.CRITICAL, EventPriority.HIGH,
                               EventPriority.NORMAL, EventPriority.LOW]:
                    queue = self.priority_queues[priority]

                    # 处理该优先级队列中的所有事件
                    while not queue.empty():
                        try:
                            event, next_handler = await asyncio.wait_for(
                                queue.get(), timeout=0.1
                            )
                            await next_handler(event)
                        except asyncio.TimeoutError:
                            break
                        except Exception as e:
                            logger.error(f"Error processing priority event: {e}")

                # 短暂休眠避免忙循环
                await asyncio.sleep(0.01)

            except Exception as e:
                logger.error(f"Error in priority queue processing: {e}")
                await asyncio.sleep(1)


class EventRetryMiddleware(EventMiddleware):
    """事件重试中间件"""

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def process(self, event: Event, next_handler: Callable) -> Any:
        """重试处理失败的事件"""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                return await next_handler(event)

            except Exception as e:
                last_error = e

                if attempt < self.max_retries:
                    logger.warning(
                        f"Event processing failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}"
                    )
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))  # 指数退避
                else:
                    logger.error(f"Event processing failed after {self.max_retries + 1} attempts: {e}")

        # 如果所有重试都失败，抛出最后一个异常
        raise last_error


class MiddlewareChain:
    """中间件链"""

    def __init__(self):
        self.middlewares: List[EventMiddleware] = []

    def add(self, middleware: EventMiddleware):
        """添加中间件"""
        self.middlewares.append(middleware)

    def remove(self, middleware: EventMiddleware):
        """移除中间件"""
        if middleware in self.middlewares:
            self.middlewares.remove(middleware)

    async def execute(self, event: Event, final_handler: Callable) -> Any:
        """执行中间件链"""
        async def create_handler(index: int) -> Callable:
            if index >= len(self.middlewares):
                return final_handler

            async def handler(event: Event) -> Any:
                next_handler = await create_handler(index + 1)
                return await self.middlewares[index].process(event, next_handler)

            return handler

        if not self.middlewares:
            return await final_handler(event)

        handler = await create_handler(0)
        return await handler(event)


# 预定义中间件组合
def create_standard_middleware_chain(
    enable_logging: bool = True,
    enable_metrics: bool = True,
    enable_rate_limit: bool = False,
    rate_limit_config: Optional[RateLimitConfig] = None,
    enable_retry: bool = False,
    retry_config: Optional[Dict[str, Any]] = None
) -> MiddlewareChain:
    """创建标准中间件链"""
    chain = MiddlewareChain()

    # 日志中间件
    if enable_logging:
        chain.add(EventLoggingMiddleware())

    # 指标中间件
    if enable_metrics:
        chain.add(EventMetricsMiddleware())

    # 速率限制中间件
    if enable_rate_limit and rate_limit_config:
        chain.add(RateLimitMiddleware(rate_limit_config))

    # 重试中间件
    if enable_retry:
        retry_kwargs = retry_config or {}
        chain.add(EventRetryMiddleware(**retry_kwargs))

    return chain


def create_filter_by_type(allowed_types: List[str]) -> EventFilterMiddleware:
    """创建按类型过滤的中间件"""
    def filter_func(event: Event) -> bool:
        return event.type in allowed_types

    return EventFilterMiddleware(filter_func)


def create_filter_by_source(allowed_sources: List[str]) -> EventFilterMiddleware:
    """创建按源过滤的中间件"""
    def filter_func(event: Event) -> bool:
        return event.source in allowed_sources

    return EventFilterMiddleware(filter_func)


def create_filter_by_priority(min_priority: EventPriority) -> EventFilterMiddleware:
    """创建按优先级过滤的中间件"""
    def filter_func(event: Event) -> bool:
        try:
            priority = get_event_priority(EventType(event.type))
            return priority.value >= min_priority.value
        except ValueError:
            return True

    return EventFilterMiddleware(filter_func)