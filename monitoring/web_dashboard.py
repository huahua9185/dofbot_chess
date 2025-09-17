#!/usr/bin/env python3
"""
象棋机器人系统 - 监控Web仪表板
============================

提供实时Web界面显示系统监控数据
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from pathlib import Path

import aiohttp
from aiohttp import web, WSMsgType
import aiohttp_cors
import jinja2
import weakref

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MonitoringDashboard:
    """监控仪表板"""

    def __init__(self, monitor_instance=None):
        self.monitor = monitor_instance
        self.app = web.Application()
        self.websockets = weakref.WeakSet()
        self._setup_routes()
        self._setup_cors()

    def _setup_routes(self):
        """设置路由"""
        # 静态文件和模板
        self.app.router.add_get('/', self.index)
        self.app.router.add_get('/api/status', self.get_status)
        self.app.router.add_get('/api/report', self.get_report)
        self.app.router.add_get('/api/alerts', self.get_alerts)
        self.app.router.add_get('/ws', self.websocket_handler)

    def _setup_cors(self):
        """设置CORS"""
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })

        # 为所有路由添加CORS
        for route in list(self.app.router.routes()):
            cors.add(route)

    async def index(self, request):
        """主页"""
        html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>象棋机器人系统监控</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }

        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }

        .status-healthy { background-color: #4CAF50; }
        .status-degraded { background-color: #FF9800; }
        .status-unhealthy { background-color: #F44336; }
        .status-stopped { background-color: #9E9E9E; }
        .status-unknown { background-color: #607D8B; }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
            transition: transform 0.3s ease;
        }

        .card:hover {
            transform: translateY(-5px);
        }

        .card-header {
            display: flex;
            justify-content: between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #f0f0f0;
        }

        .card-title {
            font-size: 1.2em;
            font-weight: bold;
            color: #2c3e50;
        }

        .service-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }

        .service-item:last-child {
            border-bottom: none;
        }

        .service-name {
            font-weight: 500;
            display: flex;
            align-items: center;
        }

        .service-details {
            font-size: 0.9em;
            color: #666;
            text-align: right;
        }

        .metric-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #2c3e50;
        }

        .metric-label {
            font-size: 0.9em;
            color: #666;
            margin-top: 5px;
        }

        .alert-item {
            padding: 10px;
            margin: 8px 0;
            border-radius: 6px;
            border-left: 4px solid;
        }

        .alert-critical {
            background-color: #ffebee;
            border-left-color: #f44336;
        }

        .alert-error {
            background-color: #fff3e0;
            border-left-color: #ff9800;
        }

        .alert-warning {
            background-color: #fff8e1;
            border-left-color: #ffc107;
        }

        .alert-info {
            background-color: #e3f2fd;
            border-left-color: #2196f3;
        }

        .alert-time {
            font-size: 0.8em;
            color: #666;
            float: right;
        }

        .connection-status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 15px;
            border-radius: 6px;
            color: white;
            font-weight: bold;
            z-index: 1000;
        }

        .connected {
            background-color: #4CAF50;
        }

        .disconnected {
            background-color: #F44336;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }

        .progress-bar {
            width: 100%;
            height: 8px;
            background-color: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
            margin: 8px 0;
        }

        .progress-fill {
            height: 100%;
            transition: width 0.3s ease;
        }

        .progress-cpu { background-color: #2196F3; }
        .progress-memory { background-color: #4CAF50; }
        .progress-disk { background-color: #FF9800; }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }

        .pulse {
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 象棋机器人系统监控</h1>
            <p>实时监控系统状态与性能指标</p>
        </div>

        <div class="connection-status" id="connectionStatus">
            <span id="connectionText">连接中...</span>
        </div>

        <div class="grid">
            <!-- 服务状态卡片 -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">🔧 服务状态</div>
                </div>
                <div id="servicesStatus">
                    <div class="loading">加载中...</div>
                </div>
            </div>

            <!-- 系统指标卡片 -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">📊 系统指标</div>
                </div>
                <div id="systemMetrics">
                    <div class="loading">加载中...</div>
                </div>
            </div>

            <!-- 告警信息卡片 -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">🚨 最新告警</div>
                </div>
                <div id="alertsInfo">
                    <div class="loading">加载中...</div>
                </div>
            </div>

            <!-- 统计摘要卡片 -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">📈 统计摘要</div>
                </div>
                <div id="summaryInfo">
                    <div class="loading">加载中...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        class MonitoringDashboard {
            constructor() {
                this.ws = null;
                this.reconnectAttempts = 0;
                this.maxReconnectAttempts = 5;
                this.reconnectDelay = 1000;

                this.init();
            }

            init() {
                this.connectWebSocket();
                this.loadInitialData();

                // 每30秒刷新一次数据
                setInterval(() => {
                    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
                        this.loadInitialData();
                    }
                }, 30000);
            }

            connectWebSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/ws`;

                try {
                    this.ws = new WebSocket(wsUrl);

                    this.ws.onopen = () => {
                        console.log('WebSocket连接已建立');
                        this.updateConnectionStatus(true);
                        this.reconnectAttempts = 0;
                    };

                    this.ws.onmessage = (event) => {
                        try {
                            const data = JSON.parse(event.data);
                            this.updateDashboard(data);
                        } catch (e) {
                            console.error('解析WebSocket消息失败:', e);
                        }
                    };

                    this.ws.onclose = () => {
                        console.log('WebSocket连接已关闭');
                        this.updateConnectionStatus(false);
                        this.attemptReconnect();
                    };

                    this.ws.onerror = (error) => {
                        console.error('WebSocket错误:', error);
                        this.updateConnectionStatus(false);
                    };

                } catch (e) {
                    console.error('WebSocket连接失败:', e);
                    this.updateConnectionStatus(false);
                    this.attemptReconnect();
                }
            }

            attemptReconnect() {
                if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                    console.log('达到最大重连次数，停止重连');
                    return;
                }

                this.reconnectAttempts++;
                const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

                console.log(`${delay/1000}秒后尝试第${this.reconnectAttempts}次重连...`);

                setTimeout(() => {
                    this.connectWebSocket();
                }, delay);
            }

            async loadInitialData() {
                try {
                    const response = await fetch('/api/status');
                    const data = await response.json();
                    this.updateDashboard(data);
                } catch (e) {
                    console.error('加载初始数据失败:', e);
                }
            }

            updateConnectionStatus(connected) {
                const statusEl = document.getElementById('connectionStatus');
                const textEl = document.getElementById('connectionText');

                if (connected) {
                    statusEl.className = 'connection-status connected';
                    textEl.textContent = '🟢 已连接';
                } else {
                    statusEl.className = 'connection-status disconnected';
                    textEl.textContent = '🔴 已断开';
                }
            }

            updateDashboard(data) {
                this.updateServicesStatus(data.services);
                this.updateSystemMetrics(data.system);
                this.updateAlerts(data.alerts_summary);
                this.updateSummary(data);
            }

            updateServicesStatus(services) {
                const container = document.getElementById('servicesStatus');
                if (!services) {
                    container.innerHTML = '<div class="loading">无服务数据</div>';
                    return;
                }

                let html = '';
                for (const [name, info] of Object.entries(services)) {
                    const statusClass = `status-${info.status}`;
                    const responseTime = info.response_time ? `${info.response_time.toFixed(2)}s` : 'N/A';
                    const uptime = info.uptime ? this.formatUptime(info.uptime) : 'N/A';

                    html += `
                        <div class="service-item">
                            <div class="service-name">
                                <span class="status-indicator ${statusClass}"></span>
                                ${name}
                            </div>
                            <div class="service-details">
                                <div>响应: ${responseTime}</div>
                                <div>运行: ${uptime}</div>
                            </div>
                        </div>
                    `;
                }

                container.innerHTML = html;
            }

            updateSystemMetrics(system) {
                const container = document.getElementById('systemMetrics');
                if (!system) {
                    container.innerHTML = '<div class="loading">无系统数据</div>';
                    return;
                }

                const html = `
                    <div class="service-item">
                        <div class="service-name">CPU使用率</div>
                        <div class="service-details">
                            <div class="metric-value">${system.cpu_percent.toFixed(1)}%</div>
                        </div>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill progress-cpu" style="width: ${system.cpu_percent}%"></div>
                    </div>

                    <div class="service-item">
                        <div class="service-name">内存使用率</div>
                        <div class="service-details">
                            <div class="metric-value">${system.memory_percent.toFixed(1)}%</div>
                        </div>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill progress-memory" style="width: ${system.memory_percent}%"></div>
                    </div>

                    <div class="service-item">
                        <div class="service-name">磁盘使用率</div>
                        <div class="service-details">
                            <div class="metric-value">${system.disk_usage.toFixed(1)}%</div>
                        </div>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill progress-disk" style="width: ${system.disk_usage}%"></div>
                    </div>
                `;

                container.innerHTML = html;
            }

            async updateAlerts(alertsSummary) {
                try {
                    const response = await fetch('/api/alerts');
                    const alerts = await response.json();

                    const container = document.getElementById('alertsInfo');

                    if (!alerts || alerts.length === 0) {
                        container.innerHTML = '<div class="service-item">🎉 暂无告警</div>';
                        return;
                    }

                    let html = '';
                    const recentAlerts = alerts.slice(-5); // 显示最近5条告警

                    for (const alert of recentAlerts.reverse()) {
                        const alertClass = `alert-${alert.level}`;
                        const timeStr = this.formatTime(alert.timestamp);

                        html += `
                            <div class="alert-item ${alertClass}">
                                <div class="alert-time">${timeStr}</div>
                                <div>${alert.message}</div>
                            </div>
                        `;
                    }

                    container.innerHTML = html;

                } catch (e) {
                    console.error('更新告警信息失败:', e);
                }
            }

            updateSummary(data) {
                const container = document.getElementById('summaryInfo');

                const totalServices = Object.keys(data.services || {}).length;
                const healthyServices = Object.values(data.services || {}).filter(s => s.status === 'healthy').length;
                const totalAlerts = data.alerts_summary?.total || 0;
                const criticalAlerts = data.alerts_summary?.critical || 0;

                const html = `
                    <div class="service-item">
                        <div class="service-name">服务总数</div>
                        <div class="service-details">
                            <div class="metric-value">${totalServices}</div>
                        </div>
                    </div>

                    <div class="service-item">
                        <div class="service-name">健康服务</div>
                        <div class="service-details">
                            <div class="metric-value" style="color: #4CAF50">${healthyServices}</div>
                        </div>
                    </div>

                    <div class="service-item">
                        <div class="service-name">告警总数</div>
                        <div class="service-details">
                            <div class="metric-value" style="color: ${totalAlerts > 0 ? '#FF9800' : '#4CAF50'}">${totalAlerts}</div>
                        </div>
                    </div>

                    <div class="service-item">
                        <div class="service-name">严重告警</div>
                        <div class="service-details">
                            <div class="metric-value" style="color: ${criticalAlerts > 0 ? '#F44336' : '#4CAF50'}">${criticalAlerts}</div>
                        </div>
                    </div>
                `;

                container.innerHTML = html;
            }

            formatUptime(seconds) {
                if (seconds < 60) return `${seconds.toFixed(0)}秒`;
                if (seconds < 3600) return `${(seconds/60).toFixed(0)}分钟`;
                if (seconds < 86400) return `${(seconds/3600).toFixed(1)}小时`;
                return `${(seconds/86400).toFixed(1)}天`;
            }

            formatTime(timestamp) {
                const date = new Date(timestamp);
                return date.toLocaleTimeString('zh-CN');
            }
        }

        // 启动仪表板
        document.addEventListener('DOMContentLoaded', () => {
            new MonitoringDashboard();
        });
    </script>
</body>
</html>
        """
        return web.Response(text=html_content, content_type='text/html')

    async def get_status(self, request):
        """获取状态API"""
        if self.monitor:
            data = self.monitor.get_status_summary()
        else:
            data = {
                'timestamp': datetime.now().isoformat(),
                'services': {},
                'system': {},
                'alerts_summary': {'total': 0, 'critical': 0, 'error': 0, 'warning': 0}
            }

        return web.json_response(data)

    async def get_report(self, request):
        """获取详细报告API"""
        if self.monitor:
            data = self.monitor.get_detailed_report()
        else:
            data = {'error': 'Monitor not available'}

        return web.json_response(data)

    async def get_alerts(self, request):
        """获取告警API"""
        if self.monitor:
            alerts = self.monitor.alerts
        else:
            alerts = []

        return web.json_response(alerts)

    async def websocket_handler(self, request):
        """WebSocket处理器"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self.websockets.add(ws)
        logger.info("新的WebSocket连接建立")

        try:
            # 发送初始数据
            if self.monitor:
                initial_data = self.monitor.get_status_summary()
                await ws.send_str(json.dumps(initial_data))

            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    if msg.data == 'close':
                        await ws.close()
                        break
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f'WebSocket错误: {ws.exception()}')
                    break

        except Exception as e:
            logger.error(f"WebSocket处理异常: {e}")
        finally:
            logger.info("WebSocket连接关闭")

        return ws

    async def broadcast_update(self, data):
        """广播更新到所有WebSocket客户端"""
        if not self.websockets:
            return

        message = json.dumps(data)
        disconnected = []

        for ws in self.websockets:
            try:
                await ws.send_str(message)
            except Exception as e:
                logger.warning(f"发送WebSocket消息失败: {e}")
                disconnected.append(ws)

        # 移除断开的连接
        for ws in disconnected:
            self.websockets.discard(ws)

    async def start_server(self, host='0.0.0.0', port=8081):
        """启动Web服务器"""
        runner = web.AppRunner(self.app)
        await runner.setup()

        site = web.TCPSite(runner, host, port)
        await site.start()

        logger.info(f"🌐 监控仪表板启动: http://{host}:{port}")
        return runner


async def run_dashboard_with_monitor():
    """同时运行监控程序和Web仪表板"""
    from service_monitor import ServiceMonitor

    # 创建监控实例
    monitor = ServiceMonitor()

    # 创建仪表板实例
    dashboard = MonitoringDashboard(monitor)

    # 启动Web服务器
    runner = await dashboard.start_server()

    try:
        # 启动监控程序（在后台运行）
        monitor_task = asyncio.create_task(monitor.start_monitoring())

        # 定期广播更新
        async def broadcast_loop():
            while True:
                await asyncio.sleep(5)  # 每5秒广播一次
                try:
                    data = monitor.get_status_summary()
                    await dashboard.broadcast_update(data)
                except Exception as e:
                    logger.error(f"广播更新失败: {e}")

        broadcast_task = asyncio.create_task(broadcast_loop())

        # 等待任务完成
        await asyncio.gather(monitor_task, broadcast_task)

    except KeyboardInterrupt:
        logger.info("用户中断程序")
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(run_dashboard_with_monitor())