# -*- coding: utf-8 -*-
"""
性能监控服务主模块
提供系统性能监控、资源管理和性能优化API
"""

import sys
import os
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# 导入共享模块
from shared.logging_config import get_logger
from shared.redis_client import RedisClient
from shared.performance import (
    MemoryManager,
    ResourceMonitor,
    PerformanceOptimizer,
    AlertLevel,
    SystemMetrics,
    ResourceAlert
)

# 配置日志
logger = get_logger(__name__)


# Pydantic模型
class PerformanceMetricsRequest(BaseModel):
    hours: int = Field(default=1, ge=1, le=168)  # 1小时到1周


class AlertThresholdRequest(BaseModel):
    metric_name: str
    level: str
    threshold: float


class CacheOperationRequest(BaseModel):
    cache_name: str
    operations: List[Dict[str, Any]]


class OptimizationRequest(BaseModel):
    target: str = Field(default="memory")  # memory, cache, gc
    aggressive: bool = Field(default=False)


class PerformanceServiceApp:
    """性能监控服务应用"""

    def __init__(self):
        self.app = None
        self.memory_manager = None
        self.resource_monitor = None
        self.performance_optimizer = None
        self.redis_client = None

    async def initialize(self):
        """初始化服务组件"""
        try:
            logger.info("初始化性能监控服务...")

            # 初始化Redis客户端
            self.redis_client = RedisClient()
            await self.redis_client.connect()

            # 初始化内存管理器（为Jetson 4GB内存优化）
            self.memory_manager = MemoryManager(memory_limit_mb=3072)

            # 初始化资源监控器
            self.resource_monitor = ResourceMonitor(
                sampling_interval=10.0,  # 10秒采样
                history_size=8640,  # 24小时历史数据
                alert_file="/app/logs/performance_alerts.log"
            )

            # 初始化性能优化器
            self.performance_optimizer = PerformanceOptimizer()
            await self.performance_optimizer.initialize()

            # 设置内存警报回调
            self.memory_manager.add_memory_alert(self._handle_memory_alert)

            # 设置资源监控警报回调
            self.resource_monitor.add_alert_callback(self._handle_resource_alert)

            # 启动资源监控
            self.resource_monitor.start_monitoring()

            # 创建常用对象池
            self._create_object_pools()

            # 注册懒加载资源
            self._register_lazy_resources()

            logger.info("性能监控服务初始化完成")

        except Exception as e:
            logger.error(f"性能监控服务初始化失败: {e}")
            raise

    async def cleanup(self):
        """清理资源"""
        try:
            if self.resource_monitor:
                self.resource_monitor.stop_monitoring()

            if self.performance_optimizer:
                await self.performance_optimizer.cleanup()

            if self.redis_client:
                await self.redis_client.close()

            logger.info("性能监控服务清理完成")

        except Exception as e:
            logger.error(f"性能监控服务清理失败: {e}")

    def _create_object_pools(self):
        """创建常用对象池"""
        # 创建字典对象池
        self.memory_manager.create_pool(
            'dict_pool',
            factory=dict,
            max_size=100,
            reset_func=lambda d: d.clear()
        )

        # 创建列表对象池
        self.memory_manager.create_pool(
            'list_pool',
            factory=list,
            max_size=100,
            reset_func=lambda l: l.clear()
        )

    def _register_lazy_resources(self):
        """注册懒加载资源"""
        # 注册一些示例懒加载资源
        self.performance_optimizer.register_lazy_resource(
            'heavy_model',
            lambda: self._load_heavy_model()
        )

    def _load_heavy_model(self):
        """模拟加载重型模型"""
        logger.info("Loading heavy model...")
        # 这里可以加载实际的ML模型
        return {"model": "heavy_model_placeholder", "loaded_at": datetime.utcnow()}

    def _handle_memory_alert(self, memory_stats):
        """处理内存警报"""
        if memory_stats.memory_percent > 90:
            logger.warning(f"高内存使用警报: {memory_stats.memory_percent:.1f}%")

            # 执行内存优化
            optimization_results = self.memory_manager.optimize_memory()
            logger.info(f"内存优化结果: {optimization_results}")

    def _handle_resource_alert(self, alert: ResourceAlert):
        """处理资源警报"""
        logger.warning(f"资源警报: {alert.message}")

        # 根据警报类型执行相应优化
        if alert.metric_name == 'memory_percent' and alert.level in [AlertLevel.HIGH, AlertLevel.CRITICAL]:
            # 触发内存优化
            optimization_results = self.memory_manager.optimize_memory()
            logger.info(f"触发内存优化: {optimization_results}")

    def create_app(self) -> FastAPI:
        """创建FastAPI应用"""
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """应用生命周期管理"""
            await self.initialize()
            yield
            await self.cleanup()

        app = FastAPI(
            title="智能象棋机器人性能监控服务",
            description="提供系统性能监控、资源管理和性能优化功能",
            version="1.0.0",
            lifespan=lifespan
        )

        # 添加CORS中间件
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "https://localhost:3000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # 健康检查端点
        @app.get("/health")
        async def health_check():
            """健康检查"""
            current_metrics = self.resource_monitor.get_current_metrics()
            system_summary = self.memory_manager.get_system_summary()

            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "service": "performance_service",
                "version": "1.0.0",
                "system_health": {
                    "memory_usage_percent": system_summary['memory_stats']['usage_percent'],
                    "memory_pressure": system_summary['memory_pressure'],
                    "cpu_percent": current_metrics.cpu_percent if current_metrics else 0,
                    "monitoring_active": self.resource_monitor._monitoring
                }
            }

        # 系统指标端点
        @app.get("/api/performance/metrics/current")
        async def get_current_metrics():
            """获取当前系统指标"""
            try:
                metrics = self.resource_monitor.get_current_metrics()
                if not metrics:
                    raise HTTPException(status_code=404, detail="没有可用的指标数据")

                return {
                    "success": True,
                    "metrics": {
                        "timestamp": metrics.timestamp.isoformat(),
                        "cpu_percent": metrics.cpu_percent,
                        "cpu_freq": metrics.cpu_freq,
                        "cpu_temp": metrics.cpu_temp,
                        "memory_percent": metrics.memory_percent,
                        "memory_used_mb": metrics.memory_used_mb,
                        "memory_available_mb": metrics.memory_available_mb,
                        "swap_percent": metrics.swap_percent,
                        "disk_usage_percent": metrics.disk_usage_percent,
                        "gpu_percent": metrics.gpu_percent,
                        "gpu_memory_percent": metrics.gpu_memory_percent,
                        "gpu_temp": metrics.gpu_temp,
                        "load_average": metrics.load_average,
                        "process_count": metrics.process_count,
                        "thread_count": metrics.thread_count
                    }
                }
            except Exception as e:
                logger.error(f"获取当前指标失败: {e}")
                raise HTTPException(status_code=500, detail=f"获取指标失败: {str(e)}")

        @app.get("/api/performance/metrics/history")
        async def get_metrics_history(hours: int = 1):
            """获取历史指标数据"""
            try:
                if hours < 1 or hours > 168:  # 最多1周
                    raise HTTPException(status_code=400, detail="时间范围必须在1-168小时之间")

                history = self.resource_monitor.get_metrics_history(hours * 60)
                summary = self.resource_monitor.get_metrics_summary(hours * 60)

                return {
                    "success": True,
                    "time_range_hours": hours,
                    "sample_count": len(history),
                    "summary": summary,
                    "data": [
                        {
                            "timestamp": m.timestamp.isoformat(),
                            "cpu_percent": m.cpu_percent,
                            "memory_percent": m.memory_percent,
                            "disk_usage_percent": m.disk_usage_percent,
                            "gpu_percent": m.gpu_percent
                        }
                        for m in history
                    ]
                }
            except Exception as e:
                logger.error(f"获取历史指标失败: {e}")
                raise HTTPException(status_code=500, detail=f"获取历史指标失败: {str(e)}")

        @app.get("/api/performance/processes/top")
        async def get_top_processes(limit: int = 10, sort_by: str = "memory_percent"):
            """获取资源使用最多的进程"""
            try:
                if limit < 1 or limit > 50:
                    raise HTTPException(status_code=400, detail="limit必须在1-50之间")

                if sort_by not in ['memory_percent', 'cpu_percent', 'memory_mb']:
                    raise HTTPException(status_code=400, detail="不支持的排序字段")

                processes = self.resource_monitor.get_top_processes(limit, sort_by)

                return {
                    "success": True,
                    "processes": [
                        {
                            "pid": p.pid,
                            "name": p.name,
                            "cpu_percent": p.cpu_percent,
                            "memory_percent": p.memory_percent,
                            "memory_mb": p.memory_mb,
                            "num_threads": p.num_threads,
                            "status": p.status
                        }
                        for p in processes
                    ]
                }
            except Exception as e:
                logger.error(f"获取进程信息失败: {e}")
                raise HTTPException(status_code=500, detail=f"获取进程信息失败: {str(e)}")

        # 内存管理端点
        @app.get("/api/performance/memory/status")
        async def get_memory_status():
            """获取内存状态"""
            try:
                memory_stats = self.memory_manager.get_memory_stats()
                system_summary = self.memory_manager.get_system_summary()
                memory_usage_by_type = self.memory_manager.get_memory_usage_by_type()

                return {
                    "success": True,
                    "memory_stats": {
                        "total_gb": round(memory_stats.total_memory / (1024**3), 2),
                        "used_gb": round(memory_stats.used_memory / (1024**3), 2),
                        "available_gb": round(memory_stats.available_memory / (1024**3), 2),
                        "usage_percent": memory_stats.memory_percent,
                        "swap_used_mb": round(memory_stats.swap_used / (1024**2), 2),
                        "cache_memory_mb": round(memory_stats.cache_memory / (1024**2), 2)
                    },
                    "system_summary": system_summary,
                    "memory_usage_by_type": memory_usage_by_type
                }
            except Exception as e:
                logger.error(f"获取内存状态失败: {e}")
                raise HTTPException(status_code=500, detail=f"获取内存状态失败: {str(e)}")

        @app.post("/api/performance/memory/optimize")
        async def optimize_memory():
            """优化内存使用"""
            try:
                optimization_results = self.memory_manager.optimize_memory()
                return {
                    "success": True,
                    "optimization_results": optimization_results,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"内存优化失败: {e}")
                raise HTTPException(status_code=500, detail=f"内存优化失败: {str(e)}")

        # 缓存管理端点
        @app.get("/api/performance/cache/stats")
        async def get_cache_stats():
            """获取缓存统计"""
            try:
                performance_summary = self.performance_optimizer.get_performance_summary()
                return {
                    "success": True,
                    "cache_stats": performance_summary['cache_stats'],
                    "task_pool_stats": performance_summary['task_pool_stats'],
                    "lazy_loader_stats": performance_summary['lazy_loader_stats']
                }
            except Exception as e:
                logger.error(f"获取缓存统计失败: {e}")
                raise HTTPException(status_code=500, detail=f"获取缓存统计失败: {str(e)}")

        @app.post("/api/performance/cache/operations")
        async def batch_cache_operations(request: CacheOperationRequest):
            """批量缓存操作"""
            try:
                results = self.performance_optimizer.batch_cache_operations(request.operations)
                return {
                    "success": True,
                    "results": results,
                    "operations_count": len(request.operations)
                }
            except Exception as e:
                logger.error(f"批量缓存操作失败: {e}")
                raise HTTPException(status_code=500, detail=f"批量缓存操作失败: {str(e)}")

        @app.delete("/api/performance/cache/{cache_name}")
        async def clear_cache(cache_name: str):
            """清空指定缓存"""
            try:
                result = self.performance_optimizer.cache_manager.clear(cache_name)
                if result:
                    return {
                        "success": True,
                        "message": f"缓存 {cache_name} 已清空"
                    }
                else:
                    raise HTTPException(status_code=404, detail=f"缓存 {cache_name} 不存在")
            except Exception as e:
                logger.error(f"清空缓存失败: {e}")
                raise HTTPException(status_code=500, detail=f"清空缓存失败: {str(e)}")

        # 警报管理端点
        @app.get("/api/performance/alerts")
        async def get_alerts(hours: int = 24):
            """获取最近的警报"""
            try:
                if hours < 1 or hours > 168:
                    raise HTTPException(status_code=400, detail="时间范围必须在1-168小时之间")

                alerts = self.resource_monitor.get_recent_alerts(hours)
                return {
                    "success": True,
                    "alerts": [
                        {
                            "timestamp": alert.timestamp.isoformat(),
                            "level": alert.level.value,
                            "metric_name": alert.metric_name,
                            "current_value": alert.current_value,
                            "threshold": alert.threshold,
                            "message": alert.message
                        }
                        for alert in alerts
                    ],
                    "alert_count": len(alerts),
                    "time_range_hours": hours
                }
            except Exception as e:
                logger.error(f"获取警报失败: {e}")
                raise HTTPException(status_code=500, detail=f"获取警报失败: {str(e)}")

        @app.post("/api/performance/alerts/threshold")
        async def set_alert_threshold(request: AlertThresholdRequest):
            """设置警报阈值"""
            try:
                self.resource_monitor.set_alert_threshold(
                    request.metric_name,
                    request.level,
                    request.threshold
                )
                return {
                    "success": True,
                    "message": f"已设置 {request.metric_name} 的 {request.level} 级别阈值为 {request.threshold}"
                }
            except Exception as e:
                logger.error(f"设置警报阈值失败: {e}")
                raise HTTPException(status_code=500, detail=f"设置警报阈值失败: {str(e)}")

        # 性能分析端点
        @app.get("/api/performance/profile/{name}")
        async def get_profile_stats(name: str):
            """获取性能分析统计"""
            try:
                stats = self.resource_monitor.profiler.get_profile_stats(name)
                if not stats:
                    raise HTTPException(status_code=404, detail=f"性能分析 {name} 不存在")

                return {
                    "success": True,
                    "profile_name": name,
                    "stats": stats
                }
            except Exception as e:
                logger.error(f"获取性能分析统计失败: {e}")
                raise HTTPException(status_code=500, detail=f"获取性能分析统计失败: {str(e)}")

        # 系统信息端点
        @app.get("/api/performance/system/info")
        async def get_system_info():
            """获取系统信息"""
            try:
                system_info = self.resource_monitor.get_system_info()
                return {
                    "success": True,
                    "system_info": system_info,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"获取系统信息失败: {e}")
                raise HTTPException(status_code=500, detail=f"获取系统信息失败: {str(e)}")

        # 后台任务端点
        @app.post("/api/performance/optimize")
        async def run_optimization(request: OptimizationRequest, background_tasks: BackgroundTasks):
            """运行性能优化"""
            async def optimization_task():
                try:
                    results = {}

                    if request.target in ['memory', 'all']:
                        # 内存优化
                        memory_results = self.memory_manager.optimize_memory()
                        results['memory'] = memory_results

                    if request.target in ['cache', 'all']:
                        # 缓存优化
                        cache_stats = self.performance_optimizer.get_performance_summary()
                        results['cache'] = cache_stats['cache_stats']

                    logger.info(f"性能优化完成: {results}")
                    return results

                except Exception as e:
                    logger.error(f"性能优化失败: {e}")

            background_tasks.add_task(optimization_task)

            return {
                "success": True,
                "message": "性能优化任务已启动",
                "target": request.target,
                "aggressive": request.aggressive,
                "timestamp": datetime.utcnow().isoformat()
            }

        @app.post("/api/performance/export")
        async def export_metrics(hours: int = 24, background_tasks: BackgroundTasks):
            """导出性能指标数据"""
            async def export_task():
                try:
                    export_path = f"/app/data/performance_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
                    self.resource_monitor.export_metrics(export_path, hours)
                    logger.info(f"性能数据已导出到: {export_path}")
                except Exception as e:
                    logger.error(f"导出性能数据失败: {e}")

            background_tasks.add_task(export_task)

            return {
                "success": True,
                "message": "性能数据导出任务已启动",
                "time_range_hours": hours,
                "timestamp": datetime.utcnow().isoformat()
            }

        self.app = app
        return app

    def run(self, host: str = "0.0.0.0", port: int = 8008, **kwargs):
        """运行服务"""
        if not self.app:
            self.app = self.create_app()

        logger.info(f"启动性能监控服务在 {host}:{port}")
        uvicorn.run(self.app, host=host, port=port, **kwargs)


# 创建应用实例
performance_service = PerformanceServiceApp()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="智能象棋机器人性能监控服务")
    parser.add_argument("--host", default="0.0.0.0", help="服务主机地址")
    parser.add_argument("--port", type=int, default=8008, help="服务端口")
    parser.add_argument("--reload", action="store_true", help="启用自动重载")

    args = parser.parse_args()

    try:
        performance_service.run(
            host=args.host,
            port=args.port,
            reload=args.reload
        )
    except KeyboardInterrupt:
        logger.info("性能监控服务停止")
    except Exception as e:
        logger.error(f"性能监控服务运行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()