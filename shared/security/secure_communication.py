# -*- coding: utf-8 -*-
"""
安全通信模块
提供TLS配置、证书管理、消息签名等功能
"""

import os
import ssl
import json
import hashlib
import ipaddress
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import aiohttp
import asyncio
from pathlib import Path

from .encryption import RSAEncryption, HashManager


class CertificateManager:
    """证书管理器"""

    def __init__(self, cert_dir: str = None):
        """初始化证书管理器"""
        self.cert_dir = Path(cert_dir or "/app/certs")
        self.cert_dir.mkdir(parents=True, exist_ok=True)

    def generate_self_signed_cert(
        self,
        common_name: str,
        country: str = "CN",
        state: str = "Beijing",
        city: str = "Beijing",
        organization: str = "ChessRobot",
        email: str = "admin@chessrobot.local",
        valid_days: int = 365,
        key_size: int = 2048
    ) -> Tuple[str, str]:
        """生成自签名证书"""

        # 生成私钥
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )

        # 创建证书主体
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state),
            x509.NameAttribute(NameOID.LOCALITY_NAME, city),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            x509.NameAttribute(NameOID.EMAIL_ADDRESS, email)
        ])

        # 创建证书
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            subject  # 自签名，所以颁发者和主体相同
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=valid_days)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(common_name),
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=0),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                key_encipherment=True,
                digital_signature=True,
                key_cert_sign=True,
                key_agreement=False,
                content_commitment=False,
                data_encipherment=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False
            ),
            critical=True,
        ).sign(private_key, hashes.SHA256(), backend=default_backend())

        # 保存证书和私钥
        cert_path = self.cert_dir / f"{common_name}.crt"
        key_path = self.cert_dir / f"{common_name}.key"

        # 写入证书
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        # 写入私钥
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))

        return str(cert_path), str(key_path)

    def load_certificate_info(self, cert_path: str) -> Dict[str, Any]:
        """加载证书信息"""
        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read(), default_backend())

        return {
            'subject': cert.subject.rfc4514_string(),
            'issuer': cert.issuer.rfc4514_string(),
            'serial_number': str(cert.serial_number),
            'not_valid_before': cert.not_valid_before.isoformat(),
            'not_valid_after': cert.not_valid_after.isoformat(),
            'fingerprint': cert.fingerprint(hashes.SHA256()).hex(),
            'public_key_size': cert.public_key().key_size
        }

    def verify_certificate(self, cert_path: str) -> bool:
        """验证证书有效性"""
        try:
            with open(cert_path, "rb") as f:
                cert = x509.load_pem_x509_certificate(f.read(), default_backend())

            # 检查有效期
            now = datetime.utcnow()
            if now < cert.not_valid_before or now > cert.not_valid_after:
                return False

            return True
        except Exception:
            return False


class TLSConfig:
    """TLS配置管理"""

    def __init__(self, cert_path: str = None, key_path: str = None):
        """初始化TLS配置"""
        self.cert_path = cert_path
        self.key_path = key_path
        self._ssl_context = None

    def create_ssl_context(
        self,
        purpose: ssl.Purpose = ssl.Purpose.SERVER_AUTH,
        verify_mode: ssl.VerifyMode = ssl.CERT_REQUIRED,
        check_hostname: bool = True,
        minimum_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2
    ) -> ssl.SSLContext:
        """创建SSL上下文"""

        context = ssl.create_default_context(purpose)
        context.minimum_version = minimum_version
        context.check_hostname = check_hostname
        context.verify_mode = verify_mode

        if self.cert_path and self.key_path:
            context.load_cert_chain(self.cert_path, self.key_path)

        # 设置安全的密码套件
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')

        self._ssl_context = context
        return context

    def create_client_context(self, ca_certs: str = None) -> ssl.SSLContext:
        """创建客户端SSL上下文"""
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

        if ca_certs:
            context.load_verify_locations(ca_certs)
        else:
            # 允许自签名证书用于开发环境
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        return context

    def get_ssl_context(self) -> Optional[ssl.SSLContext]:
        """获取SSL上下文"""
        return self._ssl_context


class MessageSigner:
    """消息签名器"""

    def __init__(self, private_key_path: str = None, public_key_path: str = None):
        """初始化消息签名器"""
        self.rsa_encryption = None

        if private_key_path:
            with open(private_key_path, 'r') as f:
                private_key_pem = f.read()
            self.rsa_encryption = RSAEncryption.load_private_key(private_key_pem)
        elif public_key_path:
            with open(public_key_path, 'r') as f:
                public_key_pem = f.read()
            self.rsa_encryption = RSAEncryption.load_public_key(public_key_pem)

    def sign_message(self, message: Dict[str, Any], include_timestamp: bool = True) -> Dict[str, Any]:
        """签名消息"""
        if not self.rsa_encryption or not self.rsa_encryption.private_key:
            raise ValueError("需要私钥进行签名")

        # 添加时间戳
        if include_timestamp:
            message['timestamp'] = datetime.utcnow().isoformat()

        # 计算消息摘要
        message_json = json.dumps(message, sort_keys=True, separators=(',', ':'))
        message_bytes = message_json.encode('utf-8')

        # 生成签名
        signature = self.rsa_encryption.sign(message_bytes)

        return {
            'message': message,
            'signature': signature,
            'hash_algorithm': 'sha256'
        }

    def verify_message(self, signed_message: Dict[str, Any], max_age_seconds: int = 300) -> bool:
        """验证消息签名"""
        if not self.rsa_encryption:
            raise ValueError("需要公钥进行签名验证")

        try:
            message = signed_message['message']
            signature = signed_message['signature']

            # 检查时间戳
            if 'timestamp' in message:
                timestamp = datetime.fromisoformat(message['timestamp'])
                age = (datetime.utcnow() - timestamp).total_seconds()
                if age > max_age_seconds:
                    return False

            # 验证签名
            message_json = json.dumps(message, sort_keys=True, separators=(',', ':'))
            message_bytes = message_json.encode('utf-8')

            return self.rsa_encryption.verify_signature(message_bytes, signature)

        except Exception:
            return False

    def create_secure_hash(self, data: str, salt: str = None) -> str:
        """创建安全哈希"""
        if salt is None:
            salt = os.urandom(16).hex()

        combined = f"{salt}{data}"
        return HashManager.hash_data(combined.encode('utf-8'), 'sha256')


class SecureChannel:
    """安全通信通道"""

    def __init__(self, tls_config: TLSConfig = None, message_signer: MessageSigner = None):
        """初始化安全通道"""
        self.tls_config = tls_config
        self.message_signer = message_signer
        self.session = None

    async def create_session(self) -> aiohttp.ClientSession:
        """创建HTTP会话"""
        if self.session:
            return self.session

        # 创建SSL上下文
        ssl_context = None
        if self.tls_config:
            ssl_context = self.tls_config.create_client_context()

        # 创建会话
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(connector=connector)
        return self.session

    async def send_secure_request(
        self,
        url: str,
        method: str = 'POST',
        data: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        sign_message: bool = True
    ) -> Dict[str, Any]:
        """发送安全请求"""

        session = await self.create_session()

        # 准备请求头
        request_headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'ChessRobot-SecureClient/1.0'
        }
        if headers:
            request_headers.update(headers)

        # 准备请求数据
        request_data = data or {}

        # 添加请求ID和时间戳
        request_data['request_id'] = os.urandom(16).hex()
        request_data['timestamp'] = datetime.utcnow().isoformat()

        # 签名消息
        if sign_message and self.message_signer:
            signed_data = self.message_signer.sign_message(request_data)
            request_body = json.dumps(signed_data)
        else:
            request_body = json.dumps(request_data)

        try:
            async with session.request(
                method,
                url,
                data=request_body,
                headers=request_headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:

                if response.content_type == 'application/json':
                    response_data = await response.json()
                else:
                    response_data = {'text': await response.text()}

                return {
                    'status': response.status,
                    'headers': dict(response.headers),
                    'data': response_data,
                    'success': 200 <= response.status < 300
                }

        except Exception as e:
            return {
                'status': 0,
                'headers': {},
                'data': {'error': str(e)},
                'success': False
            }

    async def receive_secure_request(self, request_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """接收并验证安全请求"""

        # 检查是否为签名消息
        if 'signature' in request_data:
            if not self.message_signer:
                return False, {'error': '无法验证消息签名'}

            if not self.message_signer.verify_message(request_data):
                return False, {'error': '消息签名验证失败'}

            message = request_data['message']
        else:
            message = request_data

        # 基本验证
        if 'request_id' not in message:
            return False, {'error': '缺少请求ID'}

        if 'timestamp' not in message:
            return False, {'error': '缺少时间戳'}

        # 验证时间戳
        try:
            timestamp = datetime.fromisoformat(message['timestamp'])
            age = (datetime.utcnow() - timestamp).total_seconds()
            if age > 300:  # 5分钟超时
                return False, {'error': '请求已过期'}
        except ValueError:
            return False, {'error': '无效的时间戳格式'}

        return True, message

    async def close(self):
        """关闭连接"""
        if self.session:
            await self.session.close()
            self.session = None


class SecureWebSocketHandler:
    """安全WebSocket处理器"""

    def __init__(self, message_signer: MessageSigner = None):
        """初始化WebSocket处理器"""
        self.message_signer = message_signer
        self.connections: Dict[str, Any] = {}

    async def handle_connection(self, websocket, path: str):
        """处理WebSocket连接"""
        connection_id = os.urandom(16).hex()
        self.connections[connection_id] = {
            'websocket': websocket,
            'path': path,
            'connected_at': datetime.utcnow(),
            'authenticated': False
        }

        try:
            async for message in websocket:
                await self.handle_message(connection_id, message)
        except Exception as e:
            print(f"WebSocket连接错误: {e}")
        finally:
            if connection_id in self.connections:
                del self.connections[connection_id]

    async def handle_message(self, connection_id: str, message: str):
        """处理WebSocket消息"""
        try:
            data = json.loads(message)
            connection = self.connections[connection_id]

            # 验证消息
            if self.message_signer:
                is_valid, validated_data = await self.receive_secure_request(data)
                if not is_valid:
                    await self.send_error(connection_id, validated_data.get('error', '消息验证失败'))
                    return
                data = validated_data

            # 处理消息类型
            message_type = data.get('type')
            if message_type == 'authenticate':
                await self.handle_authentication(connection_id, data)
            elif message_type == 'ping':
                await self.send_message(connection_id, {'type': 'pong', 'timestamp': datetime.utcnow().isoformat()})
            else:
                await self.handle_application_message(connection_id, data)

        except json.JSONDecodeError:
            await self.send_error(connection_id, '无效的JSON格式')
        except Exception as e:
            await self.send_error(connection_id, f'处理消息时出错: {str(e)}')

    async def send_message(self, connection_id: str, data: Dict[str, Any]):
        """发送消息"""
        if connection_id not in self.connections:
            return False

        try:
            # 签名消息
            if self.message_signer:
                signed_data = self.message_signer.sign_message(data)
                message = json.dumps(signed_data)
            else:
                message = json.dumps(data)

            websocket = self.connections[connection_id]['websocket']
            await websocket.send(message)
            return True

        except Exception as e:
            print(f"发送WebSocket消息失败: {e}")
            return False

    async def send_error(self, connection_id: str, error_message: str):
        """发送错误消息"""
        await self.send_message(connection_id, {
            'type': 'error',
            'error': error_message,
            'timestamp': datetime.utcnow().isoformat()
        })

    async def handle_authentication(self, connection_id: str, data: Dict[str, Any]):
        """处理身份验证"""
        # 这里可以集成认证模块
        # 暂时简单验证
        token = data.get('token')
        if token:
            self.connections[connection_id]['authenticated'] = True
            await self.send_message(connection_id, {
                'type': 'auth_success',
                'message': '身份验证成功'
            })
        else:
            await self.send_error(connection_id, '身份验证失败')

    async def handle_application_message(self, connection_id: str, data: Dict[str, Any]):
        """处理应用程序消息"""
        # 检查是否已认证
        if not self.connections[connection_id].get('authenticated', False):
            await self.send_error(connection_id, '需要先进行身份验证')
            return

        # 这里处理具体的应用消息
        await self.send_message(connection_id, {
            'type': 'ack',
            'message': '消息已接收',
            'original_type': data.get('type')
        })

    def get_connection_info(self) -> Dict[str, Any]:
        """获取连接信息"""
        return {
            'total_connections': len(self.connections),
            'authenticated_connections': sum(1 for conn in self.connections.values() if conn.get('authenticated', False)),
            'connections': {
                conn_id: {
                    'path': conn['path'],
                    'connected_at': conn['connected_at'].isoformat(),
                    'authenticated': conn.get('authenticated', False)
                }
                for conn_id, conn in self.connections.items()
            }
        }