# -*- coding: utf-8 -*-
"""
数据保护模块
提供数据分类、数据库加密、字段级加密、令牌保险库等功能
"""

import json
import re
from typing import Dict, Any, List, Optional, Set, Union
from datetime import datetime, timedelta
from enum import Enum
import asyncio
from pathlib import Path

from .encryption import EncryptionManager, AESEncryption


class DataClassification(Enum):
    """数据分类级别"""
    PUBLIC = "public"           # 公开数据
    INTERNAL = "internal"       # 内部数据
    CONFIDENTIAL = "confidential"  # 机密数据
    RESTRICTED = "restricted"   # 限制级数据


class SensitiveDataPattern:
    """敏感数据模式"""

    PATTERNS = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        'id_card': r'\b\d{15}|\d{18}\b',  # 身份证号
        'credit_card': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        'ip_address': r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
        'password': r'(password|pwd|pass)[\s]*[:=][\s]*[\'"]?([^\s\'"]+)',
        'api_key': r'(api[_-]?key|secret[_-]?key)[\s]*[:=][\s]*[\'"]?([A-Za-z0-9]{20,})',
        'jwt_token': r'eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*'
    }

    @classmethod
    def detect_sensitive_data(cls, text: str) -> Dict[str, List[str]]:
        """检测敏感数据"""
        results = {}

        for pattern_name, pattern in cls.PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                if pattern_name in ['password', 'api_key']:
                    # 对于包含组的模式，取第二个组
                    results[pattern_name] = [match[1] if isinstance(match, tuple) else match for match in matches]
                else:
                    results[pattern_name] = [match if isinstance(match, str) else match[0] for match in matches]

        return results

    @classmethod
    def mask_sensitive_data(cls, text: str, mask_char: str = '*') -> str:
        """遮蔽敏感数据"""
        masked_text = text

        for pattern_name, pattern in cls.PATTERNS.items():
            if pattern_name == 'email':
                # 邮箱特殊处理：保留域名部分
                masked_text = re.sub(
                    pattern,
                    lambda m: f"{m.group(0).split('@')[0][:2]}{'*' * 4}@{m.group(0).split('@')[1]}",
                    masked_text,
                    flags=re.IGNORECASE
                )
            elif pattern_name in ['password', 'api_key']:
                # 密码和API密钥完全遮蔽
                masked_text = re.sub(
                    pattern,
                    lambda m: f"{m.group(1)}{'*' * 8}",
                    masked_text,
                    flags=re.IGNORECASE
                )
            else:
                # 其他类型部分遮蔽
                matches = re.finditer(pattern, masked_text, re.IGNORECASE)
                for match in reversed(list(matches)):
                    original = match.group(0)
                    if len(original) <= 4:
                        masked = mask_char * len(original)
                    else:
                        masked = original[:2] + mask_char * (len(original) - 4) + original[-2:]
                    masked_text = masked_text[:match.start()] + masked + masked_text[match.end():]

        return masked_text


class DataClassifier:
    """数据分类器"""

    def __init__(self):
        """初始化数据分类器"""
        self.classification_rules = {
            DataClassification.RESTRICTED: [
                'password', 'secret', 'private_key', 'token', 'credential',
                'id_card', 'ssn', 'passport', 'credit_card'
            ],
            DataClassification.CONFIDENTIAL: [
                'email', 'phone', 'address', 'api_key', 'session_id',
                'user_id', 'account', 'financial'
            ],
            DataClassification.INTERNAL: [
                'internal', 'config', 'setting', 'log', 'debug',
                'system', 'server', 'database'
            ],
            DataClassification.PUBLIC: [
                'public', 'open', 'general', 'common'
            ]
        }

    def classify_field(self, field_name: str, field_value: Any = None) -> DataClassification:
        """分类字段数据"""
        field_name_lower = field_name.lower()

        # 检查字段名
        for classification, keywords in self.classification_rules.items():
            if any(keyword in field_name_lower for keyword in keywords):
                return classification

        # 检查字段值中的敏感数据模式
        if field_value and isinstance(field_value, str):
            sensitive_patterns = SensitiveDataPattern.detect_sensitive_data(field_value)
            if sensitive_patterns:
                if any(pattern in ['password', 'api_key', 'jwt_token'] for pattern in sensitive_patterns):
                    return DataClassification.RESTRICTED
                elif any(pattern in ['email', 'phone', 'id_card', 'credit_card'] for pattern in sensitive_patterns):
                    return DataClassification.CONFIDENTIAL

        return DataClassification.INTERNAL

    def classify_document(self, document: Dict[str, Any]) -> Dict[str, DataClassification]:
        """分类文档中的所有字段"""
        classifications = {}

        def classify_recursive(obj: Any, prefix: str = ""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    full_key = f"{prefix}.{key}" if prefix else key
                    classifications[full_key] = self.classify_field(key, value)
                    if isinstance(value, (dict, list)):
                        classify_recursive(value, full_key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    if isinstance(item, (dict, list)):
                        classify_recursive(item, f"{prefix}[{i}]")

        classify_recursive(document)
        return classifications

    def get_highest_classification(self, document: Dict[str, Any]) -> DataClassification:
        """获取文档的最高分类级别"""
        classifications = self.classify_document(document)

        # 按优先级排序
        priority_order = [
            DataClassification.RESTRICTED,
            DataClassification.CONFIDENTIAL,
            DataClassification.INTERNAL,
            DataClassification.PUBLIC
        ]

        for classification in priority_order:
            if classification in classifications.values():
                return classification

        return DataClassification.PUBLIC


class FieldLevelEncryption:
    """字段级加密"""

    def __init__(self, encryption_manager: EncryptionManager):
        """初始化字段级加密"""
        self.encryption_manager = encryption_manager
        self.data_classifier = DataClassifier()

        # 加密策略配置
        self.encryption_policies = {
            DataClassification.RESTRICTED: {'algorithm': 'aes', 'key_rotation_days': 30},
            DataClassification.CONFIDENTIAL: {'algorithm': 'aes', 'key_rotation_days': 90},
            DataClassification.INTERNAL: {'algorithm': 'aes', 'key_rotation_days': 365},
            DataClassification.PUBLIC: None  # 不加密
        }

    def encrypt_document(self, document: Dict[str, Any], force_encrypt: List[str] = None) -> Dict[str, Any]:
        """加密文档中的敏感字段"""
        force_encrypt = force_encrypt or []
        classifications = self.data_classifier.classify_document(document)

        encrypted_doc = {}
        encryption_metadata = {}

        def process_object(obj: Any, prefix: str = "") -> Any:
            if isinstance(obj, dict):
                result = {}
                for key, value in obj.items():
                    full_key = f"{prefix}.{key}" if prefix else key
                    classification = classifications.get(full_key, DataClassification.PUBLIC)

                    # 决定是否需要加密
                    should_encrypt = (
                        classification in [DataClassification.RESTRICTED, DataClassification.CONFIDENTIAL] or
                        key in force_encrypt or
                        full_key in force_encrypt
                    )

                    if should_encrypt and isinstance(value, (str, int, float)):
                        # 加密字段
                        encrypted_data = self._encrypt_field_value(value, classification)
                        result[key] = encrypted_data['ciphertext']

                        # 保存加密元数据
                        encryption_metadata[full_key] = {
                            'encrypted': True,
                            'algorithm': encrypted_data['algorithm'],
                            'key_id': encrypted_data['key_id'],
                            'classification': classification.value,
                            'encrypted_at': datetime.utcnow().isoformat()
                        }
                    else:
                        # 递归处理嵌套对象
                        if isinstance(value, (dict, list)):
                            result[key] = process_object(value, full_key)
                        else:
                            result[key] = value

                        encryption_metadata[full_key] = {
                            'encrypted': False,
                            'classification': classification.value
                        }

                return result

            elif isinstance(obj, list):
                return [process_object(item, f"{prefix}[{i}]") for i, item in enumerate(obj)]
            else:
                return obj

        encrypted_doc = process_object(document)
        encrypted_doc['_encryption_metadata'] = encryption_metadata

        return encrypted_doc

    def decrypt_document(self, encrypted_document: Dict[str, Any]) -> Dict[str, Any]:
        """解密文档中的加密字段"""
        if '_encryption_metadata' not in encrypted_document:
            return encrypted_document

        metadata = encrypted_document['_encryption_metadata']
        decrypted_doc = encrypted_document.copy()
        del decrypted_doc['_encryption_metadata']

        def process_object(obj: Any, prefix: str = "") -> Any:
            if isinstance(obj, dict):
                result = {}
                for key, value in obj.items():
                    full_key = f"{prefix}.{key}" if prefix else key
                    field_metadata = metadata.get(full_key, {})

                    if field_metadata.get('encrypted', False):
                        # 解密字段
                        encrypted_data = {
                            'ciphertext': value,
                            'algorithm': field_metadata['algorithm'],
                            'key_id': field_metadata['key_id']
                        }

                        try:
                            decrypted_value = self._decrypt_field_value(encrypted_data)
                            result[key] = decrypted_value
                        except Exception as e:
                            result[key] = f"[解密失败: {str(e)}]"
                    else:
                        # 递归处理嵌套对象
                        if isinstance(value, (dict, list)):
                            result[key] = process_object(value, full_key)
                        else:
                            result[key] = value

                return result

            elif isinstance(obj, list):
                return [process_object(item, f"{prefix}[{i}]") for i, item in enumerate(obj)]
            else:
                return obj

        return process_object(decrypted_doc)

    def _encrypt_field_value(self, value: Any, classification: DataClassification) -> Dict[str, Any]:
        """加密字段值"""
        policy = self.encryption_policies.get(classification)
        if not policy:
            raise ValueError(f"没有为分类 {classification.value} 定义加密策略")

        # 将值转换为字节
        if isinstance(value, str):
            value_bytes = value.encode('utf-8')
        else:
            value_bytes = str(value).encode('utf-8')

        # 加密
        return self.encryption_manager.encrypt_data(value_bytes, algorithm=policy['algorithm'])

    def _decrypt_field_value(self, encrypted_data: Dict[str, Any]) -> str:
        """解密字段值"""
        decrypted_bytes = self.encryption_manager.decrypt_data(encrypted_data)
        return decrypted_bytes.decode('utf-8')


class TokenVault:
    """令牌保险库 - 安全存储和管理敏感令牌"""

    def __init__(self, encryption_manager: EncryptionManager, vault_file: str = None):
        """初始化令牌保险库"""
        self.encryption_manager = encryption_manager
        self.vault_file = Path(vault_file or "/app/data/token_vault.json")
        self.vault_file.parent.mkdir(parents=True, exist_ok=True)
        self._tokens = {}
        self._load_vault()

    def store_token(
        self,
        token_id: str,
        token_value: str,
        token_type: str = "generic",
        expires_at: Optional[datetime] = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """存储令牌"""
        try:
            # 加密令牌值
            encrypted_token = self.encryption_manager.encrypt_data(token_value.encode('utf-8'))

            token_record = {
                'id': token_id,
                'type': token_type,
                'encrypted_value': encrypted_token,
                'created_at': datetime.utcnow().isoformat(),
                'expires_at': expires_at.isoformat() if expires_at else None,
                'metadata': metadata or {},
                'access_count': 0,
                'last_accessed': None
            }

            self._tokens[token_id] = token_record
            self._save_vault()
            return True

        except Exception as e:
            print(f"存储令牌失败: {e}")
            return False

    def retrieve_token(self, token_id: str) -> Optional[str]:
        """检索令牌"""
        if token_id not in self._tokens:
            return None

        token_record = self._tokens[token_id]

        # 检查过期时间
        if token_record['expires_at']:
            expires_at = datetime.fromisoformat(token_record['expires_at'])
            if datetime.utcnow() > expires_at:
                self.delete_token(token_id)
                return None

        try:
            # 解密令牌值
            encrypted_data = token_record['encrypted_value']
            decrypted_bytes = self.encryption_manager.decrypt_data(encrypted_data)
            token_value = decrypted_bytes.decode('utf-8')

            # 更新访问统计
            token_record['access_count'] += 1
            token_record['last_accessed'] = datetime.utcnow().isoformat()
            self._save_vault()

            return token_value

        except Exception as e:
            print(f"检索令牌失败: {e}")
            return None

    def delete_token(self, token_id: str) -> bool:
        """删除令牌"""
        if token_id in self._tokens:
            del self._tokens[token_id]
            self._save_vault()
            return True
        return False

    def list_tokens(self, token_type: str = None) -> List[Dict[str, Any]]:
        """列出令牌（不包含实际值）"""
        tokens = []

        for token_id, token_record in self._tokens.items():
            if token_type and token_record['type'] != token_type:
                continue

            # 检查过期
            is_expired = False
            if token_record['expires_at']:
                expires_at = datetime.fromisoformat(token_record['expires_at'])
                is_expired = datetime.utcnow() > expires_at

            tokens.append({
                'id': token_id,
                'type': token_record['type'],
                'created_at': token_record['created_at'],
                'expires_at': token_record['expires_at'],
                'expired': is_expired,
                'access_count': token_record['access_count'],
                'last_accessed': token_record['last_accessed'],
                'metadata': token_record['metadata']
            })

        return tokens

    def cleanup_expired_tokens(self) -> int:
        """清理过期令牌"""
        expired_tokens = []
        now = datetime.utcnow()

        for token_id, token_record in self._tokens.items():
            if token_record['expires_at']:
                expires_at = datetime.fromisoformat(token_record['expires_at'])
                if now > expires_at:
                    expired_tokens.append(token_id)

        for token_id in expired_tokens:
            del self._tokens[token_id]

        if expired_tokens:
            self._save_vault()

        return len(expired_tokens)

    def update_token_metadata(self, token_id: str, metadata: Dict[str, Any]) -> bool:
        """更新令牌元数据"""
        if token_id not in self._tokens:
            return False

        self._tokens[token_id]['metadata'].update(metadata)
        self._save_vault()
        return True

    def get_vault_statistics(self) -> Dict[str, Any]:
        """获取保险库统计信息"""
        now = datetime.utcnow()
        total_tokens = len(self._tokens)
        expired_tokens = 0
        token_types = {}

        for token_record in self._tokens.values():
            # 统计令牌类型
            token_type = token_record['type']
            token_types[token_type] = token_types.get(token_type, 0) + 1

            # 统计过期令牌
            if token_record['expires_at']:
                expires_at = datetime.fromisoformat(token_record['expires_at'])
                if now > expires_at:
                    expired_tokens += 1

        return {
            'total_tokens': total_tokens,
            'expired_tokens': expired_tokens,
            'active_tokens': total_tokens - expired_tokens,
            'token_types': token_types,
            'vault_file': str(self.vault_file),
            'last_updated': datetime.utcnow().isoformat()
        }

    def _load_vault(self):
        """加载保险库数据"""
        try:
            if self.vault_file.exists():
                with open(self.vault_file, 'r', encoding='utf-8') as f:
                    encrypted_vault = json.load(f)

                # 解密保险库数据
                if 'encrypted_data' in encrypted_vault:
                    decrypted_bytes = self.encryption_manager.decrypt_data(encrypted_vault['encrypted_data'])
                    self._tokens = json.loads(decrypted_bytes.decode('utf-8'))
                else:
                    # 兼容旧格式
                    self._tokens = encrypted_vault
        except Exception as e:
            print(f"加载令牌保险库失败: {e}")
            self._tokens = {}

    def _save_vault(self):
        """保存保险库数据"""
        try:
            # 加密整个保险库
            vault_json = json.dumps(self._tokens, ensure_ascii=False)
            encrypted_vault_data = self.encryption_manager.encrypt_data(vault_json.encode('utf-8'))

            vault_container = {
                'version': '1.0',
                'encrypted_data': encrypted_vault_data,
                'created_at': datetime.utcnow().isoformat()
            }

            # 原子写入
            temp_file = self.vault_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(vault_container, f, ensure_ascii=False, indent=2)

            temp_file.replace(self.vault_file)

        except Exception as e:
            print(f"保存令牌保险库失败: {e}")


class DatabaseEncryption:
    """数据库加密"""

    def __init__(self, encryption_manager: EncryptionManager):
        """初始化数据库加密"""
        self.encryption_manager = encryption_manager
        self.field_encryption = FieldLevelEncryption(encryption_manager)

    def encrypt_record(self, record: Dict[str, Any], table_name: str = None) -> Dict[str, Any]:
        """加密数据库记录"""
        # 可以根据表名定制加密策略
        encryption_fields = self._get_encryption_fields(table_name)
        return self.field_encryption.encrypt_document(record, encryption_fields)

    def decrypt_record(self, encrypted_record: Dict[str, Any]) -> Dict[str, Any]:
        """解密数据库记录"""
        return self.field_encryption.decrypt_document(encrypted_record)

    def _get_encryption_fields(self, table_name: str = None) -> List[str]:
        """获取需要加密的字段列表"""
        # 默认加密字段
        default_fields = ['password', 'email', 'phone', 'address', 'id_card']

        # 表特定的加密字段
        table_specific_fields = {
            'users': ['password', 'email', 'phone', 'real_name'],
            'game_records': ['player_info'],
            'system_config': ['api_keys', 'secrets'],
            'logs': []  # 日志表通常不加密，避免影响性能
        }

        if table_name and table_name in table_specific_fields:
            return table_specific_fields[table_name]

        return default_fields