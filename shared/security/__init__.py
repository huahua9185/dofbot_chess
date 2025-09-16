# -*- coding: utf-8 -*-
"""
安全模块
提供数据加密、通信安全、访问控制等功能
"""

from .encryption import (
    EncryptionManager,
    AESEncryption,
    RSAEncryption,
    SecureRandom,
    HashManager
)
from .secure_communication import (
    SecureChannel,
    TLSConfig,
    CertificateManager,
    MessageSigner
)
from .data_protection import (
    DataClassifier,
    DatabaseEncryption,
    FieldLevelEncryption,
    TokenVault
)
from .security_monitor import (
    SecurityMonitor,
    ThreatDetector,
    AuditLogger,
    SecurityEvent,
    SecurityEventType,
    SecuritySeverity
)
from .access_control import (
    IPWhitelist,
    RateLimiter,
    SecurityPolicy,
    AccessValidator,
    AccessResult
)
from .data_protection import (
    DataClassification
)

__all__ = [
    # 加密相关
    'EncryptionManager',
    'AESEncryption',
    'RSAEncryption',
    'SecureRandom',
    'HashManager',

    # 安全通信
    'SecureChannel',
    'TLSConfig',
    'CertificateManager',
    'MessageSigner',

    # 数据保护
    'DataClassifier',
    'DatabaseEncryption',
    'FieldLevelEncryption',
    'TokenVault',

    # 安全监控
    'SecurityMonitor',
    'ThreatDetector',
    'AuditLogger',
    'SecurityEvent',

    # 访问控制
    'IPWhitelist',
    'RateLimiter',
    'SecurityPolicy',
    'AccessValidator',
    'AccessResult',

    # 数据分类和事件
    'DataClassification',
    'SecurityEventType',
    'SecuritySeverity'
]