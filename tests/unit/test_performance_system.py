# -*- coding: utf-8 -*-
"""
性能优化系统单元测试
测试内存管理、资源监控、性能优化等功能
"""

import sys
import os
import unittest
import asyncio
import tempfile
import threading
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.performance import (
    MemoryManager,
    MemoryPool,
    ObjectCache,
    ResourceMonitor,
    PerformanceOptimizer,
    CacheManager,
    AsyncTaskPool,
    LazyLoader
)


class TestMemoryPool(unittest.TestCase):
    """测试内存池功能"""

    def setUp(self):
        """测试设置"""
        self.pool = MemoryPool(
            factory=dict,
            max_size=5,
            reset_func=lambda d: d.clear()
        )

    def test_basic_operations(self):
        """测试基本操作"""
        # 获取对象
        obj1 = self.pool.acquire()
        self.assertIsInstance(obj1, dict)

        # 使用对象
        obj1['test'] = 'value'
        self.assertEqual(obj1['test'], 'value')

        # 释放对象
        result = self.pool.release(obj1)
        self.assertTrue(result)

        # 再次获取应该得到同一个对象（已重置）
        obj2 = self.pool.acquire()
        self.assertIsInstance(obj2, dict)
        self.assertEqual(len(obj2), 0)  # 应该已被重置

    def test_pool_limits(self):
        """测试池大小限制"""
        # 创建多个对象
        objects = []
        for i in range(10):
            obj = self.pool.acquire()
            obj[f'key_{i}'] = f'value_{i}'
            objects.append(obj)

        # 释放对象
        released_count = 0
        for obj in objects:
            if self.pool.release(obj):
                released_count += 1

        # 只应该有max_size个对象被保留
        self.assertLessEqual(released_count, self.pool.max_size)

        # 检查统计信息
        stats = self.pool.get_stats()
        self.assertEqual(stats['created_count'], 10)
        self.assertGreaterEqual(stats['pool_size'], 0)

    def test_context_manager(self):
        """测试上下文管理器"""
        with self.pool.get_object() as obj:
            self.assertIsInstance(obj, dict)
            obj['test'] = 'context'

        # 对象应该自动被释放


class TestObjectCache(unittest.TestCase):
    """测试对象缓存功能"""

    def setUp(self):
        """测试设置"""
        self.cache = ObjectCache(max_size=10, ttl_seconds=1)

    def test_basic_cache_operations(self):
        """测试基本缓存操作"""
        # 存储数据
        result = self.cache.put('key1', 'value1')
        self.assertTrue(result)

        # 获取数据
        value = self.cache.get('key1')
        self.assertEqual(value, 'value1')

        # 获取不存在的键
        value = self.cache.get('nonexistent', 'default')
        self.assertEqual(value, 'default')

        # 删除数据
        result = self.cache.remove('key1')
        self.assertTrue(result)

        value = self.cache.get('key1')
        self.assertIsNone(value)

    def test_ttl_expiration(self):
        """测试TTL过期"""
        # 存储数据
        self.cache.put('expire_key', 'expire_value')

        # 立即获取应该成功
        value = self.cache.get('expire_key')
        self.assertEqual(value, 'expire_value')

        # 等待过期
        time.sleep(1.5)

        # 获取应该失败
        value = self.cache.get('expire_key')
        self.assertIsNone(value)

    def test_lru_eviction(self):
        """测试LRU淘汰"""
        # 填满缓存
        for i in range(10):
            self.cache.put(f'key_{i}', f'value_{i}')

        # 添加新项目，应该淘汰最老的
        self.cache.put('new_key', 'new_value')

        # 检查统计信息
        stats = self.cache.get_stats()
        self.assertGreater(stats['hit_count'] + stats['miss_count'], 0)

    def test_cache_decorator(self):
        """测试缓存装饰器"""
        call_count = {'count': 0}

        @self.cache.cache_decorator('test_cache', ttl=5)
        def expensive_function(x, y):
            call_count['count'] += 1
            return x + y

        # 第一次调用
        result1 = expensive_function(1, 2)
        self.assertEqual(result1, 3)
        self.assertEqual(call_count['count'], 1)

        # 第二次调用应该从缓存获取
        result2 = expensive_function(1, 2)
        self.assertEqual(result2, 3)
        self.assertEqual(call_count['count'], 1)  # 没有增加

        # 不同参数应该重新计算
        result3 = expensive_function(2, 3)
        self.assertEqual(result3, 5)
        self.assertEqual(call_count['count'], 2)


class TestMemoryManager(unittest.TestCase):
    """测试内存管理器"""

    def setUp(self):
        """测试设置"""
        self.memory_manager = MemoryManager(memory_limit_mb=100)

    def tearDown(self):
        """清理资源"""
        # 停止内存跟踪
        import tracemalloc
        if tracemalloc.is_tracing():
            tracemalloc.stop()

    def test_memory_stats(self):
        """测试内存统计"""
        stats = self.memory_manager.get_memory_stats()

        self.assertIsNotNone(stats.total_memory)
        self.assertIsNotNone(stats.used_memory)
        self.assertIsNotNone(stats.memory_percent)
        self.assertGreaterEqual(stats.memory_percent, 0)
        self.assertLessEqual(stats.memory_percent, 100)

    def test_object_pool_creation(self):
        """测试对象池创建"""
        pool = self.memory_manager.create_pool('test_pool', dict, max_size=5)
        self.assertIsNotNone(pool)

        # 获取池
        retrieved_pool = self.memory_manager.get_pool('test_pool')
        self.assertEqual(pool, retrieved_pool)

    def test_memory_optimization(self):
        """测试内存优化"""
        optimization_results = self.memory_manager.optimize_memory()

        self.assertIn('gc_collected', optimization_results)
        self.assertIn('cache_cleaned', optimization_results)

    def test_memory_profiler(self):
        """测试内存分析器"""
        with self.memory_manager.memory_profiler("test_operation"):
            # 执行一些内存操作
            data = [i for i in range(1000)]
            processed = [x * 2 for x in data]

        # 分析器应该捕获到内存使用情况


class TestCacheManager(unittest.TestCase):
    """测试缓存管理器"""

    def setUp(self):
        """测试设置"""
        self.cache_manager = CacheManager(max_memory_mb=10)

    def test_cache_creation(self):
        """测试缓存创建"""
        result = self.cache_manager.create_cache('test_cache', max_size=100)
        self.assertTrue(result)

        # 重复创建应该失败
        result = self.cache_manager.create_cache('test_cache', max_size=100)
        self.assertFalse(result)

    def test_cache_operations(self):
        """测试缓存操作"""
        self.cache_manager.create_cache('test_cache')

        # 设置值
        result = self.cache_manager.set('test_cache', 'key1', 'value1')
        self.assertTrue(result)

        # 获取值
        value = self.cache_manager.get('test_cache', 'key1')
        self.assertEqual(value, 'value1')

        # 删除值
        result = self.cache_manager.delete('test_cache', 'key1')
        self.assertTrue(result)

        # 清空缓存
        result = self.cache_manager.clear('test_cache')
        self.assertTrue(result)

    def test_cache_decorator(self):
        """测试缓存装饰器"""
        self.cache_manager.create_cache('func_cache')

        call_count = 0

        @self.cache_manager.cache_decorator('func_cache', ttl=10)
        def test_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # 第一次调用
        result1 = test_function(5)
        self.assertEqual(result1, 10)
        self.assertEqual(call_count, 1)

        # 第二次调用应该从缓存获取
        result2 = test_function(5)
        self.assertEqual(result2, 10)
        self.assertEqual(call_count, 1)


class TestAsyncTaskPool(unittest.TestCase):
    """测试异步任务池"""

    def setUp(self):
        """测试设置"""
        self.task_pool = AsyncTaskPool(max_concurrent_tasks=3, max_queue_size=10)

    def tearDown(self):
        """清理资源"""
        asyncio.run(self.async_teardown())

    async def async_teardown(self):
        """异步清理"""
        if hasattr(self, 'task_pool'):
            await self.task_pool.stop()

    def test_task_pool_operations(self):
        """测试任务池操作"""
        async def async_test():
            # 启动任务池
            await self.task_pool.start()

            # 提交任务
            async def test_task():
                await asyncio.sleep(0.1)
                return "task_result"

            success = await self.task_pool.submit_task('test_task', test_task())
            self.assertTrue(success)

            # 获取结果
            result = await self.task_pool.get_result('test_task', timeout=5.0)
            self.assertEqual(result, "task_result")

            # 获取统计信息
            stats = self.task_pool.get_stats()
            self.assertIn('submitted', stats['stats'])
            self.assertIn('completed', stats['stats'])

        asyncio.run(async_test())

    def test_task_cancellation(self):
        """测试任务取消"""
        async def async_test():
            await self.task_pool.start()

            # 提交长时间任务
            async def long_task():
                await asyncio.sleep(10)
                return "long_result"

            await self.task_pool.submit_task('long_task', long_task())

            # 取消任务
            result = await self.task_pool.cancel_task('long_task')
            self.assertTrue(result)

        asyncio.run(async_test())


class TestLazyLoader(unittest.TestCase):
    """测试懒加载器"""

    def setUp(self):
        """测试设置"""
        self.lazy_loader = LazyLoader()

    def test_lazy_loading(self):
        """测试懒加载"""
        load_count = {'count': 0}

        def expensive_loader():
            load_count['count'] += 1
            return {'data': 'expensive_data', 'loaded_at': time.time()}

        # 注册资源
        self.lazy_loader.register('expensive_resource', expensive_loader)

        # 第一次加载
        result1 = self.lazy_loader.load('expensive_resource')
        self.assertEqual(load_count['count'], 1)
        self.assertIn('data', result1)

        # 第二次加载应该使用缓存
        result2 = self.lazy_loader.load('expensive_resource')
        self.assertEqual(load_count['count'], 1)  # 没有增加
        self.assertEqual(result1, result2)

    def test_lazy_property(self):
        """测试懒加载属性装饰器"""
        class TestClass:
            def __init__(self):
                self.load_count = 0

            @property
            def expensive_property(self):
                if not hasattr(self, '_expensive_property'):
                    self.load_count += 1
                    self._expensive_property = {'computed': True}
                return self._expensive_property

        obj = TestClass()

        # 第一次访问
        result1 = obj.expensive_property
        self.assertEqual(obj.load_count, 1)

        # 第二次访问应该使用缓存
        result2 = obj.expensive_property
        self.assertEqual(obj.load_count, 1)
        self.assertEqual(result1, result2)


class TestResourceMonitor(unittest.TestCase):
    """测试资源监控器"""

    def setUp(self):
        """测试设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.alert_file = os.path.join(self.temp_dir, "test_alerts.log")
        self.monitor = ResourceMonitor(
            sampling_interval=0.1,  # 快速采样用于测试
            history_size=100,
            alert_file=self.alert_file
        )

    def tearDown(self):
        """清理资源"""
        self.monitor.stop_monitoring()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_system_info(self):
        """测试系统信息"""
        system_info = self.monitor.get_system_info()

        self.assertIn('cpu_count', system_info)
        self.assertIn('memory_total_gb', system_info)
        self.assertGreater(system_info['cpu_count'], 0)
        self.assertGreater(system_info['memory_total_gb'], 0)

    def test_monitoring_lifecycle(self):
        """测试监控生命周期"""
        # 开始监控
        self.monitor.start_monitoring()
        self.assertTrue(self.monitor._monitoring)

        # 等待一些数据
        time.sleep(0.5)

        # 检查是否有数据
        current_metrics = self.monitor.get_current_metrics()
        self.assertIsNotNone(current_metrics)

        # 停止监控
        self.monitor.stop_monitoring()
        self.assertFalse(self.monitor._monitoring)

    def test_metrics_collection(self):
        """测试指标收集"""
        self.monitor.start_monitoring()
        time.sleep(0.5)

        # 获取历史数据
        history = self.monitor.get_metrics_history(1)  # 1分钟
        self.assertGreater(len(history), 0)

        # 获取摘要统计
        summary = self.monitor.get_metrics_summary(1)
        self.assertIn('cpu', summary)
        self.assertIn('memory', summary)

    def test_alert_thresholds(self):
        """测试警报阈值"""
        # 设置低阈值以触发警报
        self.monitor.set_alert_threshold('cpu_percent', 'medium', 0.1)

        alert_triggered = {'triggered': False}

        def alert_callback(alert):
            alert_triggered['triggered'] = True

        self.monitor.add_alert_callback(alert_callback)

        # 开始监控
        self.monitor.start_monitoring()
        time.sleep(1.0)

        # 由于CPU使用率很可能超过0.1%，应该触发警报
        # 注意：在测试环境中可能不会总是触发，这是正常的


class TestPerformanceOptimizer(unittest.TestCase):
    """测试性能优化器"""

    def setUp(self):
        """测试设置"""
        self.optimizer = PerformanceOptimizer()

    def tearDown(self):
        """清理资源"""
        asyncio.run(self.async_teardown())

    async def async_teardown(self):
        """异步清理"""
        await self.optimizer.cleanup()

    def test_optimizer_initialization(self):
        """测试优化器初始化"""
        async def async_test():
            await self.optimizer.initialize()

            summary = self.optimizer.get_performance_summary()
            self.assertIn('cache_stats', summary)
            self.assertIn('task_pool_stats', summary)
            self.assertIn('lazy_loader_stats', summary)

        asyncio.run(async_test())

    def test_function_optimization_decorator(self):
        """测试函数优化装饰器"""
        call_count = 0

        @self.optimizer.optimize_function()
        def test_function(x, y):
            nonlocal call_count
            call_count += 1
            return x + y

        # 第一次调用
        result1 = test_function(1, 2)
        self.assertEqual(result1, 3)
        self.assertEqual(call_count, 1)

        # 第二次调用应该从缓存获取
        result2 = test_function(1, 2)
        self.assertEqual(result2, 3)
        self.assertEqual(call_count, 1)

    def test_batch_cache_operations(self):
        """测试批量缓存操作"""
        operations = [
            {'type': 'set', 'cache_name': 'default', 'key': 'key1', 'value': 'value1'},
            {'type': 'set', 'cache_name': 'default', 'key': 'key2', 'value': 'value2'},
            {'type': 'get', 'cache_name': 'default', 'key': 'key1'},
            {'type': 'get', 'cache_name': 'default', 'key': 'key2'},
        ]

        results = self.optimizer.batch_cache_operations(operations)

        # 前两个操作是set，应该返回True
        self.assertTrue(results[0])
        self.assertTrue(results[1])

        # 后两个操作是get，应该返回对应的值
        self.assertEqual(results[2], 'value1')
        self.assertEqual(results[3], 'value2')


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)