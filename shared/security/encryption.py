# -*- coding: utf-8 -*-
"""
数据加密模块
提供AES、RSA加密、哈希和随机数生成功能
"""

import os
import base64
import hashlib
import secrets
from typing import Optional, Tuple, Dict, Any
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


class SecureRandom:
    """安全随机数生成器"""

    @staticmethod
    def generate_bytes(length: int) -> bytes:
        """生成指定长度的随机字节"""
        return secrets.token_bytes(length)

    @staticmethod
    def generate_string(length: int = 32) -> str:
        """生成随机字符串"""
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_hex(length: int = 32) -> str:
        """生成十六进制随机字符串"""
        return secrets.token_hex(length)

    @staticmethod
    def generate_int(min_value: int = 0, max_value: int = 2**32 - 1) -> int:
        """生成指定范围的随机整数"""
        return secrets.randbelow(max_value - min_value + 1) + min_value


class HashManager:
    """哈希管理器"""

    ALGORITHMS = {
        'sha256': hashlib.sha256,
        'sha512': hashlib.sha512,
        'blake2b': hashlib.blake2b,
        'blake2s': hashlib.blake2s
    }

    @classmethod
    def hash_data(cls, data: bytes, algorithm: str = 'sha256', salt: Optional[bytes] = None) -> str:
        """计算数据哈希值"""
        if algorithm not in cls.ALGORITHMS:
            raise ValueError(f"不支持的哈希算法: {algorithm}")

        hasher = cls.ALGORITHMS[algorithm]()

        if salt:
            hasher.update(salt)
        hasher.update(data)

        return base64.b64encode(hasher.digest()).decode('utf-8')

    @classmethod
    def verify_hash(cls, data: bytes, hash_value: str, algorithm: str = 'sha256', salt: Optional[bytes] = None) -> bool:
        """验证哈希值"""
        computed_hash = cls.hash_data(data, algorithm, salt)
        return secrets.compare_digest(computed_hash, hash_value)

    @classmethod
    def pbkdf2_derive_key(cls, password: bytes, salt: bytes, iterations: int = 100000, key_length: int = 32) -> bytes:
        """使用PBKDF2生成密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=key_length,
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        return kdf.derive(password)


class AESEncryption:
    """AES加密/解密"""

    def __init__(self, key: Optional[bytes] = None):
        """初始化AES加密器"""
        self.key = key or SecureRandom.generate_bytes(32)  # 256位密钥
        if len(self.key) not in [16, 24, 32]:
            raise ValueError("AES密钥长度必须为16、24或32字节")

    @classmethod
    def from_password(cls, password: str, salt: Optional[bytes] = None) -> 'AESEncryption':
        """从密码生成AES加密器"""
        if salt is None:
            salt = SecureRandom.generate_bytes(16)
        key = HashManager.pbkdf2_derive_key(password.encode('utf-8'), salt)
        return cls(key)

    def encrypt(self, plaintext: bytes) -> Dict[str, str]:
        """加密数据"""
        # 生成随机IV
        iv = SecureRandom.generate_bytes(16)

        # 创建加密器
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()

        # PKCS7填充
        padded_data = self._pad_data(plaintext)

        # 加密
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        return {
            'ciphertext': base64.b64encode(ciphertext).decode('utf-8'),
            'iv': base64.b64encode(iv).decode('utf-8'),
            'key_id': self._get_key_id()
        }

    def decrypt(self, encrypted_data: Dict[str, str]) -> bytes:
        """解密数据"""
        ciphertext = base64.b64decode(encrypted_data['ciphertext'])
        iv = base64.b64decode(encrypted_data['iv'])

        # 创建解密器
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()

        # 解密
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        # 去除填充
        return self._unpad_data(padded_plaintext)

    def _pad_data(self, data: bytes) -> bytes:
        """PKCS7填充"""
        padding_length = 16 - (len(data) % 16)
        padding = bytes([padding_length] * padding_length)
        return data + padding

    def _unpad_data(self, padded_data: bytes) -> bytes:
        """去除PKCS7填充"""
        padding_length = padded_data[-1]
        return padded_data[:-padding_length]

    def _get_key_id(self) -> str:
        """获取密钥ID"""
        return HashManager.hash_data(self.key, 'sha256')[:16]

    def get_key_base64(self) -> str:
        """获取Base64编码的密钥"""
        return base64.b64encode(self.key).decode('utf-8')

    @classmethod
    def from_key_base64(cls, key_b64: str) -> 'AESEncryption':
        """从Base64密钥创建加密器"""
        key = base64.b64decode(key_b64)
        return cls(key)


class RSAEncryption:
    """RSA加密/解密和签名"""

    def __init__(self, private_key: Optional[rsa.RSAPrivateKey] = None, public_key: Optional[rsa.RSAPublicKey] = None):
        """初始化RSA加密器"""
        self.private_key = private_key
        self.public_key = public_key or (private_key.public_key() if private_key else None)

    @classmethod
    def generate_keypair(cls, key_size: int = 2048) -> 'RSAEncryption':
        """生成RSA密钥对"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        return cls(private_key=private_key)

    def encrypt(self, plaintext: bytes) -> str:
        """使用公钥加密"""
        if not self.public_key:
            raise ValueError("需要公钥进行加密")

        ciphertext = self.public_key.encrypt(
            plaintext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.b64encode(ciphertext).decode('utf-8')

    def decrypt(self, ciphertext_b64: str) -> bytes:
        """使用私钥解密"""
        if not self.private_key:
            raise ValueError("需要私钥进行解密")

        ciphertext = base64.b64decode(ciphertext_b64)
        plaintext = self.private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return plaintext

    def sign(self, message: bytes) -> str:
        """使用私钥签名"""
        if not self.private_key:
            raise ValueError("需要私钥进行签名")

        signature = self.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')

    def verify_signature(self, message: bytes, signature_b64: str) -> bool:
        """验证签名"""
        if not self.public_key:
            raise ValueError("需要公钥验证签名")

        try:
            signature = base64.b64decode(signature_b64)
            self.public_key.verify(
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False

    def export_private_key(self, password: Optional[bytes] = None) -> str:
        """导出私钥"""
        if not self.private_key:
            raise ValueError("没有私钥可导出")

        encryption_algorithm = serialization.NoEncryption()
        if password:
            encryption_algorithm = serialization.BestAvailableEncryption(password)

        pem = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption_algorithm
        )
        return pem.decode('utf-8')

    def export_public_key(self) -> str:
        """导出公钥"""
        if not self.public_key:
            raise ValueError("没有公钥可导出")

        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem.decode('utf-8')

    @classmethod
    def load_private_key(cls, pem_data: str, password: Optional[bytes] = None) -> 'RSAEncryption':
        """加载私钥"""
        private_key = serialization.load_pem_private_key(
            pem_data.encode('utf-8'),
            password=password,
            backend=default_backend()
        )
        return cls(private_key=private_key)

    @classmethod
    def load_public_key(cls, pem_data: str) -> 'RSAEncryption':
        """加载公钥"""
        public_key = serialization.load_pem_public_key(
            pem_data.encode('utf-8'),
            backend=default_backend()
        )
        return cls(public_key=public_key)


class EncryptionManager:
    """加密管理器 - 统一管理各种加密功能"""

    def __init__(self):
        """初始化加密管理器"""
        self._aes_keys: Dict[str, AESEncryption] = {}
        self._rsa_keys: Dict[str, RSAEncryption] = {}
        self._default_aes_key = None
        self._default_rsa_key = None

    def create_aes_key(self, key_id: str, password: Optional[str] = None) -> str:
        """创建AES密钥"""
        if password:
            aes_enc = AESEncryption.from_password(password)
        else:
            aes_enc = AESEncryption()

        self._aes_keys[key_id] = aes_enc
        if self._default_aes_key is None:
            self._default_aes_key = key_id

        return aes_enc.get_key_base64()

    def create_rsa_keypair(self, key_id: str, key_size: int = 2048) -> Tuple[str, str]:
        """创建RSA密钥对"""
        rsa_enc = RSAEncryption.generate_keypair(key_size)
        self._rsa_keys[key_id] = rsa_enc

        if self._default_rsa_key is None:
            self._default_rsa_key = key_id

        return rsa_enc.export_private_key(), rsa_enc.export_public_key()

    def encrypt_data(self, data: bytes, key_id: Optional[str] = None, algorithm: str = 'aes') -> Dict[str, Any]:
        """加密数据"""
        if algorithm == 'aes':
            key_id = key_id or self._default_aes_key
            if key_id not in self._aes_keys:
                raise ValueError(f"AES密钥 {key_id} 不存在")

            result = self._aes_keys[key_id].encrypt(data)
            result['algorithm'] = 'aes'
            result['key_id'] = key_id
            return result

        elif algorithm == 'rsa':
            key_id = key_id or self._default_rsa_key
            if key_id not in self._rsa_keys:
                raise ValueError(f"RSA密钥 {key_id} 不存在")

            ciphertext = self._rsa_keys[key_id].encrypt(data)
            return {
                'ciphertext': ciphertext,
                'algorithm': 'rsa',
                'key_id': key_id
            }
        else:
            raise ValueError(f"不支持的加密算法: {algorithm}")

    def decrypt_data(self, encrypted_data: Dict[str, Any]) -> bytes:
        """解密数据"""
        algorithm = encrypted_data['algorithm']
        key_id = encrypted_data['key_id']

        if algorithm == 'aes':
            if key_id not in self._aes_keys:
                raise ValueError(f"AES密钥 {key_id} 不存在")
            return self._aes_keys[key_id].decrypt(encrypted_data)

        elif algorithm == 'rsa':
            if key_id not in self._rsa_keys:
                raise ValueError(f"RSA密钥 {key_id} 不存在")
            return self._rsa_keys[key_id].decrypt(encrypted_data['ciphertext'])
        else:
            raise ValueError(f"不支持的解密算法: {algorithm}")

    def sign_data(self, data: bytes, key_id: Optional[str] = None) -> str:
        """签名数据"""
        key_id = key_id or self._default_rsa_key
        if key_id not in self._rsa_keys:
            raise ValueError(f"RSA密钥 {key_id} 不存在")
        return self._rsa_keys[key_id].sign(data)

    def verify_signature(self, data: bytes, signature: str, key_id: Optional[str] = None) -> bool:
        """验证签名"""
        key_id = key_id or self._default_rsa_key
        if key_id not in self._rsa_keys:
            raise ValueError(f"RSA密钥 {key_id} 不存在")
        return self._rsa_keys[key_id].verify_signature(data, signature)

    def get_key_info(self) -> Dict[str, Any]:
        """获取密钥信息"""
        return {
            'aes_keys': list(self._aes_keys.keys()),
            'rsa_keys': list(self._rsa_keys.keys()),
            'default_aes': self._default_aes_key,
            'default_rsa': self._default_rsa_key
        }

    def load_keys_from_config(self, config: Dict[str, Any]):
        """从配置加载密钥"""
        for key_id, key_data in config.get('aes_keys', {}).items():
            self._aes_keys[key_id] = AESEncryption.from_key_base64(key_data['key'])

        for key_id, key_data in config.get('rsa_keys', {}).items():
            if 'private_key' in key_data:
                self._rsa_keys[key_id] = RSAEncryption.load_private_key(key_data['private_key'])
            elif 'public_key' in key_data:
                self._rsa_keys[key_id] = RSAEncryption.load_public_key(key_data['public_key'])

        self._default_aes_key = config.get('default_aes_key')
        self._default_rsa_key = config.get('default_rsa_key')