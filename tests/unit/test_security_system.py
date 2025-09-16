# -*- coding: utf-8 -*-
"""
安全系统单元测试
测试数据加密、安全监控、访问控制等功能
"""

import sys
import os
import unittest
import asyncio
import tempfile
import json
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.security import (
    EncryptionManager,
    AESEncryption,
    RSAEncryption,
    SecurityMonitor,
    ThreatDetector,
    DataClassifier,
    TokenVault,
    AccessValidator,
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity,
    DataClassification,
    AccessResult
)


class TestEncryption(unittest.TestCase):
    """测试加密功能"""

    def setUp(self):
        """测试设置"""
        self.encryption_manager = EncryptionManager()

    def test_aes_encryption(self):
        """测试AES加密"""
        # 创建AES密钥
        key_id = "test_aes"
        aes_key = self.encryption_manager.create_aes_key(key_id)
        self.assertIsNotNone(aes_key)

        # 加密数据
        test_data = "这是测试数据"
        data_bytes = test_data.encode('utf-8')
        encrypted_result = self.encryption_manager.encrypt_data(data_bytes, key_id, 'aes')

        self.assertIn('ciphertext', encrypted_result)
        self.assertIn('iv', encrypted_result)
        self.assertEqual(encrypted_result['algorithm'], 'aes')

        # 解密数据
        decrypted_bytes = self.encryption_manager.decrypt_data(encrypted_result)
        decrypted_text = decrypted_bytes.decode('utf-8')
        self.assertEqual(decrypted_text, test_data)

    def test_rsa_encryption(self):
        """测试RSA加密"""
        # 创建RSA密钥对
        key_id = "test_rsa"
        private_key, public_key = self.encryption_manager.create_rsa_keypair(key_id)
        self.assertIsNotNone(private_key)
        self.assertIsNotNone(public_key)

        # 加密小数据（RSA有长度限制）
        test_data = "小数据"
        data_bytes = test_data.encode('utf-8')
        encrypted_result = self.encryption_manager.encrypt_data(data_bytes, key_id, 'rsa')

        self.assertIn('ciphertext', encrypted_result)
        self.assertEqual(encrypted_result['algorithm'], 'rsa')

        # 解密数据
        decrypted_bytes = self.encryption_manager.decrypt_data(encrypted_result)
        decrypted_text = decrypted_bytes.decode('utf-8')
        self.assertEqual(decrypted_text, test_data)

    def test_data_signing(self):
        """测试数据签名"""
        # 创建RSA密钥对
        key_id = "test_sign"
        self.encryption_manager.create_rsa_keypair(key_id)

        # 签名数据
        test_data = "需要签名的数据".encode('utf-8')
        signature = self.encryption_manager.sign_data(test_data, key_id)
        self.assertIsNotNone(signature)

        # 验证签名
        is_valid = self.encryption_manager.verify_signature(test_data, signature, key_id)
        self.assertTrue(is_valid)

        # 验证错误数据
        wrong_data = "错误的数据".encode('utf-8')
        is_valid = self.encryption_manager.verify_signature(wrong_data, signature, key_id)
        self.assertFalse(is_valid)


class TestSecurityMonitor(unittest.TestCase):
    """测试安全监控功能"""

    def setUp(self):
        """测试设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, "test_security.log")
        self.security_monitor = SecurityMonitor(self.log_file)

    def tearDown(self):
        """清理测试数据"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_threat_detection(self):
        """测试威胁检测"""
        detector = self.security_monitor.threat_detector

        # 测试SQL注入检测
        sql_injection_input = "'; DROP TABLE users; --"
        self.assertTrue(detector.detect_sql_injection(sql_injection_input))

        normal_input = "正常的搜索查询"
        self.assertFalse(detector.detect_sql_injection(normal_input))

        # 测试XSS检测
        xss_input = "<script>alert('xss')</script>"
        self.assertTrue(detector.detect_xss_attack(xss_input))

        normal_html = "<p>正常的HTML内容</p>"
        self.assertFalse(detector.detect_xss_attack(normal_html))

        # 测试可疑用户代理
        suspicious_ua = "sqlmap/1.4.7"
        self.assertTrue(detector.detect_suspicious_user_agent(suspicious_ua))

        normal_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        self.assertFalse(detector.detect_suspicious_user_agent(normal_ua))

    def test_brute_force_detection(self):
        """测试暴力破解检测"""
        detector = self.security_monitor.threat_detector
        ip = "192.168.1.100"

        # 模拟多次失败登录
        for i in range(6):  # 默认阈值是5次
            if i < 4:
                # 前4次不应该被检测
                result = detector.detect_brute_force(ip)
                self.assertFalse(result)
            else:
                # 第5次应该被检测
                result = detector.detect_brute_force(ip)
                self.assertTrue(result)

    def test_security_event_logging(self):
        """测试安全事件记录"""
        # 记录安全事件
        self.security_monitor.log_security_event(
            SecurityEventType.LOGIN_FAILURE,
            SecuritySeverity.MEDIUM,
            "192.168.1.100",
            user_id="test_user",
            details={"reason": "invalid_password"}
        )

        # 查询事件
        events = self.security_monitor.audit_logger.query_events(
            event_types=[SecurityEventType.LOGIN_FAILURE],
            limit=10
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, SecurityEventType.LOGIN_FAILURE)
        self.assertEqual(events[0].source_ip, "192.168.1.100")
        self.assertEqual(events[0].user_id, "test_user")

    def test_request_analysis(self):
        """测试请求分析"""
        # 正常请求
        normal_request = {
            'source_ip': '192.168.1.50',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'path': '/api/users',
            'method': 'GET',
            'search_query': '用户名搜索'
        }

        events = self.security_monitor.analyze_request(normal_request)
        self.assertEqual(len(events), 0)  # 正常请求不应该产生事件

        # 恶意请求
        malicious_request = {
            'source_ip': '192.168.1.666',
            'user_agent': 'sqlmap/1.4.7',
            'path': '/api/users',
            'method': 'POST',
            'username': "admin'; DROP TABLE users; --",
            'comment': "<script>alert('xss')</script>"
        }

        events = self.security_monitor.analyze_request(malicious_request)
        self.assertGreater(len(events), 0)  # 恶意请求应该产生事件

        # 检查是否检测到SQL注入
        sql_events = [e for e in events if e.event_type == SecurityEventType.SQL_INJECTION_ATTEMPT]
        self.assertGreater(len(sql_events), 0)

        # 检查是否检测到XSS
        xss_events = [e for e in events if e.event_type == SecurityEventType.XSS_ATTEMPT]
        self.assertGreater(len(xss_events), 0)


class TestDataClassification(unittest.TestCase):
    """测试数据分类功能"""

    def setUp(self):
        """测试设置"""
        self.data_classifier = DataClassifier()

    def test_field_classification(self):
        """测试字段分类"""
        # 测试限制级数据
        self.assertEqual(
            self.data_classifier.classify_field('password', 'secret123'),
            DataClassification.RESTRICTED
        )

        self.assertEqual(
            self.data_classifier.classify_field('api_key', 'sk-1234567890abcdef'),
            DataClassification.CONFIDENTIAL
        )

        # 测试机密数据
        self.assertEqual(
            self.data_classifier.classify_field('email', 'user@example.com'),
            DataClassification.CONFIDENTIAL
        )

        self.assertEqual(
            self.data_classifier.classify_field('phone', '13800138000'),
            DataClassification.CONFIDENTIAL
        )

        # 测试内部数据
        self.assertEqual(
            self.data_classifier.classify_field('config_setting', 'value'),
            DataClassification.INTERNAL
        )

        # 测试公开数据
        self.assertEqual(
            self.data_classifier.classify_field('public_info', 'information'),
            DataClassification.PUBLIC
        )

    def test_document_classification(self):
        """测试文档分类"""
        document = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'secret123',
            'preferences': {
                'theme': 'dark',
                'language': 'zh-CN'
            },
            'game_history': [
                {'date': '2024-01-01', 'result': 'win'},
                {'date': '2024-01-02', 'result': 'loss'}
            ]
        }

        classifications = self.data_classifier.classify_document(document)

        # 检查关键字段分类
        self.assertEqual(classifications['email'], DataClassification.CONFIDENTIAL)
        self.assertEqual(classifications['password'], DataClassification.RESTRICTED)

        # 检查最高分类级别
        highest = self.data_classifier.get_highest_classification(document)
        self.assertEqual(highest, DataClassification.RESTRICTED)


class TestTokenVault(unittest.TestCase):
    """测试令牌保险库功能"""

    def setUp(self):
        """测试设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.vault_file = os.path.join(self.temp_dir, "test_vault.json")
        self.encryption_manager = EncryptionManager()
        self.encryption_manager.create_aes_key("default")
        self.token_vault = TokenVault(self.encryption_manager, self.vault_file)

    def tearDown(self):
        """清理测试数据"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_token_storage_and_retrieval(self):
        """测试令牌存储和检索"""
        token_id = "test_token"
        token_value = "sk-1234567890abcdef"

        # 存储令牌
        success = self.token_vault.store_token(token_id, token_value, "api_key")
        self.assertTrue(success)

        # 检索令牌
        retrieved_value = self.token_vault.retrieve_token(token_id)
        self.assertEqual(retrieved_value, token_value)

        # 删除令牌
        success = self.token_vault.delete_token(token_id)
        self.assertTrue(success)

        # 检索已删除的令牌
        retrieved_value = self.token_vault.retrieve_token(token_id)
        self.assertIsNone(retrieved_value)

    def test_token_expiration(self):
        """测试令牌过期"""
        token_id = "expiring_token"
        token_value = "will_expire"
        expires_at = datetime.utcnow() - timedelta(seconds=1)  # 已过期

        # 存储过期令牌
        success = self.token_vault.store_token(
            token_id, token_value, "test", expires_at
        )
        self.assertTrue(success)

        # 检索过期令牌（应该返回None）
        retrieved_value = self.token_vault.retrieve_token(token_id)
        self.assertIsNone(retrieved_value)

    def test_token_listing(self):
        """测试令牌列表"""
        # 存储多个令牌
        tokens = [
            ("token1", "value1", "type1"),
            ("token2", "value2", "type1"),
            ("token3", "value3", "type2")
        ]

        for token_id, value, token_type in tokens:
            self.token_vault.store_token(token_id, value, token_type)

        # 获取所有令牌
        all_tokens = self.token_vault.list_tokens()
        self.assertEqual(len(all_tokens), 3)

        # 按类型过滤
        type1_tokens = self.token_vault.list_tokens("type1")
        self.assertEqual(len(type1_tokens), 2)

        type2_tokens = self.token_vault.list_tokens("type2")
        self.assertEqual(len(type2_tokens), 1)


class TestAccessValidator(unittest.TestCase):
    """测试访问验证功能"""

    def setUp(self):
        """测试设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.whitelist_file = os.path.join(self.temp_dir, "test_whitelist.json")
        self.access_validator = AccessValidator(self.whitelist_file)

    def tearDown(self):
        """清理测试数据"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ip_whitelist(self):
        """测试IP白名单"""
        whitelist = self.access_validator.ip_whitelist

        # 添加IP到白名单
        success = whitelist.add_ip("192.168.1.100")
        self.assertTrue(success)

        # 检查IP是否在白名单中
        self.assertTrue(whitelist.is_allowed("192.168.1.100"))
        self.assertFalse(whitelist.is_allowed("192.168.1.101"))

        # 添加网络段
        success = whitelist.add_network("10.0.0.0/24")
        self.assertTrue(success)

        # 检查网络段中的IP
        self.assertTrue(whitelist.is_allowed("10.0.0.50"))
        self.assertFalse(whitelist.is_allowed("10.0.1.50"))

    def test_rate_limiting(self):
        """测试速率限制"""
        rate_limiter = self.access_validator.rate_limiter

        # 设置测试限制：每分钟5次请求
        rate_limiter.set_rate_limit("test", 5, 60)

        ip = "192.168.1.200"

        # 前5次请求应该被允许
        for i in range(5):
            allowed, details = rate_limiter.check_rate_limit("test", ip)
            self.assertTrue(allowed)

        # 第6次请求应该被限制
        allowed, details = rate_limiter.check_rate_limit("test", ip)
        self.assertFalse(allowed)
        self.assertEqual(details['reason'], 'rate_limit_exceeded')

    def test_access_validation(self):
        """测试访问验证"""
        ip = "192.168.1.50"

        # 正常访问
        result, details = self.access_validator.validate_access(
            ip_address=ip,
            resource="/api/test",
            action="GET"
        )
        self.assertEqual(result, AccessResult.ALLOWED)

        # 恶意请求
        malicious_request_info = {
            'method': 'POST',
            'path': '/api/users',
            'user_agent': 'sqlmap/1.4.7',
            'params': {'id': "1' OR '1'='1"}
        }

        result, details = self.access_validator.validate_access(
            ip_address=ip,
            resource="/api/users",
            action="POST",
            request_info=malicious_request_info
        )
        self.assertEqual(result, AccessResult.SUSPICIOUS)


class TestSecurityIntegration(unittest.TestCase):
    """测试安全系统集成"""

    def setUp(self):
        """测试设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.encryption_manager = EncryptionManager()
        self.encryption_manager.create_aes_key("default")

        # 初始化各个组件
        self.security_monitor = SecurityMonitor(
            os.path.join(self.temp_dir, "security.log")
        )
        self.data_classifier = DataClassifier()
        self.token_vault = TokenVault(
            self.encryption_manager,
            os.path.join(self.temp_dir, "vault.json")
        )
        self.access_validator = AccessValidator(
            os.path.join(self.temp_dir, "whitelist.json")
        )

    def tearDown(self):
        """清理测试数据"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_end_to_end_security_flow(self):
        """测试端到端安全流程"""
        # 1. 数据加密存储
        sensitive_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'secret123',
            'api_key': 'sk-abcdef123456'
        }

        # 分类数据
        classifications = self.data_classifier.classify_document(sensitive_data)
        self.assertIn('password', [k for k, v in classifications.items() if v == DataClassification.RESTRICTED])

        # 加密敏感数据
        encrypted_password = self.encryption_manager.encrypt_data(
            sensitive_data['password'].encode('utf-8')
        )
        self.assertIn('ciphertext', encrypted_password)

        # 2. 令牌管理
        token_id = "user_session_token"
        session_token = "session_abcdef123456"

        success = self.token_vault.store_token(
            token_id, session_token, "session",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        self.assertTrue(success)

        # 3. 访问验证
        ip = "192.168.1.100"
        result, details = self.access_validator.validate_access(
            ip_address=ip,
            user_id="testuser",
            resource="/api/protected",
            action="GET"
        )
        self.assertEqual(result, AccessResult.ALLOWED)

        # 4. 安全事件记录
        self.security_monitor.log_security_event(
            SecurityEventType.DATA_ACCESS,
            SecuritySeverity.LOW,
            ip,
            user_id="testuser",
            resource="/api/protected",
            details={"classification": "confidential"}
        )

        # 5. 验证事件记录
        events = self.security_monitor.audit_logger.query_events(
            event_types=[SecurityEventType.DATA_ACCESS],
            limit=1
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].user_id, "testuser")


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)