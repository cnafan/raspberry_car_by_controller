# app/ws_manager.py
import asyncio
import json
from typing import Set
from fastapi import WebSocket

class ConnectionManager:
    """
    一个 WebSocket 连接管理器，用于管理所有活动连接并进行广播。
    """
    def __init__(self):
        # 使用一个集合来存储所有活动的 WebSocket 连接，保证唯一性
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """
        接受一个新的 WebSocket 连接。
        """
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"New WebSocket connection: {websocket.client}")

    def disconnect(self, websocket: WebSocket):
        """
        移除一个断开的 WebSocket 连接。
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"WebSocket connection closed: {websocket.client}")

    async def broadcast(self, message: str):
        """
        向所有活动的 WebSocket 连接广播一条消息。
        如果发送失败，则移除该连接。
        """
        disconnected_connections = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Could not broadcast message to client {connection.client}: {e}")
                disconnected_connections.add(connection)

        # 移除发送失败的连接
        for connection in disconnected_connections:
            self.active_connections.remove(connection)

    async def run_broadcast_task(self, car_state_instance):
        """
        一个异步任务，以固定频率（20Hz）广播最新的小车状态。
        """
        # 每 50 毫秒（20Hz）广播一次
        broadcast_interval = 0.05
        while True:
            # 获取最新的小车状态
            state = car_state_instance.get_state()
            # 将字典转换为 JSON 字符串
            message = json.dumps(state)
            
            # 广播状态给所有客户端
            await self.broadcast(message)

            # 等待下一个广播周期
            await asyncio.sleep(broadcast_interval)
