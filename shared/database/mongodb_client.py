"""
MongoDB客户端连接和操作封装
针对象棋机器人系统的数据存储需求
"""

import os
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import PyMongoError, ConnectionFailure
import asyncio
import motor.motor_asyncio

logger = logging.getLogger(__name__)

class MongoDBClient:
    """MongoDB同步客户端"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 27017,
        database: str = "chess_robot",
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs
    ):
        self.host = host
        self.port = port
        self.database_name = database

        # 构建连接URI
        if username and password:
            uri = f"mongodb://{username}:{password}@{host}:{port}/{database}"
        else:
            uri = f"mongodb://{host}:{port}/{database}"

        # MongoDB客户端配置
        client_options = {
            'serverSelectionTimeoutMS': 5000,
            'connectTimeoutMS': 5000,
            'socketTimeoutMS': 5000,
            'maxPoolSize': 50,
            'minPoolSize': 10,
            'maxIdleTimeMS': 30000,
            'heartbeatFrequencyMS': 10000,
            **kwargs
        }

        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        self.uri = uri
        self.client_options = client_options

    def connect(self) -> bool:
        """建立数据库连接"""
        try:
            self.client = MongoClient(self.uri, **self.client_options)
            # 测试连接
            self.client.admin.command('ping')
            self.db = self.client[self.database_name]
            logger.info(f"Successfully connected to MongoDB at {self.host}:{self.port}")
            return True
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            return False

    def disconnect(self):
        """断开数据库连接"""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            logger.info("Disconnected from MongoDB")

    def get_collection(self, collection_name: str) -> Collection:
        """获取集合对象"""
        if not self.db:
            raise RuntimeError("Database not connected")
        return self.db[collection_name]

    # 用户操作
    def create_user(self, user_data: Dict[str, Any]) -> Optional[str]:
        """创建用户"""
        try:
            user_data['created_at'] = datetime.now(timezone.utc)
            user_data['updated_at'] = datetime.now(timezone.utc)
            result = self.get_collection('users').insert_one(user_data)
            return str(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Failed to create user: {e}")
            return None

    def get_user(self, user_filter: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取用户信息"""
        try:
            return self.get_collection('users').find_one(user_filter)
        except PyMongoError as e:
            logger.error(f"Failed to get user: {e}")
            return None

    def update_user(self, user_filter: Dict[str, Any], update_data: Dict[str, Any]) -> bool:
        """更新用户信息"""
        try:
            update_data['updated_at'] = datetime.now(timezone.utc)
            result = self.get_collection('users').update_one(
                user_filter,
                {'$set': update_data}
            )
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"Failed to update user: {e}")
            return False

    # 游戏操作
    def create_game(self, game_data: Dict[str, Any]) -> Optional[str]:
        """创建游戏记录"""
        try:
            game_data['created_at'] = datetime.now(timezone.utc)
            game_data['updated_at'] = datetime.now(timezone.utc)
            result = self.get_collection('games').insert_one(game_data)
            return str(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Failed to create game: {e}")
            return None

    def get_game(self, game_filter: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取游戏信息"""
        try:
            return self.get_collection('games').find_one(game_filter)
        except PyMongoError as e:
            logger.error(f"Failed to get game: {e}")
            return None

    def update_game(self, game_filter: Dict[str, Any], update_data: Dict[str, Any]) -> bool:
        """更新游戏信息"""
        try:
            update_data['updated_at'] = datetime.now(timezone.utc)
            result = self.get_collection('games').update_one(
                game_filter,
                {'$set': update_data}
            )
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"Failed to update game: {e}")
            return False

    def get_user_games(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取用户游戏历史"""
        try:
            return list(
                self.get_collection('games')
                .find({'player_id': user_id})
                .sort('created_at', DESCENDING)
                .limit(limit)
            )
        except PyMongoError as e:
            logger.error(f"Failed to get user games: {e}")
            return []

    # 移动记录操作
    def add_move(self, move_data: Dict[str, Any]) -> Optional[str]:
        """添加移动记录"""
        try:
            move_data['created_at'] = datetime.now(timezone.utc)
            result = self.get_collection('moves').insert_one(move_data)
            return str(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Failed to add move: {e}")
            return None

    def get_game_moves(self, game_id: str) -> List[Dict[str, Any]]:
        """获取游戏的所有移动"""
        try:
            return list(
                self.get_collection('moves')
                .find({'game_id': game_id})
                .sort('move_number', ASCENDING)
            )
        except PyMongoError as e:
            logger.error(f"Failed to get game moves: {e}")
            return []

    # 标定数据操作
    def save_calibration_data(self, calibration_data: Dict[str, Any]) -> Optional[str]:
        """保存标定数据"""
        try:
            calibration_data['created_at'] = datetime.now(timezone.utc)
            calibration_data['updated_at'] = datetime.now(timezone.utc)
            result = self.get_collection('calibration_data').insert_one(calibration_data)
            return str(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Failed to save calibration data: {e}")
            return None

    def get_active_calibration(self, calibration_type: str) -> Optional[Dict[str, Any]]:
        """获取活跃的标定数据"""
        try:
            return self.get_collection('calibration_data').find_one({
                'calibration_type': calibration_type,
                'is_active': True
            })
        except PyMongoError as e:
            logger.error(f"Failed to get active calibration: {e}")
            return None

    # 日志操作
    def log_system_event(self, log_data: Dict[str, Any]) -> Optional[str]:
        """记录系统事件"""
        try:
            log_data['timestamp'] = datetime.now(timezone.utc)
            result = self.get_collection('system_logs').insert_one(log_data)
            return str(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Failed to log system event: {e}")
            return None

    def get_recent_logs(self, service: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的日志"""
        try:
            query = {}
            if service:
                query['service'] = service

            return list(
                self.get_collection('system_logs')
                .find(query)
                .sort('timestamp', DESCENDING)
                .limit(limit)
            )
        except PyMongoError as e:
            logger.error(f"Failed to get recent logs: {e}")
            return []


class AsyncMongoDBClient:
    """MongoDB异步客户端"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 27017,
        database: str = "chess_robot",
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs
    ):
        self.host = host
        self.port = port
        self.database_name = database

        # 构建连接URI
        if username and password:
            uri = f"mongodb://{username}:{password}@{host}:{port}/{database}"
        else:
            uri = f"mongodb://{host}:{port}/{database}"

        # MongoDB客户端配置
        client_options = {
            'serverSelectionTimeoutMS': 5000,
            'connectTimeoutMS': 5000,
            'socketTimeoutMS': 5000,
            'maxPoolSize': 50,
            'minPoolSize': 10,
            'maxIdleTimeMS': 30000,
            'heartbeatFrequencyMS': 10000,
            **kwargs
        }

        self.client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
        self.db: Optional[motor.motor_asyncio.AsyncIOMotorDatabase] = None
        self.uri = uri
        self.client_options = client_options

    async def connect(self) -> bool:
        """建立异步数据库连接"""
        try:
            self.client = motor.motor_asyncio.AsyncIOMotorClient(
                self.uri, **self.client_options
            )
            # 测试连接
            await self.client.admin.command('ping')
            self.db = self.client[self.database_name]
            logger.info(f"Successfully connected to MongoDB (async) at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB (async): {e}")
            return False

    async def disconnect(self):
        """断开异步数据库连接"""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            logger.info("Disconnected from MongoDB (async)")

    def get_collection(self, collection_name: str):
        """获取异步集合对象"""
        if not self.db:
            raise RuntimeError("Database not connected")
        return self.db[collection_name]

    async def create_game_async(self, game_data: Dict[str, Any]) -> Optional[str]:
        """异步创建游戏记录"""
        try:
            game_data['created_at'] = datetime.now(timezone.utc)
            game_data['updated_at'] = datetime.now(timezone.utc)
            result = await self.get_collection('games').insert_one(game_data)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Failed to create game (async): {e}")
            return None


# 全局数据库客户端实例
_mongodb_client: Optional[MongoDBClient] = None
_async_mongodb_client: Optional[AsyncMongoDBClient] = None


def get_mongodb_client() -> MongoDBClient:
    """获取MongoDB同步客户端单例"""
    global _mongodb_client
    if _mongodb_client is None:
        # 从环境变量读取配置
        host = os.getenv('MONGODB_HOST', 'localhost')
        port = int(os.getenv('MONGODB_PORT', '27017'))
        database = os.getenv('MONGODB_DATABASE', 'chess_robot')
        username = os.getenv('MONGODB_USERNAME')
        password = os.getenv('MONGODB_PASSWORD')

        _mongodb_client = MongoDBClient(
            host=host,
            port=port,
            database=database,
            username=username,
            password=password
        )

        if not _mongodb_client.connect():
            logger.error("Failed to connect to MongoDB")
            _mongodb_client = None
            raise ConnectionError("Could not connect to MongoDB")

    return _mongodb_client


def get_async_mongodb_client() -> AsyncMongoDBClient:
    """获取MongoDB异步客户端单例"""
    global _async_mongodb_client
    if _async_mongodb_client is None:
        # 从环境变量读取配置
        host = os.getenv('MONGODB_HOST', 'localhost')
        port = int(os.getenv('MONGODB_PORT', '27017'))
        database = os.getenv('MONGODB_DATABASE', 'chess_robot')
        username = os.getenv('MONGODB_USERNAME')
        password = os.getenv('MONGODB_PASSWORD')

        _async_mongodb_client = AsyncMongoDBClient(
            host=host,
            port=port,
            database=database,
            username=username,
            password=password
        )

    return _async_mongodb_client