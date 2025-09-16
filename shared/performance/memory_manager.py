# -*- coding: utf-8 -*-
"""
内存管理模块
为Jetson Orin Nano 4GB内存环境提供高效内存管理
"""

import gc
import sys
import time
import threading
import weakref
from typing import Any, Dict, List, Optional, Callable, TypeVar, Generic
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
import psutil
import tracemalloc
from contextlib import contextmanager

T = TypeVar('T')


@dataclass
class MemoryStats:
    """内存统计信息"""
    total_memory: int
    available_memory: int
    used_memory: int
    memory_percent: float
    swap_total: int
    swap_used: int
    swap_free: int
    cache_memory: int
    gc_collections: int
    gc_collected_objects: int


class MemoryPool(Generic[T]):
    """对象内存池 - 减少频繁的内存分配/释放"""

    def __init__(self, factory: Callable[[], T], max_size: int = 100, reset_func: Optional[Callable[[T], None]] = None):
        """
        初始化内存池

        Args:
            factory: 对象创建函数
            max_size: 池最大大小
            reset_func: 对象重置函数
        """
        self.factory = factory
        self.max_size = max_size
        self.reset_func = reset_func
        self._pool: List[T] = []
        self._lock = threading.Lock()
        self._created_count = 0
        self._acquired_count = 0
        self._returned_count = 0

    def acquire(self) -> T:
        """获取对象"""
        with self._lock:
            self._acquired_count += 1

            if self._pool:
                obj = self._pool.pop()
                return obj
            else:
                self._created_count += 1
                return self.factory()

    def release(self, obj: T) -> bool:
        """释放对象回池中"""
        if obj is None:
            return False

        with self._lock:
            self._returned_count += 1

            if len(self._pool) >= self.max_size:
                # 池已满，直接丢弃对象
                return False

            # 重置对象状态
            if self.reset_func:
                try:
                    self.reset_func(obj)
                except Exception:
                    # 重置失败，丢弃对象
                    return False

            self._pool.append(obj)
            return True

    def clear(self):
        """清空池"""
        with self._lock:
            self._pool.clear()

    def get_stats(self) -> Dict[str, int]:
        """获取池统计信息"""
        with self._lock:
            return {
                'pool_size': len(self._pool),
                'max_size': self.max_size,
                'created_count': self._created_count,
                'acquired_count': self._acquired_count,
                'returned_count': self._returned_count,
                'hit_rate': (self._acquired_count - self._created_count) / max(self._acquired_count, 1) * 100
            }

    @contextmanager
    def get_object(self):
        """上下文管理器方式使用对象"""
        obj = self.acquire()
        try:
            yield obj
        finally:
            self.release(obj)


class ObjectCache:
    """智能对象缓存 - LRU策略"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        初始化对象缓存

        Args:
            max_size: 缓存最大容量
            ttl_seconds: 对象存活时间
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._timestamps: Dict[str, datetime] = {}
        self._lock = threading.RLock()
        self._hit_count = 0
        self._miss_count = 0

        # 启动清理线程
        self._cleanup_thread = threading.Thread(target=self._cleanup_expired, daemon=True)
        self._cleanup_thread.start()

    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存对象"""
        with self._lock:
            if key in self._cache:
                # 检查是否过期
                if self._is_expired(key):
                    self._remove(key)
                    self._miss_count += 1
                    return default

                # 更新访问顺序 (LRU)
                value = self._cache[key]
                self._cache.move_to_end(key)
                self._hit_count += 1
                return value
            else:
                self._miss_count += 1
                return default

    def put(self, key: str, value: Any) -> bool:
        """存储对象到缓存"""
        with self._lock:
            # 如果key已存在，更新值和时间戳
            if key in self._cache:
                self._cache[key] = value
                self._cache.move_to_end(key)
                self._timestamps[key] = datetime.utcnow()
                return True

            # 检查是否需要清理空间
            if len(self._cache) >= self.max_size:
                # 移除最少使用的项目
                self._remove_lru()

            self._cache[key] = value
            self._timestamps[key] = datetime.utcnow()
            return True

    def remove(self, key: str) -> bool:
        """移除指定缓存项"""
        with self._lock:
            if key in self._cache:
                self._remove(key)
                return True
            return False

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            total_requests = self._hit_count + self._miss_count
            hit_rate = (self._hit_count / total_requests * 100) if total_requests > 0 else 0

            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hit_count': self._hit_count,
                'miss_count': self._miss_count,
                'hit_rate': hit_rate,
                'memory_usage': self._estimate_memory_usage()
            }

    def _is_expired(self, key: str) -> bool:
        """检查对象是否过期"""
        if key not in self._timestamps:
            return True

        timestamp = self._timestamps[key]
        return datetime.utcnow() - timestamp > timedelta(seconds=self.ttl_seconds)

    def _remove(self, key: str):
        """移除缓存项"""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)

    def _remove_lru(self):
        """移除最少使用的项目"""
        if self._cache:
            oldest_key = next(iter(self._cache))
            self._remove(oldest_key)

    def _cleanup_expired(self):
        """清理过期项目的后台线程"""
        while True:
            time.sleep(300)  # 每5分钟清理一次

            with self._lock:
                expired_keys = [
                    key for key in self._cache
                    if self._is_expired(key)
                ]

                for key in expired_keys:
                    self._remove(key)

    def _estimate_memory_usage(self) -> int:
        """估算缓存内存使用量"""
        try:
            return sum(sys.getsizeof(key) + sys.getsizeof(value)
                      for key, value in self._cache.items())
        except Exception:
            return 0


class GarbageCollector:
    """智能垃圾回收管理器"""

    def __init__(self):
        """初始化垃圾回收管理器"""
        self.gc_stats = {
            'manual_collections': 0,
            'total_collected': 0,
            'collection_times': []
        }

        # 设置垃圾回收阈值（更激进的回收策略）
        self._set_gc_thresholds()

    def _set_gc_thresholds(self):
        """设置垃圾回收阈值"""
        # 对于内存受限环境，使用更激进的回收策略
        gc.set_threshold(500, 10, 5)  # 默认是700, 10, 10

    def collect_garbage(self, generation: Optional[int] = None) -> int:
        """手动触发垃圾回收"""
        start_time = time.time()

        if generation is not None:
            collected = gc.collect(generation)
        else:
            collected = gc.collect()

        collection_time = time.time() - start_time

        # 更新统计
        self.gc_stats['manual_collections'] += 1
        self.gc_stats['total_collected'] += collected
        self.gc_stats['collection_times'].append(collection_time)

        # 只保留最近100次的回收时间记录
        if len(self.gc_stats['collection_times']) > 100:
            self.gc_stats['collection_times'] = self.gc_stats['collection_times'][-100:]

        return collected

    def get_gc_stats(self) -> Dict[str, Any]:
        """获取垃圾回收统计信息"""
        gc_counts = gc.get_count()
        gc_thresholds = gc.get_threshold()

        avg_collection_time = 0
        if self.gc_stats['collection_times']:
            avg_collection_time = sum(self.gc_stats['collection_times']) / len(self.gc_stats['collection_times'])

        return {
            'gc_counts': gc_counts,
            'gc_thresholds': gc_thresholds,
            'manual_collections': self.gc_stats['manual_collections'],
            'total_collected': self.gc_stats['total_collected'],
            'avg_collection_time': avg_collection_time,
            'gc_enabled': gc.isenabled()
        }

    def optimize_gc(self):
        """优化垃圾回收设置"""
        # 确保垃圾回收启用
        if not gc.isenabled():
            gc.enable()

        # 立即回收所有代的垃圾
        for generation in range(3):
            self.collect_garbage(generation)

    def disable_gc_temporarily(self):
        """临时禁用垃圾回收（用于性能关键操作）"""
        return gc.disable

    @contextmanager
    def no_gc(self):
        """上下文管理器：在代码块中禁用垃圾回收"""
        was_enabled = gc.isenabled()
        gc.disable()
        try:
            yield
        finally:
            if was_enabled:
                gc.enable()


class MemoryManager:
    """统一内存管理器"""

    def __init__(self, memory_limit_mb: int = 3072):  # 为4GB内存的Jetson设置3GB限制
        """
        初始化内存管理器

        Args:
            memory_limit_mb: 内存使用限制（MB）
        """
        self.memory_limit_mb = memory_limit_mb
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024

        # 子模块
        self.gc_manager = GarbageCollector()
        self.object_cache = ObjectCache(max_size=10000, ttl_seconds=1800)
        self._pools: Dict[str, MemoryPool] = {}

        # 内存监控
        self._memory_alerts: List[Callable[[MemoryStats], None]] = []
        self._last_memory_check = time.time()
        self._memory_check_interval = 30  # 30秒检查一次

        # 启用内存跟踪
        if not tracemalloc.is_tracing():
            tracemalloc.start()

    def create_pool(self, name: str, factory: Callable[[], T],
                   max_size: int = 100, reset_func: Optional[Callable[[T], None]] = None) -> MemoryPool[T]:
        """创建对象池"""
        pool = MemoryPool(factory, max_size, reset_func)
        self._pools[name] = pool
        return pool

    def get_pool(self, name: str) -> Optional[MemoryPool]:
        """获取对象池"""
        return self._pools.get(name)

    def get_memory_stats(self) -> MemoryStats:
        """获取内存统计信息"""
        memory_info = psutil.virtual_memory()
        swap_info = psutil.swap_memory()

        # 垃圾回收统计
        gc_stats = self.gc_manager.get_gc_stats()

        return MemoryStats(
            total_memory=memory_info.total,
            available_memory=memory_info.available,
            used_memory=memory_info.used,
            memory_percent=memory_info.percent,
            swap_total=swap_info.total,
            swap_used=swap_info.used,
            swap_free=swap_info.free,
            cache_memory=getattr(memory_info, 'cached', 0),
            gc_collections=gc_stats['manual_collections'],
            gc_collected_objects=gc_stats['total_collected']
        )

    def check_memory_pressure(self) -> bool:
        """检查内存压力"""
        current_time = time.time()
        if current_time - self._last_memory_check < self._memory_check_interval:
            return False

        self._last_memory_check = current_time
        stats = self.get_memory_stats()

        # 触发警报
        for alert_callback in self._memory_alerts:
            try:
                alert_callback(stats)
            except Exception:
                pass

        # 内存使用超过90%时认为有压力
        return stats.memory_percent > 90

    def optimize_memory(self) -> Dict[str, Any]:
        """内存优化操作"""
        optimization_results = {}

        # 1. 垃圾回收
        collected_objects = self.gc_manager.collect_garbage()
        optimization_results['gc_collected'] = collected_objects

        # 2. 清理过期缓存
        cache_stats_before = self.object_cache.get_stats()
        self.object_cache._cleanup_expired()
        cache_stats_after = self.object_cache.get_stats()
        optimization_results['cache_cleaned'] = cache_stats_before['size'] - cache_stats_after['size']

        # 3. 清理对象池（如果内存压力很大）
        if self.check_memory_pressure():
            pools_cleared = 0
            for pool in self._pools.values():
                pool.clear()
                pools_cleared += 1
            optimization_results['pools_cleared'] = pools_cleared

        return optimization_results

    def add_memory_alert(self, callback: Callable[[MemoryStats], None]):
        """添加内存警报回调"""
        self._memory_alerts.append(callback)

    def get_memory_usage_by_type(self) -> Dict[str, int]:
        """获取按对象类型分组的内存使用情况"""
        if not tracemalloc.is_tracing():
            return {}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            usage_by_type = defaultdict(int)
            for stat in top_stats[:20]:  # 只看前20个
                filename = stat.traceback.format()[-1] if stat.traceback.format() else 'unknown'
                usage_by_type[filename] += stat.size

            return dict(usage_by_type)
        except Exception:
            return {}

    def get_system_summary(self) -> Dict[str, Any]:
        """获取系统内存摘要"""
        stats = self.get_memory_stats()
        cache_stats = self.object_cache.get_stats()
        gc_stats = self.gc_manager.get_gc_stats()

        pool_stats = {}
        for name, pool in self._pools.items():
            pool_stats[name] = pool.get_stats()

        return {
            'memory_stats': {
                'total_gb': round(stats.total_memory / (1024**3), 2),
                'used_gb': round(stats.used_memory / (1024**3), 2),
                'available_gb': round(stats.available_memory / (1024**3), 2),
                'usage_percent': stats.memory_percent,
                'swap_used_mb': round(stats.swap_used / (1024**2), 2)
            },
            'cache_stats': cache_stats,
            'gc_stats': gc_stats,
            'pool_stats': pool_stats,
            'memory_limit_mb': self.memory_limit_mb,
            'memory_pressure': self.check_memory_pressure()
        }

    @contextmanager
    def memory_profiler(self, description: str = ""):
        """内存使用分析上下文管理器"""
        if not tracemalloc.is_tracing():
            tracemalloc.start()

        # 记录开始状态
        start_memory = self.get_memory_stats()
        start_snapshot = tracemalloc.take_snapshot()
        start_time = time.time()

        try:
            yield
        finally:
            # 记录结束状态
            end_time = time.time()
            end_memory = self.get_memory_stats()
            end_snapshot = tracemalloc.take_snapshot()

            # 计算差异
            memory_diff = end_memory.used_memory - start_memory.used_memory
            time_diff = end_time - start_time

            # 打印分析结果
            print(f"\n=== Memory Profile: {description} ===")
            print(f"执行时间: {time_diff:.3f}秒")
            print(f"内存变化: {memory_diff / (1024**2):.2f} MB")
            print(f"内存使用率: {start_memory.memory_percent:.1f}% -> {end_memory.memory_percent:.1f}%")

            # 显示内存增长最多的地方
            try:
                top_stats = end_snapshot.compare_to(start_snapshot, 'lineno')
                print("\n内存增长最多的位置:")
                for stat in top_stats[:5]:
                    print(f"  {stat}")
            except Exception:
                pass

            print("=" * 50)

    def __del__(self):
        """清理资源"""
        try:
            # 停止内存跟踪
            if tracemalloc.is_tracing():
                tracemalloc.stop()
        except Exception:
            pass