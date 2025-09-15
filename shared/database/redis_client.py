"""
Redis客户端连接和操作封装
用于缓存、会话管理和实时消息传递
"""

import os
import json
import logging
from typing import Optional, Dict, List, Any, Union
from datetime import datetime, timezone, timedelta
import redis
import redis.asyncio as aioredis
from redis.exceptions import ConnectionError, TimeoutError, RedisError

logger = logging.getLogger(__name__)

class RedisClient:
    """Redis同步客户端"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        decode_responses: bool = True,
        **kwargs
    ):
        self.host = host
        self.port = port
        self.db = db

        # Redis连接配置
        self.connection_params = {
            'host': host,
            'port': port,
            'db': db,
            'password': password,
            'decode_responses': decode_responses,
            'socket_timeout': 5,
            'socket_connect_timeout': 5,
            'socket_keepalive': True,
            'socket_keepalive_options': {},
            'health_check_interval': 30,
            **kwargs
        }

        self.client: Optional[redis.Redis] = None
        self.pubsub_client: Optional[redis.Redis] = None

    def connect(self) -> bool:
        """建立Redis连接"""
        try:
            self.client = redis.Redis(**self.connection_params)
            # 测试连接
            self.client.ping()

            # 创建发布订阅专用连接
            self.pubsub_client = redis.Redis(**self.connection_params)

            logger.info(f"Successfully connected to Redis at {self.host}:{self.port}")
            return True
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {e}")
            return False

    def disconnect(self):
        """断开Redis连接"""
        if self.client:
            self.client.close()
            self.client = None
        if self.pubsub_client:
            self.pubsub_client.close()
            self.pubsub_client = None
        logger.info("Disconnected from Redis")

    def is_connected(self) -> bool:
        """检查连接状态"""
        try:
            return self.client is not None and self.client.ping()
        except:
            return False

    # 基础键值操作
    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """设置键值"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            return self.client.set(key, value, ex=ex)
        except RedisError as e:
            logger.error(f"Failed to set key {key}: {e}")
            return False

    def get(self, key: str) -> Optional[Any]:
        """获取键值"""
        try:
            value = self.client.get(key)
            if value is None:
                return None

            # 尝试解析JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except RedisError as e:
            logger.error(f"Failed to get key {key}: {e}")
            return None

    def delete(self, *keys: str) -> int:
        """删除键"""
        try:
            return self.client.delete(*keys)
        except RedisError as e:
            logger.error(f"Failed to delete keys {keys}: {e}")
            return 0

    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            return bool(self.client.exists(key))
        except RedisError as e:
            logger.error(f"Failed to check existence of key {key}: {e}")
            return False

    def expire(self, key: str, seconds: int) -> bool:
        """设置键过期时间"""
        try:
            return bool(self.client.expire(key, seconds))
        except RedisError as e:
            logger.error(f"Failed to set expiry for key {key}: {e}")
            return False

    def ttl(self, key: str) -> int:
        """获取键剩余存活时间"""
        try:
            return self.client.ttl(key)
        except RedisError as e:
            logger.error(f"Failed to get TTL for key {key}: {e}")
            return -1

    # 哈希操作
    def hset(self, name: str, key: str, value: Any) -> int:
        """设置哈希字段"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            return self.client.hset(name, key, value)
        except RedisError as e:
            logger.error(f"Failed to hset {name}.{key}: {e}")
            return 0

    def hget(self, name: str, key: str) -> Optional[Any]:
        """获取哈希字段"""
        try:
            value = self.client.hget(name, key)
            if value is None:
                return None

            # 尝试解析JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except RedisError as e:
            logger.error(f"Failed to hget {name}.{key}: {e}")
            return None

    def hgetall(self, name: str) -> Dict[str, Any]:
        """获取哈希所有字段"""
        try:
            result = self.client.hgetall(name)
            # 尝试解析JSON值
            parsed_result = {}
            for k, v in result.items():
                try:
                    parsed_result[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    parsed_result[k] = v
            return parsed_result
        except RedisError as e:
            logger.error(f"Failed to hgetall {name}: {e}")
            return {}

    def hdel(self, name: str, *keys: str) -> int:
        """删除哈希字段"""
        try:
            return self.client.hdel(name, *keys)
        except RedisError as e:
            logger.error(f"Failed to hdel {name}.{keys}: {e}")
            return 0

    # 列表操作
    def lpush(self, name: str, *values: Any) -> int:
        """左侧推入列表"""
        try:
            serialized_values = []
            for value in values:
                if isinstance(value, (dict, list)):
                    serialized_values.append(json.dumps(value, ensure_ascii=False))
                else:
                    serialized_values.append(value)
            return self.client.lpush(name, *serialized_values)
        except RedisError as e:
            logger.error(f"Failed to lpush to {name}: {e}")
            return 0

    def rpush(self, name: str, *values: Any) -> int:
        """右侧推入列表"""
        try:
            serialized_values = []
            for value in values:
                if isinstance(value, (dict, list)):
                    serialized_values.append(json.dumps(value, ensure_ascii=False))
                else:
                    serialized_values.append(value)
            return self.client.rpush(name, *serialized_values)
        except RedisError as e:
            logger.error(f"Failed to rpush to {name}: {e}")
            return 0

    def lpop(self, name: str) -> Optional[Any]:
        """左侧弹出列表元素"""
        try:
            value = self.client.lpop(name)
            if value is None:
                return None

            # 尝试解析JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except RedisError as e:
            logger.error(f"Failed to lpop from {name}: {e}")
            return None

    def lrange(self, name: str, start: int = 0, end: int = -1) -> List[Any]:
        """获取列表范围元素"""
        try:
            values = self.client.lrange(name, start, end)
            result = []
            for value in values:
                try:
                    result.append(json.loads(value))
                except (json.JSONDecodeError, TypeError):
                    result.append(value)
            return result
        except RedisError as e:
            logger.error(f"Failed to lrange {name}: {e}")
            return []

    # 集合操作
    def sadd(self, name: str, *values: Any) -> int:
        """添加到集合"""
        try:
            serialized_values = []
            for value in values:
                if isinstance(value, (dict, list)):
                    serialized_values.append(json.dumps(value, ensure_ascii=False))
                else:
                    serialized_values.append(value)
            return self.client.sadd(name, *serialized_values)
        except RedisError as e:
            logger.error(f"Failed to sadd to {name}: {e}")
            return 0

    def smembers(self, name: str) -> set:
        """获取集合所有成员"""
        try:
            values = self.client.smembers(name)
            result = set()
            for value in values:
                try:
                    result.add(json.loads(value))
                except (json.JSONDecodeError, TypeError):
                    result.add(value)
            return result
        except RedisError as e:
            logger.error(f"Failed to smembers {name}: {e}")
            return set()

    # 有序集合操作
    def zadd(self, name: str, mapping: Dict[Any, float]) -> int:
        """添加到有序集合"""
        try:
            serialized_mapping = {}
            for member, score in mapping.items():
                if isinstance(member, (dict, list)):
                    serialized_mapping[json.dumps(member, ensure_ascii=False)] = score
                else:
                    serialized_mapping[member] = score
            return self.client.zadd(name, serialized_mapping)
        except RedisError as e:
            logger.error(f"Failed to zadd to {name}: {e}")
            return 0

    def zrange(self, name: str, start: int = 0, end: int = -1, withscores: bool = False) -> List:
        """获取有序集合范围元素"""
        try:
            values = self.client.zrange(name, start, end, withscores=withscores)
            if not withscores:
                result = []
                for value in values:
                    try:
                        result.append(json.loads(value))
                    except (json.JSONDecodeError, TypeError):
                        result.append(value)
                return result
            else:
                result = []
                for value, score in values:
                    try:
                        parsed_value = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        parsed_value = value
                    result.append((parsed_value, score))
                return result
        except RedisError as e:
            logger.error(f"Failed to zrange {name}: {e}")
            return []

    # 发布订阅
    def publish(self, channel: str, message: Any) -> int:
        """发布消息"""
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message, ensure_ascii=False)
            return self.client.publish(channel, message)
        except RedisError as e:
            logger.error(f"Failed to publish to channel {channel}: {e}")
            return 0

    def get_pubsub(self):
        """获取发布订阅对象"""
        if not self.pubsub_client:
            raise RuntimeError("Redis not connected")
        return self.pubsub_client.pubsub()

    # 游戏特定的缓存操作
    def cache_game_state(self, game_id: str, game_state: Dict[str, Any], ttl: int = 3600):
        """缓存游戏状态"""
        key = f"game:state:{game_id}"
        return self.set(key, game_state, ex=ttl)

    def get_cached_game_state(self, game_id: str) -> Optional[Dict[str, Any]]:
        """获取缓存的游戏状态"""
        key = f"game:state:{game_id}"
        return self.get(key)

    def cache_player_session(self, player_id: str, session_data: Dict[str, Any], ttl: int = 86400):
        """缓存玩家会话"""
        key = f"player:session:{player_id}"
        return self.set(key, session_data, ex=ttl)

    def get_cached_player_session(self, player_id: str) -> Optional[Dict[str, Any]]:
        """获取缓存的玩家会话"""
        key = f"player:session:{player_id}"
        return self.get(key)

    def add_move_to_history(self, game_id: str, move_data: Dict[str, Any]):
        """添加移动到历史记录"""
        key = f"game:moves:{game_id}"
        return self.rpush(key, move_data)

    def get_move_history(self, game_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取移动历史记录"""
        key = f"game:moves:{game_id}"
        return self.lrange(key, -limit, -1)

    def cache_calibration_data(self, calibration_type: str, data: Dict[str, Any], ttl: int = 86400):
        """缓存标定数据"""
        key = f"calibration:{calibration_type}"
        return self.set(key, data, ex=ttl)

    def get_cached_calibration_data(self, calibration_type: str) -> Optional[Dict[str, Any]]:
        """获取缓存的标定数据"""
        key = f"calibration:{calibration_type}"
        return self.get(key)


class AsyncRedisClient:
    """Redis异步客户端"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        decode_responses: bool = True,
        **kwargs
    ):
        self.host = host
        self.port = port
        self.db = db

        # Redis连接配置
        self.connection_params = {
            'host': host,
            'port': port,
            'db': db,
            'password': password,
            'decode_responses': decode_responses,
            'socket_timeout': 5,
            'socket_connect_timeout': 5,
            'socket_keepalive': True,
            'health_check_interval': 30,
            **kwargs
        }

        self.client: Optional[aioredis.Redis] = None

    async def connect(self) -> bool:
        """建立异步Redis连接"""
        try:
            self.client = aioredis.Redis(**self.connection_params)
            # 测试连接
            await self.client.ping()
            logger.info(f"Successfully connected to Redis (async) at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis (async): {e}")
            return False

    async def disconnect(self):
        """断开异步Redis连接"""
        if self.client:
            await self.client.close()
            self.client = None
        logger.info("Disconnected from Redis (async)")

    async def set_async(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """异步设置键值"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            return await self.client.set(key, value, ex=ex)
        except Exception as e:
            logger.error(f"Failed to set key {key} (async): {e}")
            return False

    async def get_async(self, key: str) -> Optional[Any]:
        """异步获取键值"""
        try:
            value = await self.client.get(key)
            if value is None:
                return None

            # 尝试解析JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Failed to get key {key} (async): {e}")
            return None

    async def publish_async(self, channel: str, message: Any) -> int:
        """异步发布消息"""
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message, ensure_ascii=False)
            return await self.client.publish(channel, message)
        except Exception as e:
            logger.error(f"Failed to publish to channel {channel} (async): {e}")
            return 0


# 全局Redis客户端实例
_redis_client: Optional[RedisClient] = None
_async_redis_client: Optional[AsyncRedisClient] = None


def get_redis_client() -> RedisClient:
    """获取Redis同步客户端单例"""
    global _redis_client
    if _redis_client is None:
        # 从环境变量读取配置
        host = os.getenv('REDIS_HOST', 'localhost')
        port = int(os.getenv('REDIS_PORT', '6379'))
        db = int(os.getenv('REDIS_DB', '0'))
        password = os.getenv('REDIS_PASSWORD')

        _redis_client = RedisClient(
            host=host,
            port=port,
            db=db,
            password=password
        )

        if not _redis_client.connect():
            logger.error("Failed to connect to Redis")
            _redis_client = None
            raise ConnectionError("Could not connect to Redis")

    return _redis_client


def get_async_redis_client() -> AsyncRedisClient:
    """获取Redis异步客户端单例"""
    global _async_redis_client
    if _async_redis_client is None:
        # 从环境变量读取配置
        host = os.getenv('REDIS_HOST', 'localhost')
        port = int(os.getenv('REDIS_PORT', '6379'))
        db = int(os.getenv('REDIS_DB', '0'))
        password = os.getenv('REDIS_PASSWORD')

        _async_redis_client = AsyncRedisClient(
            host=host,
            port=port,
            db=db,
            password=password
        )

    return _async_redis_client