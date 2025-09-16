# -*- coding: utf-8 -*-
"""
性能优化模块
提供缓存管理、异步任务池、懒加载等性能优化功能
"""

import asyncio
import threading
import time
import weakref
from typing import Any, Dict, List, Optional, Callable, TypeVar, Generic, Union, Coroutine
from collections import defaultdict, OrderedDict
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from functools import wraps, lru_cache
import json
import pickle
import hashlib
from pathlib import Path

T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])


@dataclass
class CacheStats:
    """缓存统计信息"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    memory_usage: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0


class CacheManager:
    """高级缓存管理器"""

    def __init__(self, default_ttl: int = 3600, max_memory_mb: int = 100):
        """
        初始化缓存管理器

        Args:
            default_ttl: 默认TTL（秒）
            max_memory_mb: 最大内存使用（MB）
        """
        self.default_ttl = default_ttl
        self.max_memory_bytes = max_memory_mb * 1024 * 1024

        self._caches: Dict[str, Dict[str, Any]] = {}
        self._metadata: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._stats: Dict[str, CacheStats] = defaultdict(CacheStats)
        self._lock = threading.RLock()

    def create_cache(self, name: str, max_size: int = 1000, ttl: Optional[int] = None) -> bool:
        """创建命名缓存"""
        with self._lock:
            if name in self._caches:
                return False

            self._caches[name] = OrderedDict()
            self._metadata[name] = {}
            self._stats[name] = CacheStats()
            return True

    def get(self, cache_name: str, key: str, default: Any = None) -> Any:
        """获取缓存值"""
        with self._lock:
            if cache_name not in self._caches:
                return default

            cache = self._caches[cache_name]
            metadata = self._metadata[cache_name]
            stats = self._stats[cache_name]

            if key not in cache:
                stats.misses += 1
                return default

            # 检查TTL
            meta = metadata.get(key, {})
            if meta.get('expires_at', float('inf')) < time.time():
                self._remove_item(cache_name, key)
                stats.misses += 1
                return default

            # 更新访问时间和LRU顺序
            meta['accessed_at'] = time.time()
            meta['access_count'] = meta.get('access_count', 0) + 1
            cache.move_to_end(key)

            stats.hits += 1
            return cache[key]

    def set(self, cache_name: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        with self._lock:
            if cache_name not in self._caches:
                self.create_cache(cache_name)

            cache = self._caches[cache_name]
            metadata = self._metadata[cache_name]

            # 计算过期时间
            expires_at = float('inf')
            if ttl is not None:
                expires_at = time.time() + ttl
            elif self.default_ttl > 0:
                expires_at = time.time() + self.default_ttl

            # 检查内存限制
            value_size = self._estimate_size(value)
            if not self._ensure_memory_available(cache_name, value_size):
                return False

            # 存储值和元数据
            cache[key] = value
            metadata[key] = {
                'created_at': time.time(),
                'accessed_at': time.time(),
                'expires_at': expires_at,
                'size': value_size,
                'access_count': 0
            }

            # 更新内存使用统计
            self._stats[cache_name].memory_usage += value_size

            return True

    def delete(self, cache_name: str, key: str) -> bool:
        """删除缓存项"""
        with self._lock:
            return self._remove_item(cache_name, key)

    def clear(self, cache_name: str) -> bool:
        """清空缓存"""
        with self._lock:
            if cache_name not in self._caches:
                return False

            self._caches[cache_name].clear()
            self._metadata[cache_name].clear()
            self._stats[cache_name] = CacheStats()
            return True

    def get_stats(self, cache_name: str) -> Optional[CacheStats]:
        """获取缓存统计"""
        return self._stats.get(cache_name)

    def cache_decorator(self, cache_name: str, ttl: Optional[int] = None,
                       key_func: Optional[Callable] = None):
        """缓存装饰器"""
        def decorator(func: F) -> F:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 生成缓存键
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = self._generate_key(func.__name__, args, kwargs)

                # 尝试从缓存获取
                result = self.get(cache_name, cache_key)
                if result is not None:
                    return result

                # 计算结果并缓存
                result = func(*args, **kwargs)
                self.set(cache_name, cache_key, result, ttl)
                return result

            return wrapper
        return decorator

    def _remove_item(self, cache_name: str, key: str) -> bool:
        """移除缓存项"""
        if cache_name not in self._caches or key not in self._caches[cache_name]:
            return False

        # 更新内存使用统计
        meta = self._metadata[cache_name].get(key, {})
        size = meta.get('size', 0)
        self._stats[cache_name].memory_usage -= size
        self._stats[cache_name].evictions += 1

        # 删除数据
        del self._caches[cache_name][key]
        del self._metadata[cache_name][key]
        return True

    def _ensure_memory_available(self, cache_name: str, required_size: int) -> bool:
        """确保有足够内存空间"""
        stats = self._stats[cache_name]

        if stats.memory_usage + required_size <= self.max_memory_bytes:
            return True

        # 需要清理内存，按LRU顺序清理
        cache = self._caches[cache_name]
        metadata = self._metadata[cache_name]

        while stats.memory_usage + required_size > self.max_memory_bytes and cache:
            # 移除最老的项目
            oldest_key = next(iter(cache))
            self._remove_item(cache_name, oldest_key)

        return stats.memory_usage + required_size <= self.max_memory_bytes

    def _estimate_size(self, obj: Any) -> int:
        """估算对象大小"""
        try:
            if isinstance(obj, (str, int, float, bool)):
                return len(str(obj).encode('utf-8'))
            elif isinstance(obj, (list, tuple, dict)):
                return len(json.dumps(obj, ensure_ascii=False).encode('utf-8'))
            else:
                return len(pickle.dumps(obj))
        except Exception:
            return 1024  # 默认1KB

    def _generate_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """生成缓存键"""
        key_data = {
            'func': func_name,
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        key_str = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(key_str.encode('utf-8')).hexdigest()


class AsyncTaskPool:
    """异步任务池 - 管理异步任务执行"""

    def __init__(self, max_concurrent_tasks: int = 10, max_queue_size: int = 100):
        """
        初始化异步任务池

        Args:
            max_concurrent_tasks: 最大并发任务数
            max_queue_size: 最大队列大小
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_queue_size = max_queue_size

        self._task_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._completed_tasks: Dict[str, Any] = {}
        self._task_results: Dict[str, Any] = {}
        self._task_stats = {
            'submitted': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0
        }

        self._running = False
        self._workers: List[asyncio.Task] = []

    async def start(self):
        """启动任务池"""
        if self._running:
            return

        self._running = True
        self._task_queue = asyncio.Queue(maxsize=self.max_queue_size)

        # 启动工作协程
        for i in range(self.max_concurrent_tasks):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(worker)

    async def stop(self, timeout: float = 30.0):
        """停止任务池"""
        if not self._running:
            return

        self._running = False

        # 等待所有工作协程完成
        if self._workers:
            await asyncio.wait_for(
                asyncio.gather(*self._workers, return_exceptions=True),
                timeout=timeout
            )

        # 取消剩余任务
        for task in self._active_tasks.values():
            if not task.done():
                task.cancel()

        self._workers.clear()
        self._active_tasks.clear()

    async def submit_task(self, task_id: str, coro: Coroutine) -> bool:
        """提交异步任务"""
        if not self._running:
            return False

        try:
            await self._task_queue.put((task_id, coro), timeout=1.0)
            self._task_stats['submitted'] += 1
            return True
        except asyncio.TimeoutError:
            return False

    async def get_result(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """获取任务结果"""
        if task_id in self._task_results:
            return self._task_results[task_id]

        # 等待任务完成
        start_time = time.time()
        while task_id not in self._task_results:
            if timeout and (time.time() - start_time) > timeout:
                raise asyncio.TimeoutError(f"Task {task_id} timeout")

            await asyncio.sleep(0.1)

        return self._task_results[task_id]

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self._active_tasks:
            task = self._active_tasks[task_id]
            if not task.done():
                task.cancel()
                self._task_stats['cancelled'] += 1
                return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """获取任务池统计"""
        return {
            'running': self._running,
            'max_concurrent_tasks': self.max_concurrent_tasks,
            'active_tasks': len(self._active_tasks),
            'queue_size': self._task_queue.qsize(),
            'max_queue_size': self.max_queue_size,
            'stats': self._task_stats.copy()
        }

    async def _worker(self, worker_name: str):
        """工作协程"""
        while self._running:
            try:
                # 获取任务
                task_id, coro = await asyncio.wait_for(
                    self._task_queue.get(),
                    timeout=1.0
                )

                # 执行任务
                task = asyncio.create_task(coro)
                self._active_tasks[task_id] = task

                try:
                    result = await task
                    self._task_results[task_id] = result
                    self._task_stats['completed'] += 1
                except asyncio.CancelledError:
                    self._task_stats['cancelled'] += 1
                    raise
                except Exception as e:
                    self._task_results[task_id] = e
                    self._task_stats['failed'] += 1
                finally:
                    self._active_tasks.pop(task_id, None)
                    self._task_queue.task_done()

            except asyncio.TimeoutError:
                continue  # 超时继续等待
            except asyncio.CancelledError:
                break  # 工作协程被取消


class LazyLoader:
    """懒加载管理器 - 延迟加载资源以节省内存"""

    def __init__(self):
        """初始化懒加载管理器"""
        self._loaders: Dict[str, Callable] = {}
        self._loaded: Dict[str, Any] = {}
        self._loading: Dict[str, bool] = {}
        self._lock = threading.RLock()
        self._stats = {
            'registered': 0,
            'loaded': 0,
            'cache_hits': 0
        }

    def register(self, name: str, loader: Callable[[], Any],
                cache_result: bool = True) -> None:
        """
        注册懒加载资源

        Args:
            name: 资源名称
            loader: 加载函数
            cache_result: 是否缓存结果
        """
        with self._lock:
            self._loaders[name] = {
                'loader': loader,
                'cache_result': cache_result
            }
            self._stats['registered'] += 1

    def load(self, name: str, *args, **kwargs) -> Any:
        """加载资源"""
        with self._lock:
            if name not in self._loaders:
                raise KeyError(f"Resource '{name}' not registered")

            # 检查缓存
            if name in self._loaded:
                self._stats['cache_hits'] += 1
                return self._loaded[name]

            # 检查是否正在加载（避免重复加载）
            if self._loading.get(name, False):
                # 简单的等待机制
                while self._loading.get(name, False):
                    time.sleep(0.01)

                if name in self._loaded:
                    return self._loaded[name]

            # 开始加载
            self._loading[name] = True

            try:
                loader_config = self._loaders[name]
                loader = loader_config['loader']
                cache_result = loader_config['cache_result']

                # 执行加载
                result = loader(*args, **kwargs)

                # 缓存结果（如果配置为缓存）
                if cache_result:
                    self._loaded[name] = result

                self._stats['loaded'] += 1
                return result

            finally:
                self._loading[name] = False

    def unload(self, name: str) -> bool:
        """卸载资源"""
        with self._lock:
            if name in self._loaded:
                del self._loaded[name]
                return True
            return False

    def is_loaded(self, name: str) -> bool:
        """检查资源是否已加载"""
        return name in self._loaded

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                'registered_count': len(self._loaders),
                'loaded_count': len(self._loaded),
                'stats': self._stats.copy()
            }

    def lazy_property(self, loader: Callable[[], T]) -> property:
        """懒加载属性装饰器"""
        attr_name = f"_lazy_{id(loader)}"

        def getter(self):
            if not hasattr(self, attr_name):
                setattr(self, attr_name, loader())
            return getattr(self, attr_name)

        def setter(self, value):
            setattr(self, attr_name, value)

        def deleter(self):
            if hasattr(self, attr_name):
                delattr(self, attr_name)

        return property(getter, setter, deleter)


class PerformanceOptimizer:
    """性能优化器 - 统一管理所有优化功能"""

    def __init__(self):
        """初始化性能优化器"""
        self.cache_manager = CacheManager(max_memory_mb=200)
        self.task_pool = AsyncTaskPool(max_concurrent_tasks=5)
        self.lazy_loader = LazyLoader()

        # 创建默认缓存
        self.cache_manager.create_cache('default', max_size=1000)
        self.cache_manager.create_cache('function_cache', max_size=500)
        self.cache_manager.create_cache('api_cache', max_size=200, ttl=300)

    async def initialize(self):
        """初始化异步组件"""
        await self.task_pool.start()

    async def cleanup(self):
        """清理资源"""
        await self.task_pool.stop()

    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        return {
            'cache_stats': {
                name: self.cache_manager.get_stats(name).__dict__
                for name in self.cache_manager._caches.keys()
            },
            'task_pool_stats': self.task_pool.get_stats(),
            'lazy_loader_stats': self.lazy_loader.get_stats()
        }

    def optimize_function(self, cache_name: str = 'function_cache', ttl: int = 3600):
        """函数优化装饰器"""
        return self.cache_manager.cache_decorator(cache_name, ttl)

    def create_object_pool(self, name: str, factory: Callable[[], T],
                          max_size: int = 50) -> 'MemoryPool[T]':
        """创建对象池（需要导入MemoryPool）"""
        from .memory_manager import MemoryPool
        return MemoryPool(factory, max_size)

    async def run_background_task(self, task_id: str, coro: Coroutine):
        """运行后台任务"""
        return await self.task_pool.submit_task(task_id, coro)

    def register_lazy_resource(self, name: str, loader: Callable):
        """注册懒加载资源"""
        self.lazy_loader.register(name, loader)

    def batch_cache_operations(self, operations: List[Dict[str, Any]]):
        """批量缓存操作"""
        results = []
        for op in operations:
            op_type = op['type']
            cache_name = op['cache_name']
            key = op['key']

            if op_type == 'get':
                result = self.cache_manager.get(cache_name, key, op.get('default'))
                results.append(result)
            elif op_type == 'set':
                value = op['value']
                ttl = op.get('ttl')
                result = self.cache_manager.set(cache_name, key, value, ttl)
                results.append(result)
            elif op_type == 'delete':
                result = self.cache_manager.delete(cache_name, key)
                results.append(result)

        return results