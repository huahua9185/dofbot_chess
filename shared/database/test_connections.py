#!/usr/bin/env python3
"""
数据库连接测试脚本
测试MongoDB和Redis连接及基本操作
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timezone

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.database.mongodb_client import MongoDBClient, AsyncMongoDBClient
from shared.database.redis_client import RedisClient, AsyncRedisClient
from shared.models.database_models import GameModel, UserModel, SystemLogModel

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_mongodb_sync():
    """测试MongoDB同步连接"""
    print("\n=== Testing MongoDB Synchronous Connection ===")

    try:
        # 创建客户端
        mongo_client = MongoDBClient(
            host=os.getenv('MONGODB_HOST', 'localhost'),
            port=int(os.getenv('MONGODB_PORT', '27017')),
            database=os.getenv('MONGODB_DATABASE', 'chess_robot')
        )

        # 连接数据库
        if not mongo_client.connect():
            print("❌ Failed to connect to MongoDB")
            return False

        print("✅ Successfully connected to MongoDB")

        # 测试集合创建
        collection = mongo_client.get_collection('test_collection')
        print("✅ Successfully created test collection")

        # 测试插入数据
        test_user_data = {
            'username': 'test_user',
            'email': 'test@example.com',
            'password_hash': 'hashed_password',
            'created_at': datetime.now(timezone.utc)
        }

        user_id = mongo_client.create_user(test_user_data)
        if user_id:
            print(f"✅ Successfully created user with ID: {user_id}")
        else:
            print("❌ Failed to create user")
            return False

        # 测试查询数据
        user = mongo_client.get_user({'username': 'test_user'})
        if user:
            print(f"✅ Successfully retrieved user: {user['username']}")
        else:
            print("❌ Failed to retrieve user")
            return False

        # 测试游戏创建
        test_game_data = {
            'game_id': 'test_game_001',
            'player_id': str(user_id),
            'player_color': 'white',
            'ai_difficulty': 3,
            'status': 'waiting',
            'created_at': datetime.now(timezone.utc)
        }

        game_id = mongo_client.create_game(test_game_data)
        if game_id:
            print(f"✅ Successfully created game with ID: {game_id}")
        else:
            print("❌ Failed to create game")

        # 测试系统日志
        log_data = {
            'service': 'test_service',
            'level': 'INFO',
            'message': 'MongoDB connection test successful',
            'timestamp': datetime.now(timezone.utc)
        }

        log_id = mongo_client.log_system_event(log_data)
        if log_id:
            print(f"✅ Successfully logged system event with ID: {log_id}")
        else:
            print("❌ Failed to log system event")

        # 清理测试数据
        mongo_client.get_collection('users').delete_many({'username': 'test_user'})
        mongo_client.get_collection('games').delete_many({'game_id': 'test_game_001'})
        mongo_client.get_collection('system_logs').delete_many({'service': 'test_service'})
        print("✅ Test data cleaned up")

        # 断开连接
        mongo_client.disconnect()
        print("✅ Successfully disconnected from MongoDB")

        return True

    except Exception as e:
        print(f"❌ MongoDB test failed with error: {e}")
        return False


async def test_mongodb_async():
    """测试MongoDB异步连接"""
    print("\n=== Testing MongoDB Asynchronous Connection ===")

    try:
        # 创建异步客户端
        async_mongo_client = AsyncMongoDBClient(
            host=os.getenv('MONGODB_HOST', 'localhost'),
            port=int(os.getenv('MONGODB_PORT', '27017')),
            database=os.getenv('MONGODB_DATABASE', 'chess_robot')
        )

        # 连接数据库
        if not await async_mongo_client.connect():
            print("❌ Failed to connect to MongoDB (async)")
            return False

        print("✅ Successfully connected to MongoDB (async)")

        # 测试异步创建游戏
        test_game_data = {
            'game_id': 'async_test_game_001',
            'player_id': 'async_test_player',
            'player_color': 'black',
            'ai_difficulty': 5,
            'status': 'waiting',
            'created_at': datetime.now(timezone.utc)
        }

        game_id = await async_mongo_client.create_game_async(test_game_data)
        if game_id:
            print(f"✅ Successfully created game (async) with ID: {game_id}")
        else:
            print("❌ Failed to create game (async)")

        # 清理测试数据
        await async_mongo_client.get_collection('games').delete_many({'game_id': 'async_test_game_001'})
        print("✅ Test data cleaned up (async)")

        # 断开连接
        await async_mongo_client.disconnect()
        print("✅ Successfully disconnected from MongoDB (async)")

        return True

    except Exception as e:
        print(f"❌ MongoDB async test failed with error: {e}")
        return False


def test_redis_sync():
    """测试Redis同步连接"""
    print("\n=== Testing Redis Synchronous Connection ===")

    try:
        # 创建客户端
        redis_client = RedisClient(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', '6379')),
            db=int(os.getenv('REDIS_DB', '0'))
        )

        # 连接Redis
        if not redis_client.connect():
            print("❌ Failed to connect to Redis")
            return False

        print("✅ Successfully connected to Redis")

        # 测试基本键值操作
        test_key = "test:connection:key"
        test_value = {"message": "Hello Redis!", "timestamp": datetime.now().isoformat()}

        if redis_client.set(test_key, test_value, ex=60):
            print("✅ Successfully set test key-value")
        else:
            print("❌ Failed to set test key-value")
            return False

        retrieved_value = redis_client.get(test_key)
        if retrieved_value and retrieved_value["message"] == "Hello Redis!":
            print(f"✅ Successfully retrieved test value: {retrieved_value['message']}")
        else:
            print("❌ Failed to retrieve test value")
            return False

        # 测试游戏状态缓存
        game_state = {
            "game_id": "test_game_redis",
            "status": "playing",
            "current_player": "white",
            "board_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "move_count": 0
        }

        if redis_client.cache_game_state("test_game_redis", game_state, ttl=300):
            print("✅ Successfully cached game state")
        else:
            print("❌ Failed to cache game state")

        cached_state = redis_client.get_cached_game_state("test_game_redis")
        if cached_state and cached_state["status"] == "playing":
            print(f"✅ Successfully retrieved cached game state: {cached_state['status']}")
        else:
            print("❌ Failed to retrieve cached game state")

        # 测试列表操作（移动历史）
        move_data = {
            "move_number": 1,
            "move": "e2e4",
            "player": "white",
            "timestamp": datetime.now().isoformat()
        }

        if redis_client.add_move_to_history("test_game_redis", move_data):
            print("✅ Successfully added move to history")
        else:
            print("❌ Failed to add move to history")

        history = redis_client.get_move_history("test_game_redis")
        if history and len(history) > 0:
            print(f"✅ Successfully retrieved move history: {len(history)} moves")
        else:
            print("❌ Failed to retrieve move history")

        # 测试发布订阅
        channel = "test:channel"
        message = {"type": "test_message", "data": "Hello PubSub!"}

        subscribers = redis_client.publish(channel, message)
        print(f"✅ Successfully published message to {subscribers} subscribers")

        # 清理测试数据
        redis_client.delete(test_key, f"game:state:test_game_redis", f"game:moves:test_game_redis")
        print("✅ Test data cleaned up")

        # 断开连接
        redis_client.disconnect()
        print("✅ Successfully disconnected from Redis")

        return True

    except Exception as e:
        print(f"❌ Redis test failed with error: {e}")
        return False


async def test_redis_async():
    """测试Redis异步连接"""
    print("\n=== Testing Redis Asynchronous Connection ===")

    try:
        # 创建异步客户端
        async_redis_client = AsyncRedisClient(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', '6379')),
            db=int(os.getenv('REDIS_DB', '0'))
        )

        # 连接Redis
        if not await async_redis_client.connect():
            print("❌ Failed to connect to Redis (async)")
            return False

        print("✅ Successfully connected to Redis (async)")

        # 测试异步操作
        test_key = "async:test:key"
        test_value = {"async": True, "message": "Hello Async Redis!"}

        if await async_redis_client.set_async(test_key, test_value, ex=60):
            print("✅ Successfully set test key-value (async)")
        else:
            print("❌ Failed to set test key-value (async)")

        retrieved_value = await async_redis_client.get_async(test_key)
        if retrieved_value and retrieved_value["message"] == "Hello Async Redis!":
            print(f"✅ Successfully retrieved test value (async): {retrieved_value['message']}")
        else:
            print("❌ Failed to retrieve test value (async)")

        # 测试异步发布
        channel = "async:test:channel"
        message = {"type": "async_test", "data": "Hello Async PubSub!"}

        subscribers = await async_redis_client.publish_async(channel, message)
        print(f"✅ Successfully published async message to {subscribers} subscribers")

        # 断开连接
        await async_redis_client.disconnect()
        print("✅ Successfully disconnected from Redis (async)")

        return True

    except Exception as e:
        print(f"❌ Redis async test failed with error: {e}")
        return False


def test_data_models():
    """测试数据模型"""
    print("\n=== Testing Data Models ===")

    try:
        # 测试用户模型
        user_data = {
            "username": "test_model_user",
            "email": "model@test.com",
            "password_hash": "hashed_password_123"
        }

        user_model = UserModel(**user_data)
        print(f"✅ Successfully created UserModel: {user_model.username}")

        # 测试游戏模型
        game_data = {
            "game_id": "model_test_game",
            "player_id": str(user_model.id),
            "player_color": "white",
            "ai_difficulty": 5
        }

        game_model = GameModel(**game_data)
        print(f"✅ Successfully created GameModel: {game_model.game_id}")

        # 测试系统日志模型
        log_data = {
            "service": "model_test",
            "level": "INFO",
            "message": "Data model test successful"
        }

        log_model = SystemLogModel(**log_data)
        print(f"✅ Successfully created SystemLogModel: {log_model.service}")

        # 测试模型序列化
        user_json = user_model.json()
        game_json = game_model.json()
        log_json = log_model.json()

        print("✅ Successfully serialized models to JSON")

        return True

    except Exception as e:
        print(f"❌ Data model test failed with error: {e}")
        return False


async def main():
    """主测试函数"""
    print("🚀 Starting Database Connection Tests")
    print("=" * 50)

    # 设置环境变量（如果未设置）
    os.environ.setdefault('MONGODB_HOST', 'localhost')
    os.environ.setdefault('MONGODB_PORT', '27017')
    os.environ.setdefault('MONGODB_DATABASE', 'chess_robot')
    os.environ.setdefault('REDIS_HOST', 'localhost')
    os.environ.setdefault('REDIS_PORT', '6379')
    os.environ.setdefault('REDIS_DB', '0')

    results = []

    # 测试数据模型
    results.append(("Data Models", test_data_models()))

    # 测试MongoDB同步连接
    results.append(("MongoDB Sync", test_mongodb_sync()))

    # 测试MongoDB异步连接
    results.append(("MongoDB Async", await test_mongodb_async()))

    # 测试Redis同步连接
    results.append(("Redis Sync", test_redis_sync()))

    # 测试Redis异步连接
    results.append(("Redis Async", await test_redis_async()))

    # 汇总结果
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)

    all_passed = True
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:<20} {status}")
        if not result:
            all_passed = False

    print("=" * 50)
    if all_passed:
        print("🎉 All database tests passed successfully!")
        return 0
    else:
        print("⚠️  Some database tests failed. Please check the configuration.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)