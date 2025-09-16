# -*- coding: utf-8 -*-
"""
安全监控模块
提供威胁检测、审计日志、安全事件监控等功能
"""

import json
import asyncio
import time
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import re
import ipaddress
from pathlib import Path

from .data_protection import SensitiveDataPattern


class SecurityEventType(Enum):
    """安全事件类型"""
    # 认证相关
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    SESSION_EXPIRED = "session_expired"
    PASSWORD_CHANGED = "password_changed"

    # 授权相关
    ACCESS_DENIED = "access_denied"
    PERMISSION_ESCALATION = "permission_escalation"
    UNAUTHORIZED_ACCESS = "unauthorized_access"

    # 数据相关
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    DATA_EXPORT = "data_export"
    SENSITIVE_DATA_DETECTED = "sensitive_data_detected"

    # 系统相关
    SYSTEM_ERROR = "system_error"
    CONFIG_CHANGE = "config_change"
    SERVICE_START = "service_start"
    SERVICE_STOP = "service_stop"

    # 威胁相关
    BRUTE_FORCE_ATTACK = "brute_force_attack"
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
    XSS_ATTEMPT = "xss_attempt"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    MALICIOUS_REQUEST = "malicious_request"

    # 网络相关
    UNUSUAL_NETWORK_ACTIVITY = "unusual_network_activity"
    BLOCKED_IP = "blocked_ip"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


class SecuritySeverity(Enum):
    """安全事件严重程度"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class SecurityEvent:
    """安全事件"""
    event_type: SecurityEventType
    severity: SecuritySeverity
    timestamp: datetime
    source_ip: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    details: Dict[str, Any] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['severity'] = self.severity.value
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SecurityEvent':
        """从字典创建实例"""
        data = data.copy()
        data['event_type'] = SecurityEventType(data['event_type'])
        data['severity'] = SecuritySeverity(data['severity'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class ThreatDetector:
    """威胁检测器"""

    def __init__(self):
        """初始化威胁检测器"""
        # 登录失败计数器
        self.login_failures = defaultdict(list)
        self.blocked_ips = set()

        # 请求速率监控
        self.request_rates = defaultdict(lambda: deque(maxlen=100))

        # SQL注入模式
        self.sql_injection_patterns = [
            r"(\')|(\-\-)|(\;)",
            r"(union.*select)|(select.*from)|(insert.*into)|(delete.*from)|(drop.*table)",
            r"(script|javascript|vbscript|onload|onerror|onclick)",
            r"(<|>|\"|\'|\%3C|\%3E|\%22|\%27)"
        ]

        # XSS攻击模式
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"onload\s*=",
            r"onerror\s*=",
            r"onclick\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>"
        ]

        # 可疑用户代理
        self.suspicious_user_agents = [
            r"sqlmap",
            r"nikto",
            r"nessus",
            r"burp",
            r"nmap",
            r"curl.*",
            r"wget.*",
            r"python-requests",
            r"bot.*crawler"
        ]

    def detect_brute_force(self, ip_address: str, user_id: str = None, max_failures: int = 5, time_window: int = 300) -> bool:
        """检测暴力破解攻击"""
        now = time.time()
        key = f"{ip_address}:{user_id}" if user_id else ip_address

        # 清理过期记录
        self.login_failures[key] = [
            timestamp for timestamp in self.login_failures[key]
            if now - timestamp <= time_window
        ]

        # 添加当前失败记录
        self.login_failures[key].append(now)

        # 检查是否超过阈值
        if len(self.login_failures[key]) >= max_failures:
            self.blocked_ips.add(ip_address)
            return True

        return False

    def detect_sql_injection(self, input_data: str) -> bool:
        """检测SQL注入攻击"""
        input_lower = input_data.lower()

        for pattern in self.sql_injection_patterns:
            if re.search(pattern, input_lower, re.IGNORECASE):
                return True

        return False

    def detect_xss_attack(self, input_data: str) -> bool:
        """检测XSS攻击"""
        for pattern in self.xss_patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                return True

        return False

    def detect_suspicious_user_agent(self, user_agent: str) -> bool:
        """检测可疑用户代理"""
        if not user_agent:
            return False

        user_agent_lower = user_agent.lower()

        for pattern in self.suspicious_user_agents:
            if re.search(pattern, user_agent_lower):
                return True

        return False

    def detect_rate_limiting(self, ip_address: str, max_requests: int = 100, time_window: int = 60) -> bool:
        """检测请求速率限制"""
        now = time.time()
        requests = self.request_rates[ip_address]

        # 清理过期请求
        while requests and now - requests[0] > time_window:
            requests.popleft()

        # 添加当前请求
        requests.append(now)

        # 检查是否超过速率限制
        return len(requests) > max_requests

    def detect_unusual_access_pattern(self, user_id: str, current_ip: str, user_history: List[Dict[str, Any]]) -> bool:
        """检测异常访问模式"""
        if not user_history:
            return False

        # 获取用户常用IP地址
        common_ips = set()
        for record in user_history[-50:]:  # 检查最近50次登录
            if record.get('ip_address'):
                common_ips.add(record['ip_address'])

        # 检查当前IP是否为常用IP
        if current_ip not in common_ips:
            # 检查IP地理位置差异（简化版本）
            try:
                current_network = ipaddress.ip_network(f"{current_ip}/24", strict=False)
                is_same_network = any(
                    ipaddress.ip_address(ip) in current_network
                    for ip in common_ips
                )
                if not is_same_network:
                    return True
            except ValueError:
                pass

        # 检查访问时间模式
        recent_access_times = [
            datetime.fromisoformat(record['timestamp']).hour
            for record in user_history[-20:]
            if 'timestamp' in record
        ]

        if recent_access_times:
            current_hour = datetime.now().hour
            common_hours = set(recent_access_times)
            if current_hour not in common_hours:
                # 如果当前访问时间与历史模式差异很大，标记为可疑
                hour_diff = min(
                    abs(current_hour - h) for h in common_hours
                )
                if hour_diff > 6:  # 时间差异超过6小时
                    return True

        return False

    def is_ip_blocked(self, ip_address: str) -> bool:
        """检查IP是否被阻止"""
        return ip_address in self.blocked_ips

    def unblock_ip(self, ip_address: str) -> bool:
        """解除IP阻止"""
        if ip_address in self.blocked_ips:
            self.blocked_ips.remove(ip_address)
            return True
        return False

    def get_threat_statistics(self) -> Dict[str, Any]:
        """获取威胁统计信息"""
        return {
            'blocked_ips_count': len(self.blocked_ips),
            'blocked_ips': list(self.blocked_ips),
            'monitored_ips_count': len(self.login_failures),
            'active_rate_limits': len(self.request_rates)
        }


class AuditLogger:
    """审计日志记录器"""

    def __init__(self, log_file: str = None):
        """初始化审计日志记录器"""
        self.log_file = Path(log_file or "/app/logs/security_audit.log")
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # 内存中的事件缓冲区
        self.event_buffer = deque(maxlen=1000)

        # 日志级别配置
        self.log_levels = {
            SecuritySeverity.CRITICAL: True,
            SecuritySeverity.HIGH: True,
            SecuritySeverity.MEDIUM: True,
            SecuritySeverity.LOW: False  # 默认不记录低级别事件
        }

    def log_event(self, event: SecurityEvent):
        """记录安全事件"""
        # 检查是否需要记录该级别的事件
        if not self.log_levels.get(event.severity, True):
            return

        # 添加到内存缓冲区
        self.event_buffer.append(event)

        # 写入日志文件
        self._write_to_file(event)

    def _write_to_file(self, event: SecurityEvent):
        """写入日志文件"""
        try:
            log_entry = {
                'timestamp': event.timestamp.isoformat(),
                'event_type': event.event_type.value,
                'severity': event.severity.name,
                'source_ip': event.source_ip,
                'user_id': event.user_id,
                'session_id': event.session_id,
                'resource': event.resource,
                'action': event.action,
                'details': event.details,
                'user_agent': event.user_agent,
                'request_id': event.request_id
            }

            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

        except Exception as e:
            print(f"写入审计日志失败: {e}")

    def query_events(
        self,
        start_time: datetime = None,
        end_time: datetime = None,
        event_types: List[SecurityEventType] = None,
        severity: SecuritySeverity = None,
        user_id: str = None,
        source_ip: str = None,
        limit: int = 100
    ) -> List[SecurityEvent]:
        """查询安全事件"""

        # 首先从内存缓冲区查询
        matching_events = []

        for event in reversed(list(self.event_buffer)):
            # 时间过滤
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue

            # 事件类型过滤
            if event_types and event.event_type not in event_types:
                continue

            # 严重程度过滤
            if severity and event.severity != severity:
                continue

            # 用户ID过滤
            if user_id and event.user_id != user_id:
                continue

            # 源IP过滤
            if source_ip and event.source_ip != source_ip:
                continue

            matching_events.append(event)

            if len(matching_events) >= limit:
                break

        # 如果内存中的事件不够，从文件中读取
        if len(matching_events) < limit:
            file_events = self._query_from_file(
                start_time, end_time, event_types, severity, user_id, source_ip, limit - len(matching_events)
            )
            matching_events.extend(file_events)

        return matching_events[:limit]

    def _query_from_file(
        self,
        start_time: datetime = None,
        end_time: datetime = None,
        event_types: List[SecurityEventType] = None,
        severity: SecuritySeverity = None,
        user_id: str = None,
        source_ip: str = None,
        limit: int = 100
    ) -> List[SecurityEvent]:
        """从文件查询事件"""
        events = []

        try:
            if not self.log_file.exists():
                return events

            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 从最新的记录开始读取
            for line in reversed(lines):
                if len(events) >= limit:
                    break

                try:
                    log_entry = json.loads(line.strip())
                    event_timestamp = datetime.fromisoformat(log_entry['timestamp'])

                    # 应用过滤条件
                    if start_time and event_timestamp < start_time:
                        continue
                    if end_time and event_timestamp > end_time:
                        continue

                    event_type = SecurityEventType(log_entry['event_type'])
                    if event_types and event_type not in event_types:
                        continue

                    event_severity = SecuritySeverity[log_entry['severity']]
                    if severity and event_severity != severity:
                        continue

                    if user_id and log_entry.get('user_id') != user_id:
                        continue

                    if source_ip and log_entry.get('source_ip') != source_ip:
                        continue

                    # 创建事件对象
                    event = SecurityEvent(
                        event_type=event_type,
                        severity=event_severity,
                        timestamp=event_timestamp,
                        source_ip=log_entry.get('source_ip', ''),
                        user_id=log_entry.get('user_id'),
                        session_id=log_entry.get('session_id'),
                        resource=log_entry.get('resource'),
                        action=log_entry.get('action'),
                        details=log_entry.get('details', {}),
                        user_agent=log_entry.get('user_agent'),
                        request_id=log_entry.get('request_id')
                    )

                    events.append(event)

                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

        except Exception as e:
            print(f"从文件查询事件失败: {e}")

        return events

    def get_event_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """获取事件统计信息"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_events = self.query_events(start_time=cutoff_time, limit=10000)

        # 统计数据
        stats = {
            'total_events': len(recent_events),
            'by_type': defaultdict(int),
            'by_severity': defaultdict(int),
            'by_hour': defaultdict(int),
            'unique_users': set(),
            'unique_ips': set()
        }

        for event in recent_events:
            stats['by_type'][event.event_type.value] += 1
            stats['by_severity'][event.severity.name] += 1
            stats['by_hour'][event.timestamp.hour] += 1

            if event.user_id:
                stats['unique_users'].add(event.user_id)
            if event.source_ip:
                stats['unique_ips'].add(event.source_ip)

        # 转换为普通字典
        return {
            'total_events': stats['total_events'],
            'by_type': dict(stats['by_type']),
            'by_severity': dict(stats['by_severity']),
            'by_hour': dict(stats['by_hour']),
            'unique_users_count': len(stats['unique_users']),
            'unique_ips_count': len(stats['unique_ips']),
            'time_range_hours': hours
        }

    def set_log_level(self, severity: SecuritySeverity, enabled: bool):
        """设置日志级别"""
        self.log_levels[severity] = enabled


class SecurityMonitor:
    """安全监控主类"""

    def __init__(self, log_file: str = None):
        """初始化安全监控器"""
        self.threat_detector = ThreatDetector()
        self.audit_logger = AuditLogger(log_file)
        self.event_handlers: Dict[SecurityEventType, List[Callable]] = defaultdict(list)

        # 自动威胁响应配置
        self.auto_response_enabled = True
        self.auto_block_brute_force = True
        self.auto_block_malicious_requests = True

    def log_security_event(
        self,
        event_type: SecurityEventType,
        severity: SecuritySeverity,
        source_ip: str,
        user_id: str = None,
        session_id: str = None,
        resource: str = None,
        action: str = None,
        details: Dict[str, Any] = None,
        user_agent: str = None,
        request_id: str = None
    ):
        """记录安全事件"""
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            timestamp=datetime.utcnow(),
            source_ip=source_ip,
            user_id=user_id,
            session_id=session_id,
            resource=resource,
            action=action,
            details=details or {},
            user_agent=user_agent,
            request_id=request_id
        )

        # 记录到审计日志
        self.audit_logger.log_event(event)

        # 执行威胁检测
        self._perform_threat_detection(event)

        # 触发事件处理器
        self._trigger_event_handlers(event)

    def _perform_threat_detection(self, event: SecurityEvent):
        """执行威胁检测"""
        # 检测暴力破解
        if event.event_type == SecurityEventType.LOGIN_FAILURE:
            if self.threat_detector.detect_brute_force(event.source_ip, event.user_id):
                self.log_security_event(
                    SecurityEventType.BRUTE_FORCE_ATTACK,
                    SecuritySeverity.HIGH,
                    event.source_ip,
                    event.user_id,
                    details={'original_event': event.to_dict()}
                )

        # 检测可疑用户代理
        if event.user_agent and self.threat_detector.detect_suspicious_user_agent(event.user_agent):
            self.log_security_event(
                SecurityEventType.SUSPICIOUS_ACTIVITY,
                SecuritySeverity.MEDIUM,
                event.source_ip,
                event.user_id,
                details={'user_agent': event.user_agent}
            )

        # 检测请求速率限制
        if self.threat_detector.detect_rate_limiting(event.source_ip):
            self.log_security_event(
                SecurityEventType.RATE_LIMIT_EXCEEDED,
                SecuritySeverity.MEDIUM,
                event.source_ip,
                event.user_id,
                details={'rate_limit_exceeded': True}
            )

    def _trigger_event_handlers(self, event: SecurityEvent):
        """触发事件处理器"""
        handlers = self.event_handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"事件处理器执行失败: {e}")

    def register_event_handler(self, event_type: SecurityEventType, handler: Callable[[SecurityEvent], None]):
        """注册事件处理器"""
        self.event_handlers[event_type].append(handler)

    def analyze_request(self, request_data: Dict[str, Any]) -> List[SecurityEvent]:
        """分析请求安全性"""
        detected_events = []
        source_ip = request_data.get('source_ip', 'unknown')
        user_id = request_data.get('user_id')
        user_agent = request_data.get('user_agent', '')

        # 检查输入数据中的敏感信息
        for key, value in request_data.items():
            if isinstance(value, str):
                # 检测敏感数据泄露
                sensitive_patterns = SensitiveDataPattern.detect_sensitive_data(value)
                if sensitive_patterns:
                    event = SecurityEvent(
                        event_type=SecurityEventType.SENSITIVE_DATA_DETECTED,
                        severity=SecuritySeverity.HIGH,
                        timestamp=datetime.utcnow(),
                        source_ip=source_ip,
                        user_id=user_id,
                        details={'field': key, 'patterns': list(sensitive_patterns.keys())}
                    )
                    detected_events.append(event)

                # 检测SQL注入
                if self.threat_detector.detect_sql_injection(value):
                    event = SecurityEvent(
                        event_type=SecurityEventType.SQL_INJECTION_ATTEMPT,
                        severity=SecuritySeverity.CRITICAL,
                        timestamp=datetime.utcnow(),
                        source_ip=source_ip,
                        user_id=user_id,
                        user_agent=user_agent,
                        details={'field': key, 'value': value[:100]}  # 只保存前100个字符
                    )
                    detected_events.append(event)

                # 检测XSS攻击
                if self.threat_detector.detect_xss_attack(value):
                    event = SecurityEvent(
                        event_type=SecurityEventType.XSS_ATTEMPT,
                        severity=SecuritySeverity.HIGH,
                        timestamp=datetime.utcnow(),
                        source_ip=source_ip,
                        user_id=user_id,
                        user_agent=user_agent,
                        details={'field': key, 'value': value[:100]}
                    )
                    detected_events.append(event)

        # 记录所有检测到的事件
        for event in detected_events:
            self.audit_logger.log_event(event)

        return detected_events

    def get_security_dashboard(self) -> Dict[str, Any]:
        """获取安全仪表板数据"""
        return {
            'threat_statistics': self.threat_detector.get_threat_statistics(),
            'event_statistics': self.audit_logger.get_event_statistics(),
            'recent_critical_events': [
                event.to_dict() for event in self.audit_logger.query_events(
                    severity=SecuritySeverity.CRITICAL,
                    limit=10
                )
            ],
            'system_status': {
                'auto_response_enabled': self.auto_response_enabled,
                'auto_block_brute_force': self.auto_block_brute_force,
                'auto_block_malicious_requests': self.auto_block_malicious_requests
            }
        }