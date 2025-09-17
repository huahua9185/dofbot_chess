#!/usr/bin/env python3
"""
象棋机器人系统 - 严谨的服务监控程序
==================================

功能特性:
- 实时健康状态监控
- 服务异常检测和告警
- 自动恢复机制
- 性能指标收集
- 监控数据持久化
- Web界面展示
"""

import asyncio
import json
import time
import psutil
import logging
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, NamedTuple
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import signal
import sys
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/service_monitor.log')
    ]
)
logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """服务状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    STOPPED = "stopped"


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ServiceHealth:
    """服务健康状态"""
    name: str
    status: ServiceStatus
    last_check: datetime
    response_time: float
    error_message: Optional[str] = None
    uptime: Optional[float] = None
    restart_count: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['status'] = self.status.value
        data['last_check'] = self.last_check.isoformat()
        return data


@dataclass
class SystemMetrics:
    """系统指标"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_usage: float
    network_io: Dict[str, int]
    load_average: List[float]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class ServiceMonitor:
    """服务监控器"""

    def __init__(self):
        self.services = {
            'redis': {
                'type': 'docker',
                'container': 'chess_robot_redis',
                'health_check': self._check_redis_health,
                'port': 6379,
                'critical': True
            },
            'mongodb': {
                'type': 'docker',
                'container': 'chess_robot_mongodb',
                'health_check': self._check_mongodb_health,
                'port': 27017,
                'critical': True
            },
            'web_gateway': {
                'type': 'docker',
                'container': 'chess_robot_web_gateway',
                'health_check': self._check_web_gateway_health,
                'port': 8000,
                'critical': True,
                'endpoint': 'http://localhost:8000/api/v1/health'
            },
            'game_manager': {
                'type': 'docker',
                'container': 'chess_robot_game_manager',
                'health_check': self._check_container_health,
                'critical': True
            },
            'ai_engine': {
                'type': 'docker',
                'container': 'chess_robot_ai_engine',
                'health_check': self._check_container_health,
                'critical': True
            }
        }

        self.health_history: Dict[str, List[ServiceHealth]] = {}
        self.system_metrics_history: List[SystemMetrics] = []
        self.alerts: List[Dict[str, Any]] = []
        self.running = False
        self.check_interval = 10  # 秒
        self.max_history = 1000  # 保留最近1000条记录

        # 配置阈值
        self.thresholds = {
            'response_time': 5.0,  # 响应时间阈值(秒)
            'cpu_usage': 80.0,     # CPU使用率阈值(%)
            'memory_usage': 85.0,  # 内存使用率阈值(%)
            'disk_usage': 90.0,    # 磁盘使用率阈值(%)
            'restart_limit': 5     # 重启次数限制
        }

        # 初始化历史记录
        for service_name in self.services:
            self.health_history[service_name] = []

    async def start_monitoring(self):
        """开始监控"""
        logger.info("🚀 启动服务监控程序")
        self.running = True

        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            # 启动监控任务
            tasks = [
                asyncio.create_task(self._health_check_loop()),
                asyncio.create_task(self._system_metrics_loop()),
                asyncio.create_task(self._cleanup_loop()),
                asyncio.create_task(self._recovery_loop())
            ]

            await asyncio.gather(*tasks)

        except asyncio.CancelledError:
            logger.info("监控任务被取消")
        except Exception as e:
            logger.error(f"监控程序异常: {e}")
        finally:
            await self._cleanup()

    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"收到信号 {signum}，准备停止监控")
        self.running = False

    async def _health_check_loop(self):
        """健康检查循环"""
        while self.running:
            try:
                await self._check_all_services()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"健康检查循环异常: {e}")
                await asyncio.sleep(self.check_interval)

    async def _system_metrics_loop(self):
        """系统指标收集循环"""
        while self.running:
            try:
                metrics = await self._collect_system_metrics()
                self.system_metrics_history.append(metrics)

                # 检查系统指标告警
                await self._check_system_alerts(metrics)

                # 限制历史记录长度
                if len(self.system_metrics_history) > self.max_history:
                    self.system_metrics_history = self.system_metrics_history[-self.max_history:]

                await asyncio.sleep(30)  # 每30秒收集一次系统指标
            except Exception as e:
                logger.error(f"系统指标收集异常: {e}")
                await asyncio.sleep(30)

    async def _cleanup_loop(self):
        """数据清理循环"""
        while self.running:
            try:
                # 每小时清理一次过期数据
                await asyncio.sleep(3600)
                await self._cleanup_old_data()
            except Exception as e:
                logger.error(f"数据清理异常: {e}")

    async def _recovery_loop(self):
        """自动恢复循环"""
        while self.running:
            try:
                await self._attempt_service_recovery()
                await asyncio.sleep(60)  # 每分钟检查一次
            except Exception as e:
                logger.error(f"自动恢复异常: {e}")
                await asyncio.sleep(60)

    async def _check_all_services(self):
        """检查所有服务"""
        tasks = []
        for service_name, config in self.services.items():
            task = asyncio.create_task(self._check_service_health(service_name, config))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            service_name = list(self.services.keys())[i]
            if isinstance(result, Exception):
                logger.error(f"检查服务 {service_name} 时发生异常: {result}")

    async def _check_service_health(self, service_name: str, config: Dict[str, Any]) -> ServiceHealth:
        """检查单个服务健康状态"""
        start_time = time.time()

        try:
            # 调用特定的健康检查方法
            health_check_func = config['health_check']
            status, error_msg, extra_data = await health_check_func(config)

            response_time = time.time() - start_time

            # 获取容器统计信息
            container_stats = await self._get_container_stats(config.get('container'))

            health = ServiceHealth(
                name=service_name,
                status=status,
                last_check=datetime.now(),
                response_time=response_time,
                error_message=error_msg,
                uptime=extra_data.get('uptime'),
                restart_count=extra_data.get('restart_count', 0),
                cpu_usage=container_stats.get('cpu_usage', 0.0),
                memory_usage=container_stats.get('memory_usage', 0.0)
            )

            # 保存到历史记录
            self.health_history[service_name].append(health)
            if len(self.health_history[service_name]) > self.max_history:
                self.health_history[service_name] = self.health_history[service_name][-self.max_history:]

            # 检查告警条件
            await self._check_service_alerts(health, config)

            return health

        except Exception as e:
            logger.error(f"检查服务 {service_name} 健康状态异常: {e}")
            response_time = time.time() - start_time

            health = ServiceHealth(
                name=service_name,
                status=ServiceStatus.UNKNOWN,
                last_check=datetime.now(),
                response_time=response_time,
                error_message=str(e)
            )

            self.health_history[service_name].append(health)
            return health

    async def _check_redis_health(self, config: Dict[str, Any]) -> tuple:
        """检查Redis健康状态"""
        try:
            # 检查容器状态
            container_info = await self._get_container_info(config['container'])
            if not container_info or container_info['state'] != 'running':
                return ServiceStatus.STOPPED, "Container not running", {}

            # 检查Redis连接
            result = subprocess.run(
                ['docker', 'exec', config['container'], 'redis-cli', 'ping'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and 'PONG' in result.stdout:
                return ServiceStatus.HEALTHY, None, {
                    'uptime': container_info.get('uptime', 0),
                    'restart_count': container_info.get('restart_count', 0)
                }
            else:
                return ServiceStatus.UNHEALTHY, "Redis ping failed", {}

        except subprocess.TimeoutExpired:
            return ServiceStatus.DEGRADED, "Redis ping timeout", {}
        except Exception as e:
            return ServiceStatus.UNHEALTHY, f"Redis check failed: {str(e)}", {}

    async def _check_mongodb_health(self, config: Dict[str, Any]) -> tuple:
        """检查MongoDB健康状态"""
        try:
            # 检查容器状态
            container_info = await self._get_container_info(config['container'])
            if not container_info or container_info['state'] != 'running':
                return ServiceStatus.STOPPED, "Container not running", {}

            # 检查MongoDB连接
            result = subprocess.run(
                ['docker', 'exec', config['container'], 'mongosh', '--quiet', '--eval', 'db.runCommand("ping")'],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and '"ok": 1' in result.stdout:
                return ServiceStatus.HEALTHY, None, {
                    'uptime': container_info.get('uptime', 0),
                    'restart_count': container_info.get('restart_count', 0)
                }
            else:
                return ServiceStatus.UNHEALTHY, "MongoDB ping failed", {}

        except subprocess.TimeoutExpired:
            return ServiceStatus.DEGRADED, "MongoDB ping timeout", {}
        except Exception as e:
            return ServiceStatus.UNHEALTHY, f"MongoDB check failed: {str(e)}", {}

    async def _check_web_gateway_health(self, config: Dict[str, Any]) -> tuple:
        """检查Web网关健康状态"""
        try:
            # 检查容器状态
            container_info = await self._get_container_info(config['container'])
            if not container_info or container_info['state'] != 'running':
                return ServiceStatus.STOPPED, "Container not running", {}

            # HTTP健康检查
            if 'endpoint' in config:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                    async with session.get(config['endpoint']) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('status') == 'healthy':
                                return ServiceStatus.HEALTHY, None, {
                                    'uptime': container_info.get('uptime', 0),
                                    'restart_count': container_info.get('restart_count', 0)
                                }
                            else:
                                return ServiceStatus.DEGRADED, "Service reports unhealthy", {}
                        else:
                            return ServiceStatus.UNHEALTHY, f"HTTP {response.status}", {}
            else:
                # 仅检查容器状态
                return ServiceStatus.HEALTHY, None, {
                    'uptime': container_info.get('uptime', 0),
                    'restart_count': container_info.get('restart_count', 0)
                }

        except asyncio.TimeoutError:
            return ServiceStatus.DEGRADED, "HTTP timeout", {}
        except Exception as e:
            return ServiceStatus.UNHEALTHY, f"HTTP check failed: {str(e)}", {}

    async def _check_container_health(self, config: Dict[str, Any]) -> tuple:
        """检查容器基础健康状态"""
        try:
            container_info = await self._get_container_info(config['container'])
            if not container_info:
                return ServiceStatus.STOPPED, "Container not found", {}

            state = container_info['state']
            if state == 'running':
                return ServiceStatus.HEALTHY, None, {
                    'uptime': container_info.get('uptime', 0),
                    'restart_count': container_info.get('restart_count', 0)
                }
            elif state == 'restarting':
                return ServiceStatus.DEGRADED, "Container restarting", {}
            else:
                return ServiceStatus.STOPPED, f"Container state: {state}", {}

        except Exception as e:
            return ServiceStatus.UNKNOWN, f"Container check failed: {str(e)}", {}

    async def _get_container_info(self, container_name: str) -> Optional[Dict[str, Any]]:
        """获取容器信息"""
        try:
            result = subprocess.run(
                ['docker', 'inspect', container_name],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)[0]
                state = data['State']

                return {
                    'state': state['Status'],
                    'running': state['Running'],
                    'restart_count': data['RestartCount'],
                    'started_at': state.get('StartedAt'),
                    'uptime': self._calculate_uptime(state.get('StartedAt'))
                }
            else:
                return None

        except Exception as e:
            logger.error(f"获取容器信息失败: {e}")
            return None

    def _calculate_uptime(self, started_at: Optional[str]) -> float:
        """计算运行时间"""
        if not started_at:
            return 0.0

        try:
            # Docker时间格式: 2023-11-15T10:30:45.123456789Z
            start_time = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            uptime = (datetime.now(start_time.tzinfo) - start_time).total_seconds()
            return max(0.0, uptime)
        except Exception:
            return 0.0

    async def _get_container_stats(self, container_name: Optional[str]) -> Dict[str, float]:
        """获取容器资源使用统计"""
        if not container_name:
            return {}

        try:
            result = subprocess.run(
                ['docker', 'stats', '--no-stream', '--format',
                 'table {{.CPUPerc}},{{.MemPerc}}', container_name],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:  # Header + data
                    data_line = lines[1]
                    cpu_str, mem_str = data_line.split(',')

                    cpu_usage = float(cpu_str.replace('%', ''))
                    memory_usage = float(mem_str.replace('%', ''))

                    return {
                        'cpu_usage': cpu_usage,
                        'memory_usage': memory_usage
                    }

            return {}

        except Exception as e:
            logger.error(f"获取容器统计信息失败: {e}")
            return {}

    async def _collect_system_metrics(self) -> SystemMetrics:
        """收集系统指标"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)

            # 内存使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # 磁盘使用率
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100

            # 网络IO
            network = psutil.net_io_counters()
            network_io = {
                'bytes_sent': network.bytes_sent,
                'bytes_recv': network.bytes_recv,
                'packets_sent': network.packets_sent,
                'packets_recv': network.packets_recv
            }

            # 负载平均值
            load_avg = list(psutil.getloadavg())

            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_usage=disk_percent,
                network_io=network_io,
                load_average=load_avg
            )

        except Exception as e:
            logger.error(f"收集系统指标失败: {e}")
            raise

    async def _check_service_alerts(self, health: ServiceHealth, config: Dict[str, Any]):
        """检查服务告警条件"""
        alerts = []

        # 状态告警
        if health.status == ServiceStatus.UNHEALTHY and config.get('critical', False):
            alerts.append({
                'level': AlertLevel.CRITICAL,
                'message': f"关键服务 {health.name} 不健康: {health.error_message}",
                'service': health.name,
                'timestamp': datetime.now()
            })
        elif health.status == ServiceStatus.DEGRADED:
            alerts.append({
                'level': AlertLevel.WARNING,
                'message': f"服务 {health.name} 性能下降: {health.error_message}",
                'service': health.name,
                'timestamp': datetime.now()
            })

        # 响应时间告警
        if health.response_time > self.thresholds['response_time']:
            alerts.append({
                'level': AlertLevel.WARNING,
                'message': f"服务 {health.name} 响应时间过长: {health.response_time:.2f}s",
                'service': health.name,
                'timestamp': datetime.now()
            })

        # 重启次数告警
        if health.restart_count > self.thresholds['restart_limit']:
            alerts.append({
                'level': AlertLevel.ERROR,
                'message': f"服务 {health.name} 重启次数过多: {health.restart_count}次",
                'service': health.name,
                'timestamp': datetime.now()
            })

        # 资源使用告警
        if health.cpu_usage > self.thresholds['cpu_usage']:
            alerts.append({
                'level': AlertLevel.WARNING,
                'message': f"服务 {health.name} CPU使用率过高: {health.cpu_usage:.1f}%",
                'service': health.name,
                'timestamp': datetime.now()
            })

        if health.memory_usage > self.thresholds['memory_usage']:
            alerts.append({
                'level': AlertLevel.WARNING,
                'message': f"服务 {health.name} 内存使用率过高: {health.memory_usage:.1f}%",
                'service': health.name,
                'timestamp': datetime.now()
            })

        # 记录告警
        for alert in alerts:
            self._add_alert(alert)

    async def _check_system_alerts(self, metrics: SystemMetrics):
        """检查系统级告警"""
        alerts = []

        if metrics.cpu_percent > self.thresholds['cpu_usage']:
            alerts.append({
                'level': AlertLevel.WARNING,
                'message': f"系统CPU使用率过高: {metrics.cpu_percent:.1f}%",
                'service': 'system',
                'timestamp': datetime.now()
            })

        if metrics.memory_percent > self.thresholds['memory_usage']:
            alerts.append({
                'level': AlertLevel.WARNING,
                'message': f"系统内存使用率过高: {metrics.memory_percent:.1f}%",
                'service': 'system',
                'timestamp': datetime.now()
            })

        if metrics.disk_usage > self.thresholds['disk_usage']:
            alerts.append({
                'level': AlertLevel.ERROR,
                'message': f"系统磁盘使用率过高: {metrics.disk_usage:.1f}%",
                'service': 'system',
                'timestamp': datetime.now()
            })

        for alert in alerts:
            self._add_alert(alert)

    def _add_alert(self, alert: Dict[str, Any]):
        """添加告警"""
        alert_dict = {
            'level': alert['level'].value if isinstance(alert['level'], AlertLevel) else alert['level'],
            'message': alert['message'],
            'service': alert['service'],
            'timestamp': alert['timestamp'].isoformat()
        }

        self.alerts.append(alert_dict)

        # 限制告警历史长度
        if len(self.alerts) > self.max_history:
            self.alerts = self.alerts[-self.max_history:]

        # 记录日志
        level_map = {
            AlertLevel.INFO: logging.INFO,
            AlertLevel.WARNING: logging.WARNING,
            AlertLevel.ERROR: logging.ERROR,
            AlertLevel.CRITICAL: logging.CRITICAL
        }

        log_level = level_map.get(alert['level'], logging.INFO)
        logger.log(log_level, f"🚨 {alert['message']}")

    async def _attempt_service_recovery(self):
        """尝试服务自动恢复"""
        for service_name, config in self.services.items():
            if not config.get('critical', False):
                continue

            # 检查最近的健康状态
            recent_health = self._get_recent_health(service_name, minutes=5)
            if not recent_health:
                continue

            # 统计不健康状态
            unhealthy_count = sum(1 for h in recent_health
                                if h.status in [ServiceStatus.UNHEALTHY, ServiceStatus.STOPPED])

            # 如果超过一半的检查都是不健康的，尝试恢复
            if unhealthy_count > len(recent_health) / 2:
                await self._recover_service(service_name, config)

    async def _recover_service(self, service_name: str, config: Dict[str, Any]):
        """恢复服务"""
        logger.info(f"🔄 尝试恢复服务: {service_name}")

        try:
            container_name = config.get('container')
            if container_name:
                # 尝试重启容器
                result = subprocess.run(
                    ['docker', 'restart', container_name],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    logger.info(f"✅ 服务 {service_name} 重启成功")
                    self._add_alert({
                        'level': AlertLevel.INFO,
                        'message': f"服务 {service_name} 已自动重启恢复",
                        'service': service_name,
                        'timestamp': datetime.now()
                    })
                else:
                    logger.error(f"❌ 服务 {service_name} 重启失败: {result.stderr}")
                    self._add_alert({
                        'level': AlertLevel.ERROR,
                        'message': f"服务 {service_name} 自动重启失败",
                        'service': service_name,
                        'timestamp': datetime.now()
                    })

        except Exception as e:
            logger.error(f"恢复服务 {service_name} 时发生异常: {e}")

    def _get_recent_health(self, service_name: str, minutes: int = 5) -> List[ServiceHealth]:
        """获取最近的健康状态记录"""
        if service_name not in self.health_history:
            return []

        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [h for h in self.health_history[service_name]
                if h.last_check > cutoff_time]

    async def _cleanup_old_data(self):
        """清理过期数据"""
        cutoff_time = datetime.now() - timedelta(hours=24)

        # 清理健康状态历史
        for service_name in self.health_history:
            self.health_history[service_name] = [
                h for h in self.health_history[service_name]
                if h.last_check > cutoff_time
            ]

        # 清理系统指标历史
        self.system_metrics_history = [
            m for m in self.system_metrics_history
            if m.timestamp > cutoff_time
        ]

        # 清理告警历史
        alert_cutoff = datetime.now() - timedelta(hours=6)
        self.alerts = [
            a for a in self.alerts
            if datetime.fromisoformat(a['timestamp']) > alert_cutoff
        ]

        logger.info("🧹 数据清理完成")

    def get_status_summary(self) -> Dict[str, Any]:
        """获取状态摘要"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'services': {},
            'system': {},
            'alerts_summary': {
                'total': len(self.alerts),
                'critical': len([a for a in self.alerts if a['level'] == 'critical']),
                'error': len([a for a in self.alerts if a['level'] == 'error']),
                'warning': len([a for a in self.alerts if a['level'] == 'warning'])
            }
        }

        # 服务状态摘要
        for service_name in self.services:
            if service_name in self.health_history and self.health_history[service_name]:
                latest_health = self.health_history[service_name][-1]
                summary['services'][service_name] = latest_health.to_dict()
            else:
                summary['services'][service_name] = {
                    'name': service_name,
                    'status': ServiceStatus.UNKNOWN.value,
                    'error_message': 'No health data available'
                }

        # 系统指标摘要
        if self.system_metrics_history:
            latest_metrics = self.system_metrics_history[-1]
            summary['system'] = latest_metrics.to_dict()

        return summary

    def get_detailed_report(self) -> Dict[str, Any]:
        """获取详细报告"""
        return {
            'summary': self.get_status_summary(),
            'services_history': {
                name: [h.to_dict() for h in history[-10:]]  # 最近10条记录
                for name, history in self.health_history.items()
            },
            'system_metrics': [m.to_dict() for m in self.system_metrics_history[-20:]],  # 最近20条
            'recent_alerts': self.alerts[-50:],  # 最近50条告警
            'thresholds': self.thresholds
        }

    async def _cleanup(self):
        """清理资源"""
        logger.info("🛑 停止服务监控程序")
        self.running = False

    def save_report_to_file(self, filepath: str = "/tmp/service_monitor_report.json"):
        """保存报告到文件"""
        try:
            report = self.get_detailed_report()
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"📄 监控报告已保存至: {filepath}")
        except Exception as e:
            logger.error(f"保存报告失败: {e}")


async def main():
    """主函数"""
    monitor = ServiceMonitor()

    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        logger.info("用户中断程序")
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
    finally:
        # 保存最终报告
        monitor.save_report_to_file()


if __name__ == "__main__":
    asyncio.run(main())