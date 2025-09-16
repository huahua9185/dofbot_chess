"""
日志指标收集模块
提供日志相关的监控指标收集功能
"""

import time
import threading
from typing import Dict, Any, Optional
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class LogMetrics:
    """日志指标数据结构"""
    total_logs: int = 0
    error_logs: int = 0
    warning_logs: int = 0
    info_logs: int = 0
    debug_logs: int = 0
    avg_log_rate: float = 0.0
    recent_errors: deque = field(default_factory=lambda: deque(maxlen=100))
    start_time: datetime = field(default_factory=datetime.now)


class LogMetricsCollector:
    """
    日志指标收集器
    收集和统计日志相关指标，用于监控和告警
    """

    def __init__(self, window_size: int = 3600):  # 1小时窗口
        self.window_size = window_size
        self.metrics = defaultdict(LogMetrics)
        self.log_timestamps = defaultdict(lambda: deque(maxlen=1000))
        self.lock = threading.RLock()

    def record_log(
        self,
        service_name: str,
        level: str,
        message: str,
        extra: Dict[str, Any] = None
    ):
        """
        记录日志事件

        Args:
            service_name: 服务名称
            level: 日志级别
            message: 日志消息
            extra: 额外信息
        """
        with self.lock:
            now = datetime.now()
            metrics = self.metrics[service_name]

            # 更新计数
            metrics.total_logs += 1

            # 按级别统计
            level_lower = level.lower()
            if level_lower == 'error':
                metrics.error_logs += 1
                # 记录最近的错误
                metrics.recent_errors.append({
                    'timestamp': now,
                    'message': message,
                    'extra': extra or {}
                })
            elif level_lower == 'warning':
                metrics.warning_logs += 1
            elif level_lower == 'info':
                metrics.info_logs += 1
            elif level_lower == 'debug':
                metrics.debug_logs += 1

            # 记录时间戳用于计算速率
            self.log_timestamps[service_name].append(now)

            # 更新平均日志速率
            self._update_log_rate(service_name)

    def get_metrics(self, service_name: str) -> LogMetrics:
        """
        获取服务的日志指标

        Args:
            service_name: 服务名称

        Returns:
            日志指标对象
        """
        with self.lock:
            return self.metrics[service_name]

    def get_all_metrics(self) -> Dict[str, LogMetrics]:
        """
        获取所有服务的日志指标

        Returns:
            服务名到指标的映射
        """
        with self.lock:
            return dict(self.metrics)

    def get_error_rate(self, service_name: str, time_window: int = 300) -> float:
        """
        获取指定时间窗口内的错误率

        Args:
            service_name: 服务名称
            time_window: 时间窗口(秒)

        Returns:
            错误率(0-1之间的浮点数)
        """
        with self.lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=time_window)

            timestamps = self.log_timestamps[service_name]
            recent_logs = [ts for ts in timestamps if ts >= cutoff]

            if not recent_logs:
                return 0.0

            metrics = self.metrics[service_name]
            recent_errors = [err for err in metrics.recent_errors if err['timestamp'] >= cutoff]

            return len(recent_errors) / len(recent_logs)

    def get_log_rate(self, service_name: str, time_window: int = 300) -> float:
        """
        获取指定时间窗口内的日志速率

        Args:
            service_name: 服务名称
            time_window: 时间窗口(秒)

        Returns:
            日志速率(日志/秒)
        """
        with self.lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=time_window)

            timestamps = self.log_timestamps[service_name]
            recent_logs = [ts for ts in timestamps if ts >= cutoff]

            if not recent_logs:
                return 0.0

            return len(recent_logs) / time_window

    def _update_log_rate(self, service_name: str):
        """更新平均日志速率"""
        metrics = self.metrics[service_name]
        duration = (datetime.now() - metrics.start_time).total_seconds()

        if duration > 0:
            metrics.avg_log_rate = metrics.total_logs / duration

    def reset_metrics(self, service_name: str = None):
        """
        重置指标

        Args:
            service_name: 服务名称，None表示重置所有服务
        """
        with self.lock:
            if service_name:
                if service_name in self.metrics:
                    self.metrics[service_name] = LogMetrics()
                    self.log_timestamps[service_name].clear()
            else:
                self.metrics.clear()
                self.log_timestamps.clear()

    def export_prometheus_metrics(self) -> str:
        """
        导出Prometheus格式的指标

        Returns:
            Prometheus格式的指标字符串
        """
        with self.lock:
            lines = []

            # 添加帮助信息
            lines.append("# HELP chess_logs_total Total number of logs by service and level")
            lines.append("# TYPE chess_logs_total counter")

            for service_name, metrics in self.metrics.items():
                lines.append(f'chess_logs_total{{service="{service_name}",level="error"}} {metrics.error_logs}')
                lines.append(f'chess_logs_total{{service="{service_name}",level="warning"}} {metrics.warning_logs}')
                lines.append(f'chess_logs_total{{service="{service_name}",level="info"}} {metrics.info_logs}')
                lines.append(f'chess_logs_total{{service="{service_name}",level="debug"}} {metrics.debug_logs}')

            lines.append("# HELP chess_log_rate_avg Average log rate by service")
            lines.append("# TYPE chess_log_rate_avg gauge")

            for service_name, metrics in self.metrics.items():
                lines.append(f'chess_log_rate_avg{{service="{service_name}"}} {metrics.avg_log_rate:.2f}')

            lines.append("# HELP chess_error_rate Current error rate by service")
            lines.append("# TYPE chess_error_rate gauge")

            for service_name in self.metrics.keys():
                error_rate = self.get_error_rate(service_name)
                lines.append(f'chess_error_rate{{service="{service_name}"}} {error_rate:.4f}')

            return '\n'.join(lines) + '\n'

    def get_summary(self) -> Dict[str, Any]:
        """
        获取指标摘要

        Returns:
            包含摘要信息的字典
        """
        with self.lock:
            summary = {
                'total_services': len(self.metrics),
                'services': {}
            }

            for service_name, metrics in self.metrics.items():
                summary['services'][service_name] = {
                    'total_logs': metrics.total_logs,
                    'error_logs': metrics.error_logs,
                    'warning_logs': metrics.warning_logs,
                    'info_logs': metrics.info_logs,
                    'debug_logs': metrics.debug_logs,
                    'avg_log_rate': round(metrics.avg_log_rate, 2),
                    'current_error_rate': round(self.get_error_rate(service_name), 4),
                    'recent_error_count': len(metrics.recent_errors),
                    'uptime_seconds': (datetime.now() - metrics.start_time).total_seconds()
                }

            return summary


# 全局日志指标收集器实例
log_metrics_collector = LogMetricsCollector()