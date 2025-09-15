"""
WebSocket连接管理器
"""
import json
import asyncio
from typing import Dict, List, Set, Any
from fastapi import WebSocket
from dataclasses import asdict

from shared.utils.logger import get_logger

logger = get_logger(__name__)


class WebSocketManager:
    """WebSocket连接管理器"""

    def __init__(self):
        # 游戏房间连接
        self.game_connections: Dict[str, List[WebSocket]] = {}

        # 系统监控连接
        self.system_connections: Set[WebSocket] = set()

        # 所有活跃连接
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, game_id: str):
        """连接到游戏房间"""
        try:
            if game_id not in self.game_connections:
                self.game_connections[game_id] = []

            self.game_connections[game_id].append(websocket)
            self.active_connections.add(websocket)

            logger.info(f"WebSocket连接到游戏 {game_id}, 当前连接数: {len(self.game_connections[game_id])}")

            # 发送欢迎消息
            await self.send_to_client(websocket, {
                "type": "connection_established",
                "game_id": game_id,
                "message": "连接成功"
            })

        except Exception as e:
            logger.error(f"WebSocket连接失败: {str(e)}")

    async def disconnect(self, websocket: WebSocket, game_id: str):
        """断开游戏房间连接"""
        try:
            if game_id in self.game_connections:
                if websocket in self.game_connections[game_id]:
                    self.game_connections[game_id].remove(websocket)

                # 如果房间没有连接了，清理房间
                if not self.game_connections[game_id]:
                    del self.game_connections[game_id]

            self.active_connections.discard(websocket)

            logger.info(f"WebSocket断开游戏 {game_id} 连接")

        except Exception as e:
            logger.error(f"WebSocket断开失败: {str(e)}")

    async def connect_system(self, websocket: WebSocket):
        """连接系统监控"""
        try:
            self.system_connections.add(websocket)
            self.active_connections.add(websocket)

            logger.info(f"系统监控WebSocket连接, 当前连接数: {len(self.system_connections)}")

            await self.send_to_client(websocket, {
                "type": "system_connection_established",
                "message": "系统监控连接成功"
            })

        except Exception as e:
            logger.error(f"系统监控连接失败: {str(e)}")

    async def disconnect_system(self, websocket: WebSocket):
        """断开系统监控连接"""
        try:
            self.system_connections.discard(websocket)
            self.active_connections.discard(websocket)

            logger.info("系统监控WebSocket断开连接")

        except Exception as e:
            logger.error(f"系统监控断开失败: {str(e)}")

    async def send_to_game(self, game_id: str, message: Dict[str, Any]):
        """发送消息到游戏房间的所有客户端"""
        if game_id not in self.game_connections:
            return

        disconnected = []
        message_str = json.dumps(message)

        for websocket in self.game_connections[game_id]:
            try:
                await websocket.send_text(message_str)
            except Exception as e:
                logger.error(f"发送消息到游戏房间失败: {str(e)}")
                disconnected.append(websocket)

        # 清理断开的连接
        for ws in disconnected:
            await self.disconnect(ws, game_id)

    async def send_to_system_monitors(self, message: Dict[str, Any]):
        """发送消息到所有系统监控客户端"""
        if not self.system_connections:
            return

        disconnected = []
        message_str = json.dumps(message)

        for websocket in self.system_connections:
            try:
                await websocket.send_text(message_str)
            except Exception as e:
                logger.error(f"发送系统监控消息失败: {str(e)}")
                disconnected.append(websocket)

        # 清理断开的连接
        for ws in disconnected:
            await self.disconnect_system(ws)

    async def send_to_client(self, websocket: WebSocket, message: Dict[str, Any]):
        """发送消息到特定客户端"""
        try:
            message_str = json.dumps(message)
            await websocket.send_text(message_str)
        except Exception as e:
            logger.error(f"发送消息到客户端失败: {str(e)}")

    async def broadcast(self, message: Dict[str, Any]):
        """广播消息到所有连接的客户端"""
        if not self.active_connections:
            return

        disconnected = []
        message_str = json.dumps(message)

        for websocket in self.active_connections:
            try:
                await websocket.send_text(message_str)
            except Exception as e:
                logger.error(f"广播消息失败: {str(e)}")
                disconnected.append(websocket)

        # 清理断开的连接
        for ws in disconnected:
            self.active_connections.discard(ws)

    async def handle_client_message(self, game_id: str, message: Dict[str, Any]):
        """处理客户端消息"""
        try:
            message_type = message.get("type")

            if message_type == "ping":
                # 心跳检查
                await self.send_to_game(game_id, {
                    "type": "pong",
                    "timestamp": asyncio.get_event_loop().time()
                })

            elif message_type == "move":
                # 移动消息
                await self._handle_move_message(game_id, message)

            elif message_type == "chat":
                # 聊天消息
                await self._handle_chat_message(game_id, message)

            elif message_type == "request_status":
                # 状态请求
                await self._handle_status_request(game_id, message)

            else:
                logger.warning(f"未知消息类型: {message_type}")

        except Exception as e:
            logger.error(f"处理客户端消息失败: {str(e)}")

    async def _handle_move_message(self, game_id: str, message: Dict[str, Any]):
        """处理移动消息"""
        try:
            move_data = message.get("data", {})

            # 广播移动到房间内其他客户端
            await self.send_to_game(game_id, {
                "type": "move_broadcast",
                "data": move_data,
                "timestamp": asyncio.get_event_loop().time()
            })

            logger.info(f"处理移动消息: {game_id}, {move_data}")

        except Exception as e:
            logger.error(f"处理移动消息失败: {str(e)}")

    async def _handle_chat_message(self, game_id: str, message: Dict[str, Any]):
        """处理聊天消息"""
        try:
            chat_data = message.get("data", {})

            # 广播聊天消息到房间
            await self.send_to_game(game_id, {
                "type": "chat_message",
                "data": {
                    "user": chat_data.get("user", "匿名"),
                    "message": chat_data.get("message", ""),
                    "timestamp": asyncio.get_event_loop().time()
                }
            })

        except Exception as e:
            logger.error(f"处理聊天消息失败: {str(e)}")

    async def _handle_status_request(self, game_id: str, message: Dict[str, Any]):
        """处理状态请求"""
        try:
            # 返回游戏状态
            await self.send_to_game(game_id, {
                "type": "game_status",
                "data": {
                    "game_id": game_id,
                    "connections": len(self.game_connections.get(game_id, [])),
                    "timestamp": asyncio.get_event_loop().time()
                }
            })

        except Exception as e:
            logger.error(f"处理状态请求失败: {str(e)}")

    def get_connection_stats(self) -> Dict[str, Any]:
        """获取连接统计"""
        return {
            "total_connections": len(self.active_connections),
            "game_rooms": len(self.game_connections),
            "system_monitors": len(self.system_connections),
            "game_connections_detail": {
                game_id: len(connections)
                for game_id, connections in self.game_connections.items()
            }
        }

    async def cleanup_dead_connections(self):
        """清理死连接"""
        try:
            dead_connections = []

            # 检查所有连接
            for websocket in self.active_connections:
                try:
                    # 发送ping测试连接
                    await websocket.ping()
                except Exception:
                    dead_connections.append(websocket)

            # 清理死连接
            for ws in dead_connections:
                self.active_connections.discard(ws)
                self.system_connections.discard(ws)

                # 从游戏房间中移除
                for game_id, connections in list(self.game_connections.items()):
                    if ws in connections:
                        connections.remove(ws)
                        if not connections:
                            del self.game_connections[game_id]

            if dead_connections:
                logger.info(f"清理死连接数: {len(dead_connections)}")

        except Exception as e:
            logger.error(f"清理死连接失败: {str(e)}")

    async def start_heartbeat(self):
        """启动心跳检查"""
        while True:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次
                await self.cleanup_dead_connections()

                # 发送心跳到系统监控客户端
                await self.send_to_system_monitors({
                    "type": "heartbeat",
                    "timestamp": asyncio.get_event_loop().time(),
                    "connection_stats": self.get_connection_stats()
                })

            except Exception as e:
                logger.error(f"心跳检查错误: {str(e)}")

    def has_game_connections(self, game_id: str) -> bool:
        """检查游戏是否有活跃连接"""
        return game_id in self.game_connections and len(self.game_connections[game_id]) > 0