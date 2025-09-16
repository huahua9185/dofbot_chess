# -*- coding: utf-8 -*-
"""
资源监控模块
监控系统资源使用情况，提供性能分析和预警
"""

import time
import threading
import asyncio
from typing import Dict, List, Any, Optional, Callable, NamedTuple
from dataclasses import dataclass, asdict
from collections import deque, defaultdict
from datetime import datetime, timedelta
from enum import Enum
import psutil
import os
import json
from pathlib import Path

# 导入GPU监控（如果可用）
try:
    import pynvml
    NVIDIA_GPU_AVAILABLE = True
except ImportError:
    NVIDIA_GPU_AVAILABLE = False


class AlertLevel(Enum):
    """警报级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SystemMetrics:
    """系统指标数据"""
    timestamp: datetime
    cpu_percent: float
    cpu_freq: float
    cpu_temp: Optional[float]
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    swap_percent: float
    disk_usage_percent: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float
    gpu_percent: Optional[float] = None
    gpu_memory_percent: Optional[float] = None
    gpu_temp: Optional[float] = None
    load_average: Optional[List[float]] = None
    process_count: int = 0
    thread_count: int = 0


@dataclass
class ProcessMetrics:
    """进程指标数据"""
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    num_threads: int
    status: str
    create_time: float


@dataclass
class ResourceAlert:
    """资源警报"""
    timestamp: datetime
    level: AlertLevel
    metric_name: str
    current_value: float
    threshold: float
    message: str
    duration: Optional[timedelta] = None


class PerformanceProfiler:
    """性能分析器"""

    def __init__(self):
        """初始化性能分析器"""
        self._profiles: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._active_profiles: Dict[str, Dict[str, Any]] = {}

    def start_profile(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """开始性能分析"""
        profile_data = {
            'start_time': time.time(),
            'start_memory': self._get_memory_usage(),
            'start_cpu': psutil.Process().cpu_percent(),
            'metadata': metadata or {}
        }
        self._active_profiles[name] = profile_data

    def end_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """结束性能分析"""
        if name not in self._active_profiles:
            return None

        profile_data = self._active_profiles[name]
        end_time = time.time()
        end_memory = self._get_memory_usage()
        end_cpu = psutil.Process().cpu_percent()

        result = {
            'name': name,
            'duration': end_time - profile_data['start_time'],
            'memory_delta': end_memory - profile_data['start_memory'],
            'cpu_usage': (profile_data['start_cpu'] + end_cpu) / 2,
            'start_time': datetime.fromtimestamp(profile_data['start_time']),
            'end_time': datetime.fromtimestamp(end_time),
            'metadata': profile_data['metadata']
        }

        self._profiles[name].append(result)
        del self._active_profiles[name]

        # 只保留最近100条记录
        if len(self._profiles[name]) > 100:
            self._profiles[name] = self._profiles[name][-100:]

        return result

    def get_profile_stats(self, name: str) -> Dict[str, Any]:
        """获取性能分析统计"""
        if name not in self._profiles or not self._profiles[name]:
            return {}

        profiles = self._profiles[name]
        durations = [p['duration'] for p in profiles]
        memory_deltas = [p['memory_delta'] for p in profiles]

        return {
            'count': len(profiles),
            'avg_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'avg_memory_delta': sum(memory_deltas) / len(memory_deltas),
            'total_memory_delta': sum(memory_deltas),
            'last_run': profiles[-1]['end_time'].isoformat() if profiles else None
        }

    def _get_memory_usage(self) -> float:
        """获取当前进程内存使用量（MB）"""
        return psutil.Process().memory_info().rss / 1024 / 1024

    def profile_decorator(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """性能分析装饰器"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                self.start_profile(name, metadata)
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    self.end_profile(name)
            return wrapper
        return decorator

    async def profile_async_decorator(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """异步性能分析装饰器"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                self.start_profile(name, metadata)
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    self.end_profile(name)
            return wrapper
        return decorator


class ResourceMonitor:
    """系统资源监控器"""

    def __init__(self,
                 sampling_interval: float = 5.0,
                 history_size: int = 1440,  # 24小时的5秒采样
                 alert_file: Optional[str] = None):
        """
        初始化资源监控器

        Args:
            sampling_interval: 采样间隔（秒）
            history_size: 历史数据保留条数
            alert_file: 警报日志文件路径
        """
        self.sampling_interval = sampling_interval
        self.history_size = history_size
        self.alert_file = Path(alert_file) if alert_file else None

        # 数据存储
        self.metrics_history: deque[SystemMetrics] = deque(maxlen=history_size)
        self.alerts_history: deque[ResourceAlert] = deque(maxlen=1000)

        # 监控控制
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None

        # 警报规则
        self.alert_thresholds = {
            'cpu_percent': {'medium': 70, 'high': 85, 'critical': 95},
            'memory_percent': {'medium': 70, 'high': 85, 'critical': 95},
            'disk_usage_percent': {'medium': 80, 'high': 90, 'critical': 95},
            'cpu_temp': {'medium': 70, 'high': 80, 'critical': 90},
            'gpu_temp': {'medium': 75, 'high': 85, 'critical': 95}
        }

        # 警报回调
        self.alert_callbacks: List[Callable[[ResourceAlert], None]] = []

        # 性能分析器
        self.profiler = PerformanceProfiler()

        # 初始化GPU监控
        self._init_gpu_monitoring()

        # 基准测试数据
        self._baseline_metrics: Optional[SystemMetrics] = None

    def _init_gpu_monitoring(self):
        """初始化GPU监控"""
        self.gpu_available = False
        if NVIDIA_GPU_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self.gpu_count = pynvml.nvmlDeviceGetCount()
                self.gpu_available = self.gpu_count > 0
            except Exception:
                self.gpu_available = False

    def start_monitoring(self):
        """开始监控"""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop_monitoring(self):
        """停止监控"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

    def _monitor_loop(self):
        """监控主循环"""
        last_disk_io = psutil.disk_io_counters()
        last_network_io = psutil.net_io_counters()
        last_time = time.time()

        while self._monitoring:
            try:
                # 收集系统指标
                metrics = self._collect_system_metrics(last_disk_io, last_network_io, last_time)

                # 更新历史数据
                self.metrics_history.append(metrics)

                # 检查警报
                self._check_alerts(metrics)

                # 更新基线数据
                current_time = time.time()
                last_disk_io = psutil.disk_io_counters()
                last_network_io = psutil.net_io_counters()
                last_time = current_time

                # 等待下次采样
                time.sleep(self.sampling_interval)

            except Exception as e:
                print(f"监控循环出错: {e}")
                time.sleep(self.sampling_interval)

    def _collect_system_metrics(self, last_disk_io, last_network_io, last_time) -> SystemMetrics:
        """收集系统指标"""
        current_time = time.time()
        time_delta = current_time - last_time

        # CPU指标
        cpu_percent = psutil.cpu_percent()
        cpu_freq = psutil.cpu_freq().current if psutil.cpu_freq() else 0

        # 温度（如果可用）
        cpu_temp = None
        try:
            temps = psutil.sensors_temperatures()
            if 'coretemp' in temps:
                cpu_temp = temps['coretemp'][0].current
            elif 'cpu_thermal' in temps:  # Jetson
                cpu_temp = temps['cpu_thermal'][0].current
        except Exception:
            pass

        # 内存指标
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # 磁盘指标
        disk_usage = psutil.disk_usage('/')
        current_disk_io = psutil.disk_io_counters()

        disk_io_read_mb = 0
        disk_io_write_mb = 0
        if last_disk_io and time_delta > 0:
            disk_io_read_mb = (current_disk_io.read_bytes - last_disk_io.read_bytes) / (1024**2) / time_delta
            disk_io_write_mb = (current_disk_io.write_bytes - last_disk_io.write_bytes) / (1024**2) / time_delta

        # 网络指标
        current_network_io = psutil.net_io_counters()

        network_sent_mb = 0
        network_recv_mb = 0
        if last_network_io and time_delta > 0:
            network_sent_mb = (current_network_io.bytes_sent - last_network_io.bytes_sent) / (1024**2) / time_delta
            network_recv_mb = (current_network_io.bytes_recv - last_network_io.bytes_recv) / (1024**2) / time_delta

        # 负载平均（Linux）
        load_average = None
        try:
            load_average = list(os.getloadavg())
        except (OSError, AttributeError):
            pass

        # 进程和线程数量
        process_count = len(psutil.pids())
        thread_count = sum(p.num_threads() for p in psutil.process_iter(['num_threads']) if p.info['num_threads'])

        # GPU指标
        gpu_percent = None
        gpu_memory_percent = None
        gpu_temp = None

        if self.gpu_available:
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)  # 使用第一块GPU
                gpu_util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_percent = gpu_util.gpu

                gpu_memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_memory_percent = (gpu_memory.used / gpu_memory.total) * 100

                gpu_temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except Exception:
                pass

        return SystemMetrics(
            timestamp=datetime.fromtimestamp(current_time),
            cpu_percent=cpu_percent,
            cpu_freq=cpu_freq,
            cpu_temp=cpu_temp,
            memory_percent=memory.percent,
            memory_used_mb=memory.used / (1024**2),
            memory_available_mb=memory.available / (1024**2),
            swap_percent=swap.percent,
            disk_usage_percent=disk_usage.percent,
            disk_io_read_mb=disk_io_read_mb,
            disk_io_write_mb=disk_io_write_mb,
            network_sent_mb=network_sent_mb,
            network_recv_mb=network_recv_mb,
            gpu_percent=gpu_percent,
            gpu_memory_percent=gpu_memory_percent,
            gpu_temp=gpu_temp,
            load_average=load_average,
            process_count=process_count,
            thread_count=thread_count
        )

    def _check_alerts(self, metrics: SystemMetrics):
        """检查警报条件"""
        alerts = []

        # 检查各项指标
        for metric_name, thresholds in self.alert_thresholds.items():
            metric_value = getattr(metrics, metric_name, None)
            if metric_value is None:
                continue

            # 确定警报级别
            alert_level = None
            if metric_value >= thresholds.get('critical', float('inf')):
                alert_level = AlertLevel.CRITICAL
            elif metric_value >= thresholds.get('high', float('inf')):
                alert_level = AlertLevel.HIGH
            elif metric_value >= thresholds.get('medium', float('inf')):
                alert_level = AlertLevel.MEDIUM

            if alert_level:
                threshold = thresholds.get(alert_level.value, 0)
                alert = ResourceAlert(
                    timestamp=metrics.timestamp,
                    level=alert_level,
                    metric_name=metric_name,
                    current_value=metric_value,
                    threshold=threshold,
                    message=f"{metric_name} 达到 {alert_level.value} 级别: {metric_value:.1f}% (阈值: {threshold}%)"
                )
                alerts.append(alert)

        # 处理警报
        for alert in alerts:
            self._handle_alert(alert)

    def _handle_alert(self, alert: ResourceAlert):
        """处理警报"""
        # 添加到历史记录
        self.alerts_history.append(alert)

        # 写入日志文件
        if self.alert_file:
            try:
                with open(self.alert_file, 'a', encoding='utf-8') as f:
                    alert_data = asdict(alert)
                    alert_data['timestamp'] = alert.timestamp.isoformat()
                    f.write(json.dumps(alert_data, ensure_ascii=False) + '\n')
            except Exception:
                pass

        # 调用回调函数
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception:
                pass

    def get_current_metrics(self) -> Optional[SystemMetrics]:
        """获取最新的系统指标"""
        return self.metrics_history[-1] if self.metrics_history else None

    def get_metrics_history(self, minutes: int = 60) -> List[SystemMetrics]:
        """获取指定时间范围的历史指标"""
        if not self.metrics_history:
            return []

        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        return [m for m in self.metrics_history if m.timestamp >= cutoff_time]

    def get_metrics_summary(self, minutes: int = 60) -> Dict[str, Any]:
        """获取指标摘要统计"""
        history = self.get_metrics_history(minutes)
        if not history:
            return {}

        # 计算统计值
        cpu_values = [m.cpu_percent for m in history]
        memory_values = [m.memory_percent for m in history]
        disk_values = [m.disk_usage_percent for m in history]

        summary = {
            'time_range_minutes': minutes,
            'sample_count': len(history),
            'cpu': {
                'avg': sum(cpu_values) / len(cpu_values),
                'min': min(cpu_values),
                'max': max(cpu_values)
            },
            'memory': {
                'avg': sum(memory_values) / len(memory_values),
                'min': min(memory_values),
                'max': max(memory_values)
            },
            'disk': {
                'avg': sum(disk_values) / len(disk_values),
                'min': min(disk_values),
                'max': max(disk_values)
            }
        }

        # GPU统计（如果可用）
        gpu_values = [m.gpu_percent for m in history if m.gpu_percent is not None]
        if gpu_values:
            summary['gpu'] = {
                'avg': sum(gpu_values) / len(gpu_values),
                'min': min(gpu_values),
                'max': max(gpu_values)
            }

        return summary

    def get_top_processes(self, limit: int = 10, sort_by: str = 'memory_percent') -> List[ProcessMetrics]:
        """获取资源使用最多的进程"""
        processes = []

        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info', 'num_threads', 'status', 'create_time']):
            try:
                pinfo = proc.info
                process_metrics = ProcessMetrics(
                    pid=pinfo['pid'],
                    name=pinfo['name'],
                    cpu_percent=pinfo['cpu_percent'] or 0,
                    memory_percent=pinfo['memory_percent'] or 0,
                    memory_mb=(pinfo['memory_info'].rss / (1024**2)) if pinfo['memory_info'] else 0,
                    num_threads=pinfo['num_threads'] or 0,
                    status=pinfo['status'],
                    create_time=pinfo['create_time'] or 0
                )
                processes.append(process_metrics)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # 排序并返回前N个
        processes.sort(key=lambda x: getattr(x, sort_by), reverse=True)
        return processes[:limit]

    def get_recent_alerts(self, hours: int = 24) -> List[ResourceAlert]:
        """获取最近的警报"""
        if not self.alerts_history:
            return []

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [alert for alert in self.alerts_history if alert.timestamp >= cutoff_time]

    def add_alert_callback(self, callback: Callable[[ResourceAlert], None]):
        """添加警报回调函数"""
        self.alert_callbacks.append(callback)

    def set_alert_threshold(self, metric_name: str, level: str, threshold: float):
        """设置警报阈值"""
        if metric_name not in self.alert_thresholds:
            self.alert_thresholds[metric_name] = {}
        self.alert_thresholds[metric_name][level] = threshold

    def export_metrics(self, filepath: str, hours: int = 24):
        """导出指标数据到文件"""
        history = self.get_metrics_history(hours * 60)

        data = {
            'export_time': datetime.utcnow().isoformat(),
            'time_range_hours': hours,
            'metrics': [asdict(m) for m in history]
        }

        # 转换datetime为字符串
        for metric in data['metrics']:
            metric['timestamp'] = metric['timestamp'].isoformat()

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        return {
            'platform': psutil.WINDOWS if psutil.WINDOWS else 'linux',
            'cpu_count': psutil.cpu_count(),
            'cpu_count_logical': psutil.cpu_count(logical=True),
            'memory_total_gb': psutil.virtual_memory().total / (1024**3),
            'disk_total_gb': psutil.disk_usage('/').total / (1024**3),
            'gpu_available': self.gpu_available,
            'gpu_count': getattr(self, 'gpu_count', 0),
            'monitoring_active': self._monitoring,
            'sampling_interval': self.sampling_interval
        }