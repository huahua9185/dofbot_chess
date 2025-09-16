# -*- coding: utf-8 -*-
"""
访问控制模块
提供IP白名单、速率限制、安全策略、访问验证等功能
"""

import os
import time
import ipaddress
import re
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

from .security_monitor import SecurityEvent, SecurityEventType, SecuritySeverity


class AccessResult(Enum):
    """访问结果"""
    ALLOWED = "allowed"
    DENIED = "denied"
    RATE_LIMITED = "rate_limited"
    IP_BLOCKED = "ip_blocked"
    SUSPICIOUS = "suspicious"


@dataclass
class AccessAttempt:
    """访问尝试记录"""
    ip_address: str
    user_id: Optional[str]
    timestamp: datetime
    resource: str
    action: str
    result: AccessResult
    reason: Optional[str] = None
    user_agent: Optional[str] = None


class IPWhitelist:
    """IP白名单管理"""

    def __init__(self, whitelist_file: str = None):
        """初始化IP白名单"""
        self.whitelist_file = Path(whitelist_file or "/app/config/ip_whitelist.json")
        self.whitelist_file.parent.mkdir(parents=True, exist_ok=True)

        # IP地址和网络段
        self.allowed_ips: Set[str] = set()
        self.allowed_networks: List[ipaddress.IPv4Network] = []

        # 加载白名单
        self._load_whitelist()

    def add_ip(self, ip_address: str) -> bool:
        """添加IP到白名单"""
        try:
            # 验证IP地址格式
            ipaddress.ip_address(ip_address)
            self.allowed_ips.add(ip_address)
            self._save_whitelist()
            return True
        except ValueError:
            return False

    def add_network(self, network: str) -> bool:
        """添加网络段到白名单"""
        try:
            network_obj = ipaddress.ip_network(network, strict=False)
            self.allowed_networks.append(network_obj)
            self._save_whitelist()
            return True
        except ValueError:
            return False

    def remove_ip(self, ip_address: str) -> bool:
        """从白名单移除IP"""
        if ip_address in self.allowed_ips:
            self.allowed_ips.remove(ip_address)
            self._save_whitelist()
            return True
        return False

    def remove_network(self, network: str) -> bool:
        """从白名单移除网络段"""
        try:
            network_obj = ipaddress.ip_network(network, strict=False)
            if network_obj in self.allowed_networks:
                self.allowed_networks.remove(network_obj)
                self._save_whitelist()
                return True
        except ValueError:
            pass
        return False

    def is_allowed(self, ip_address: str) -> bool:
        """检查IP是否在白名单中"""
        try:
            ip = ipaddress.ip_address(ip_address)

            # 检查直接IP匹配
            if ip_address in self.allowed_ips:
                return True

            # 检查网络段匹配
            for network in self.allowed_networks:
                if ip in network:
                    return True

            return False

        except ValueError:
            return False

    def get_whitelist_info(self) -> Dict[str, Any]:
        """获取白名单信息"""
        return {
            'allowed_ips': list(self.allowed_ips),
            'allowed_networks': [str(network) for network in self.allowed_networks],
            'total_entries': len(self.allowed_ips) + len(self.allowed_networks)
        }

    def _load_whitelist(self):
        """加载白名单"""
        try:
            if self.whitelist_file.exists():
                with open(self.whitelist_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self.allowed_ips = set(data.get('ips', []))

                for network_str in data.get('networks', []):
                    try:
                        network = ipaddress.ip_network(network_str, strict=False)
                        self.allowed_networks.append(network)
                    except ValueError:
                        continue
        except Exception as e:
            print(f"加载IP白名单失败: {e}")

    def _save_whitelist(self):
        """保存白名单"""
        try:
            data = {
                'ips': list(self.allowed_ips),
                'networks': [str(network) for network in self.allowed_networks],
                'updated_at': datetime.utcnow().isoformat()
            }

            with open(self.whitelist_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"保存IP白名单失败: {e}")


class RateLimiter:
    """速率限制器"""

    def __init__(self):
        """初始化速率限制器"""
        # 不同类型的速率限制
        self.rate_limits = {
            'global': {'requests': 1000, 'window': 60},      # 全局限制：每分钟1000请求
            'per_ip': {'requests': 100, 'window': 60},       # 每IP：每分钟100请求
            'per_user': {'requests': 200, 'window': 60},     # 每用户：每分钟200请求
            'login': {'requests': 10, 'window': 300},        # 登录：每5分钟10次
            'api': {'requests': 50, 'window': 60}            # API调用：每分钟50次
        }

        # 请求记录
        self.request_records = {
            'global': deque(),
            'per_ip': defaultdict(lambda: deque()),
            'per_user': defaultdict(lambda: deque()),
            'login': defaultdict(lambda: deque()),
            'api': defaultdict(lambda: deque())
        }

    def check_rate_limit(
        self,
        limit_type: str,
        identifier: str = None,
        custom_limits: Dict[str, int] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """检查速率限制"""

        if limit_type not in self.rate_limits:
            return True, {'allowed': True, 'reason': 'unknown_limit_type'}

        # 使用自定义限制或默认限制
        limits = custom_limits or self.rate_limits[limit_type]
        max_requests = limits['requests']
        time_window = limits['window']

        # 获取请求记录
        if limit_type == 'global':
            records = self.request_records['global']
        else:
            if not identifier:
                return True, {'allowed': True, 'reason': 'no_identifier'}
            # 确保键存在
            if identifier not in self.request_records[limit_type]:
                self.request_records[limit_type][identifier] = deque()
            records = self.request_records[limit_type][identifier]

        # 清理过期记录
        current_time = time.time()
        while records and current_time - records[0] > time_window:
            records.popleft()

        # 检查是否超过限制
        if len(records) >= max_requests:
            return False, {
                'allowed': False,
                'reason': 'rate_limit_exceeded',
                'limit_type': limit_type,
                'max_requests': max_requests,
                'time_window': time_window,
                'current_count': len(records),
                'reset_time': records[0] + time_window if records else current_time
            }

        # 记录当前请求
        records.append(current_time)

        return True, {
            'allowed': True,
            'limit_type': limit_type,
            'max_requests': max_requests,
            'time_window': time_window,
            'current_count': len(records),
            'remaining': max_requests - len(records)
        }

    def set_rate_limit(self, limit_type: str, requests: int, window: int):
        """设置速率限制"""
        self.rate_limits[limit_type] = {'requests': requests, 'window': window}

    def get_rate_limit_status(self, limit_type: str, identifier: str = None) -> Dict[str, Any]:
        """获取速率限制状态"""
        if limit_type not in self.rate_limits:
            return {'error': 'unknown_limit_type'}

        limits = self.rate_limits[limit_type]

        if limit_type == 'global':
            records = self.request_records['global']
        else:
            if not identifier:
                return {'error': 'no_identifier'}
            records = self.request_records[limit_type][identifier]

        # 清理过期记录
        current_time = time.time()
        while records and current_time - records[0] > limits['window']:
            records.popleft()

        return {
            'limit_type': limit_type,
            'identifier': identifier,
            'max_requests': limits['requests'],
            'time_window': limits['window'],
            'current_count': len(records),
            'remaining': limits['requests'] - len(records),
            'reset_time': records[0] + limits['window'] if records else current_time
        }

    def reset_rate_limit(self, limit_type: str, identifier: str = None):
        """重置速率限制"""
        if limit_type == 'global':
            self.request_records['global'].clear()
        elif identifier:
            if identifier in self.request_records[limit_type]:
                self.request_records[limit_type][identifier].clear()

    def get_all_limits_status(self) -> Dict[str, Any]:
        """获取所有限制状态"""
        status = {}

        for limit_type in self.rate_limits.keys():
            if limit_type == 'global':
                status[limit_type] = self.get_rate_limit_status(limit_type)
            else:
                # 获取活跃的标识符
                active_identifiers = list(self.request_records[limit_type].keys())[:10]  # 最多显示10个
                status[limit_type] = {
                    'config': self.rate_limits[limit_type],
                    'active_identifiers_count': len(self.request_records[limit_type]),
                    'sample_identifiers': [
                        {
                            'identifier': identifier,
                            'status': self.get_rate_limit_status(limit_type, identifier)
                        }
                        for identifier in active_identifiers
                    ]
                }

        return status


class SecurityPolicy:
    """安全策略管理"""

    def __init__(self):
        """初始化安全策略"""
        self.policies = {
            # 密码策略
            'password_policy': {
                'min_length': 8,
                'require_uppercase': True,
                'require_lowercase': True,
                'require_digits': True,
                'require_special_chars': True,
                'forbidden_patterns': ['123456', 'password', 'admin'],
                'max_age_days': 90,
                'history_count': 5
            },

            # 会话策略
            'session_policy': {
                'max_idle_time': 1800,  # 30分钟
                'absolute_timeout': 28800,  # 8小时
                'require_reauth_for_sensitive': True,
                'secure_cookies': True,
                'same_site': 'strict'
            },

            # 访问策略
            'access_policy': {
                'require_https': True,
                'allowed_http_methods': ['GET', 'POST', 'PUT', 'DELETE'],
                'max_request_size': 10 * 1024 * 1024,  # 10MB
                'enable_ip_whitelist': False,
                'enable_geo_blocking': False,
                'blocked_countries': []
            },

            # 文件上传策略
            'upload_policy': {
                'allowed_extensions': ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.txt'],
                'max_file_size': 5 * 1024 * 1024,  # 5MB
                'scan_for_malware': True,
                'quarantine_suspicious_files': True
            },

            # API策略
            'api_policy': {
                'require_authentication': True,
                'require_api_key': False,
                'enable_cors': True,
                'allowed_origins': ['http://localhost:3000', 'https://localhost:3000'],
                'rate_limit_enabled': True
            }
        }

        # 策略违规记录
        self.violations = deque(maxlen=1000)

    def validate_password(self, password: str, username: str = None) -> Tuple[bool, List[str]]:
        """验证密码是否符合策略"""
        policy = self.policies['password_policy']
        errors = []

        # 长度检查
        if len(password) < policy['min_length']:
            errors.append(f"密码长度至少为{policy['min_length']}位")

        # 大写字母检查
        if policy['require_uppercase'] and not re.search(r'[A-Z]', password):
            errors.append("密码必须包含至少一个大写字母")

        # 小写字母检查
        if policy['require_lowercase'] and not re.search(r'[a-z]', password):
            errors.append("密码必须包含至少一个小写字母")

        # 数字检查
        if policy['require_digits'] and not re.search(r'\d', password):
            errors.append("密码必须包含至少一个数字")

        # 特殊字符检查
        if policy['require_special_chars'] and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("密码必须包含至少一个特殊字符")

        # 禁用模式检查
        password_lower = password.lower()
        for pattern in policy['forbidden_patterns']:
            if pattern.lower() in password_lower:
                errors.append(f"密码不能包含常见模式: {pattern}")

        # 用户名检查
        if username and username.lower() in password_lower:
            errors.append("密码不能包含用户名")

        return len(errors) == 0, errors

    def validate_session(self, session_info: Dict[str, Any]) -> Tuple[bool, str]:
        """验证会话是否符合策略"""
        policy = self.policies['session_policy']

        # 检查空闲超时
        if 'last_activity' in session_info:
            last_activity = datetime.fromisoformat(session_info['last_activity'])
            idle_time = (datetime.utcnow() - last_activity).total_seconds()
            if idle_time > policy['max_idle_time']:
                return False, "会话空闲超时"

        # 检查绝对超时
        if 'created_at' in session_info:
            created_at = datetime.fromisoformat(session_info['created_at'])
            session_age = (datetime.utcnow() - created_at).total_seconds()
            if session_age > policy['absolute_timeout']:
                return False, "会话绝对超时"

        return True, "会话有效"

    def validate_request(self, request_info: Dict[str, Any]) -> Tuple[bool, str]:
        """验证请求是否符合策略"""
        policy = self.policies['access_policy']

        # 检查HTTPS要求
        if policy['require_https'] and not request_info.get('is_https', False):
            return False, "需要使用HTTPS"

        # 检查HTTP方法
        method = request_info.get('method', '').upper()
        if method not in policy['allowed_http_methods']:
            return False, f"不允许的HTTP方法: {method}"

        # 检查请求大小
        content_length = request_info.get('content_length', 0)
        if content_length > policy['max_request_size']:
            return False, f"请求大小超过限制: {content_length} > {policy['max_request_size']}"

        return True, "请求有效"

    def validate_file_upload(self, file_info: Dict[str, Any]) -> Tuple[bool, str]:
        """验证文件上传是否符合策略"""
        policy = self.policies['upload_policy']

        # 检查文件扩展名
        filename = file_info.get('filename', '')
        if filename:
            _, ext = os.path.splitext(filename.lower())
            if ext not in policy['allowed_extensions']:
                return False, f"不允许的文件类型: {ext}"

        # 检查文件大小
        file_size = file_info.get('size', 0)
        if file_size > policy['max_file_size']:
            return False, f"文件大小超过限制: {file_size} > {policy['max_file_size']}"

        return True, "文件上传有效"

    def record_violation(self, policy_type: str, violation_details: Dict[str, Any]):
        """记录策略违规"""
        violation = {
            'timestamp': datetime.utcnow().isoformat(),
            'policy_type': policy_type,
            'details': violation_details
        }
        self.violations.append(violation)

    def get_policy(self, policy_name: str) -> Optional[Dict[str, Any]]:
        """获取指定策略"""
        return self.policies.get(policy_name)

    def update_policy(self, policy_name: str, policy_config: Dict[str, Any]) -> bool:
        """更新策略配置"""
        if policy_name in self.policies:
            self.policies[policy_name].update(policy_config)
            return True
        return False

    def get_violation_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """获取违规统计"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_violations = [
            v for v in self.violations
            if datetime.fromisoformat(v['timestamp']) > cutoff_time
        ]

        stats = {
            'total_violations': len(recent_violations),
            'by_policy_type': defaultdict(int),
            'by_hour': defaultdict(int)
        }

        for violation in recent_violations:
            stats['by_policy_type'][violation['policy_type']] += 1
            hour = datetime.fromisoformat(violation['timestamp']).hour
            stats['by_hour'][hour] += 1

        return {
            'total_violations': stats['total_violations'],
            'by_policy_type': dict(stats['by_policy_type']),
            'by_hour': dict(stats['by_hour']),
            'time_range_hours': hours
        }


class AccessValidator:
    """访问验证器 - 综合访问控制"""

    def __init__(self, whitelist_file: str = None):
        """初始化访问验证器"""
        self.ip_whitelist = IPWhitelist(whitelist_file)
        self.rate_limiter = RateLimiter()
        self.security_policy = SecurityPolicy()

        # 访问记录
        self.access_log = deque(maxlen=10000)

        # 可疑活动模式
        self.suspicious_patterns = {
            'user_agents': [
                r'sqlmap', r'nikto', r'nessus', r'burp', r'nmap',
                r'curl.*', r'wget.*', r'python-requests'
            ],
            'paths': [
                r'\.\./', r'/etc/passwd', r'/admin', r'wp-admin',
                r'phpMyAdmin', r'/config', r'/backup'
            ],
            'parameters': [
                r'<script', r'javascript:', r'union.*select',
                r'drop.*table', r'exec\(', r'eval\('
            ]
        }

    def validate_access(
        self,
        ip_address: str,
        user_id: Optional[str] = None,
        resource: str = None,
        action: str = None,
        request_info: Dict[str, Any] = None
    ) -> Tuple[AccessResult, Dict[str, Any]]:
        """验证访问请求"""

        access_details = {
            'ip_address': ip_address,
            'user_id': user_id,
            'resource': resource,
            'action': action,
            'timestamp': datetime.utcnow().isoformat()
        }

        # 1. 检查IP白名单（如果启用）
        if self.security_policy.get_policy('access_policy').get('enable_ip_whitelist', False):
            if not self.ip_whitelist.is_allowed(ip_address):
                result = AccessResult.IP_BLOCKED
                reason = "IP不在白名单中"
                self._log_access_attempt(ip_address, user_id, resource, action, result, reason)
                return result, {'reason': reason, 'details': access_details}

        # 2. 检查速率限制
        # 全局速率限制
        allowed, limit_info = self.rate_limiter.check_rate_limit('global')
        if not allowed:
            result = AccessResult.RATE_LIMITED
            reason = "全局速率限制超出"
            self._log_access_attempt(ip_address, user_id, resource, action, result, reason)
            return result, {'reason': reason, 'limit_info': limit_info, 'details': access_details}

        # IP速率限制
        allowed, limit_info = self.rate_limiter.check_rate_limit('per_ip', ip_address)
        if not allowed:
            result = AccessResult.RATE_LIMITED
            reason = "IP速率限制超出"
            self._log_access_attempt(ip_address, user_id, resource, action, result, reason)
            return result, {'reason': reason, 'limit_info': limit_info, 'details': access_details}

        # 用户速率限制
        if user_id:
            allowed, limit_info = self.rate_limiter.check_rate_limit('per_user', user_id)
            if not allowed:
                result = AccessResult.RATE_LIMITED
                reason = "用户速率限制超出"
                self._log_access_attempt(ip_address, user_id, resource, action, result, reason)
                return result, {'reason': reason, 'limit_info': limit_info, 'details': access_details}

        # 3. 检查请求策略
        if request_info:
            is_valid, validation_message = self.security_policy.validate_request(request_info)
            if not is_valid:
                result = AccessResult.DENIED
                reason = f"请求策略违规: {validation_message}"
                self._log_access_attempt(ip_address, user_id, resource, action, result, reason)
                self.security_policy.record_violation('access_policy', {
                    'ip_address': ip_address,
                    'user_id': user_id,
                    'violation': validation_message,
                    'request_info': request_info
                })
                return result, {'reason': reason, 'details': access_details}

        # 4. 检查可疑活动
        suspicious_score = self._calculate_suspicious_score(request_info or {})
        if suspicious_score > 0.7:  # 可疑分数阈值
            result = AccessResult.SUSPICIOUS
            reason = f"检测到可疑活动 (分数: {suspicious_score:.2f})"
            self._log_access_attempt(ip_address, user_id, resource, action, result, reason)
            return result, {'reason': reason, 'suspicious_score': suspicious_score, 'details': access_details}

        # 5. 访问允许
        result = AccessResult.ALLOWED
        self._log_access_attempt(ip_address, user_id, resource, action, result)
        return result, {'reason': 'access_granted', 'details': access_details}

    def _calculate_suspicious_score(self, request_info: Dict[str, Any]) -> float:
        """计算可疑活动分数"""
        score = 0.0
        max_score = 1.0

        # 检查用户代理
        user_agent = request_info.get('user_agent', '')
        if user_agent:
            for pattern in self.suspicious_patterns['user_agents']:
                if re.search(pattern, user_agent, re.IGNORECASE):
                    score += 0.3
                    break

        # 检查请求路径
        path = request_info.get('path', '')
        if path:
            for pattern in self.suspicious_patterns['paths']:
                if re.search(pattern, path, re.IGNORECASE):
                    score += 0.4
                    break

        # 检查请求参数
        params = request_info.get('params', {})
        if params:
            param_string = json.dumps(params, ensure_ascii=False).lower()
            for pattern in self.suspicious_patterns['parameters']:
                if re.search(pattern, param_string, re.IGNORECASE):
                    score += 0.5
                    break

        # 检查请求头
        headers = request_info.get('headers', {})
        suspicious_headers = ['x-forwarded-for', 'x-real-ip', 'x-originating-ip']
        if any(header.lower() in [h.lower() for h in headers.keys()] for header in suspicious_headers):
            # 有代理头，略微增加可疑分数
            score += 0.1

        return min(score, max_score)

    def _log_access_attempt(
        self,
        ip_address: str,
        user_id: Optional[str],
        resource: str,
        action: str,
        result: AccessResult,
        reason: str = None,
        user_agent: str = None
    ):
        """记录访问尝试"""
        attempt = AccessAttempt(
            ip_address=ip_address,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            resource=resource or 'unknown',
            action=action or 'unknown',
            result=result,
            reason=reason,
            user_agent=user_agent
        )
        self.access_log.append(attempt)

    def get_access_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """获取访问统计"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_attempts = [
            attempt for attempt in self.access_log
            if attempt.timestamp > cutoff_time
        ]

        stats = {
            'total_attempts': len(recent_attempts),
            'by_result': defaultdict(int),
            'by_ip': defaultdict(int),
            'by_user': defaultdict(int),
            'by_resource': defaultdict(int),
            'by_hour': defaultdict(int)
        }

        for attempt in recent_attempts:
            stats['by_result'][attempt.result.value] += 1
            stats['by_ip'][attempt.ip_address] += 1
            if attempt.user_id:
                stats['by_user'][attempt.user_id] += 1
            stats['by_resource'][attempt.resource] += 1
            stats['by_hour'][attempt.timestamp.hour] += 1

        return {
            'total_attempts': stats['total_attempts'],
            'by_result': dict(stats['by_result']),
            'top_ips': dict(sorted(stats['by_ip'].items(), key=lambda x: x[1], reverse=True)[:10]),
            'top_users': dict(sorted(stats['by_user'].items(), key=lambda x: x[1], reverse=True)[:10]),
            'top_resources': dict(sorted(stats['by_resource'].items(), key=lambda x: x[1], reverse=True)[:10]),
            'by_hour': dict(stats['by_hour']),
            'time_range_hours': hours
        }

    def get_blocked_ips(self) -> List[str]:
        """获取被阻止的IP列表"""
        return list(self.blocked_ips) if hasattr(self, 'blocked_ips') else []

    def block_ip(self, ip_address: str, duration_hours: int = 24):
        """阻止IP地址"""
        # 这里可以与威胁检测器集成
        pass

    def unblock_ip(self, ip_address: str):
        """解除IP阻止"""
        # 这里可以与威胁检测器集成
        pass