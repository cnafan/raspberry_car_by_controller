import asyncio
import websockets
import json
from typing import Optional, Callable, Dict, Any, Awaitable

# 导入配置和协议
try:
    from car.config import SERVER_URL, AUDIO_IN_PATH, AUDIO_OUT_PATH, CONTROL_PATH
    from server.api.protocol import ControlCmd, StatusMsg, parse_frame
except ImportError:
    print("Warning: Failed to import config or protocol. Using mock values.")
    SERVER_URL = "ws://127.0.0.1:8765"
    AUDIO_IN_PATH = "/audio/in"
    CONTROL_PATH = "/control"
    class ControlCmd:
        def __init__(self, type, value): self.type = type; self.value = value
        def to_json(self): return json.dumps(self.__dict__)


# 定义一个异步回调函数类型，用于处理接收到的控制命令
ControlHandler = Callable[[ControlCmd], Awaitable[None]]

class WebSocketClient:
    """
    PetCar 小车端 WebSocket 客户端。
    负责与服务端建立持久连接，并管理音频流的上传/下载以及控制命令的接收。
    """
    
    def __init__(self, url: str, path: str, control_handler: Optional[ControlHandler] = None):
        self.url = url.rstrip('/') + path
        self.path = path
        self.conn: Optional[websockets.WebSocketClientProtocol] = None
        self._control_handler = control_handler
        self.is_connected = False
        print(f"WebSocket Client initialized for: {self.url}")
        
    async def connect(self):
        """尝试连接到服务端。"""
        print(f"Attempting to connect to {self.url}...")
        try:
            self.conn = await websockets.connect(self.url)
            self.is_connected = True
            print(f"Successfully connected to {self.path}.")
            return self.conn
        except ConnectionRefusedError:
            print(f"Connection refused by server at {self.url}.")
            self.conn = None
            return None
        except Exception as e:
            print(f"Connection error to {self.url}: {e}")
            self.conn = None
            return None

    async def disconnect(self):
        """断开连接。"""
        if self.conn:
            await self.conn.close()
            self.conn = None
            self.is_connected = False
            print(f"Disconnected from {self.url}.")

    def get_connection(self) -> Optional[websockets.WebSocketClientProtocol]:
        """获取当前连接对象，供 MicClient/SpeakerClient 使用。"""
        return self.conn

    async def send_audio_chunk(self, chunk: bytes):
        """发送音频数据块（通常由 MicClient 调用）。"""
        if self.conn and self.is_connected:
            try:
                await self.conn.send(chunk)
            except websockets.exceptions.ConnectionClosed:
                print("Cannot send audio: Connection closed.")
                self.is_connected = False
            except Exception as e:
                print(f"Error sending audio chunk: {e}")

    async def send_json(self, data: Dict[str, Any]):
        """发送 JSON 控制信息（可选，例如心跳或结束标记）。"""
        if self.conn and self.is_connected:
            try:
                await self.conn.send(json.dumps(data))
            except websockets.exceptions.ConnectionClosed:
                print("Cannot send JSON: Connection closed.")
                self.is_connected = False
            except Exception as e:
                print(f"Error sending JSON: {e}")

    async def listen_for_control_commands(self):
        """
        持续监听连接上的文本消息，解析为 ControlCmd 并调用处理函数。
        此方法通常在一个独立的 asyncio Task 中运行，尤其是在处理 /audio/in 的双向流时。
        """
        if not self.conn:
            print(f"Cannot listen: Not connected to {self.path}.")
            return

        print(f"Starting listener for control/status messages on {self.path}...")
        try:
            async for message in self.conn:
                if isinstance(message, str):
                    # 尝试解析为协议帧
                    frame = parse_frame(message)
                    
                    if isinstance(frame, ControlCmd) and self._control_handler:
                        # 发现动作指令，调用回调函数
                        await self._control_handler(frame)
                    elif isinstance(frame, StatusMsg):
                        print(f"[Status] Code {frame.code}: {frame.message}")
                    else:
                        print(f"[Unknown Frame] Received text: {message[:50]}...")
                        
                elif isinstance(message, bytes):
                    # 收到二进制数据，通常是 TTS 音频，不在此处处理
                    # 应该由 SpeakerClient 的 receive_and_play_audio 方法处理
                    pass

        except websockets.exceptions.ConnectionClosed:
            print(f"Listener detected connection closed on {self.path}.")
            self.is_connected = False
        except Exception as e:
            print(f"Error in listener on {self.path}: {e}")
        finally:
            print(f"Listener on {self.path} stopped.")


class CommManager:
    """
    管理所有 WebSocket 连接和客户端组件。
    在 PetCar 项目中，我们使用一个双向连接来处理所有流。
    """
    def __init__(self, control_handler: ControlHandler):
        # 创建一个双向客户端，用于 ASR 输入、TTS 输出和控制指令
        self.audio_control_client = WebSocketClient(
            url=SERVER_URL, 
            path=AUDIO_IN_PATH, # 路径为 /audio/in，但用于双向通信
            control_handler=control_handler
        )
        self.control_handler = control_handler
        self.listener_task: Optional[asyncio.Task] = None
        
    async def establish_connection(self) -> Optional[websockets.WebSocketClientProtocol]:
        """建立连接并启动监听任务。"""
        conn = await self.audio_control_client.connect()
        if conn:
            # 启动一个独立的 Task 来监听控制指令和状态消息
            self.listener_task = asyncio.create_task(
                self.audio_control_client.listen_for_control_commands()
            )
        return conn
        
    async def close_connection(self):
        """关闭连接和监听任务。"""
        if self.listener_task:
            self.listener_task.cancel()
            await asyncio.gather(self.listener_task, return_exceptions=True)
            self.listener_task = None
        await self.audio_control_client.disconnect()


if __name__ == '__main__':
    # 示例用法
    async def mock_control_handler(cmd: ControlCmd):
        """模拟小车动作执行逻辑。"""
        print(f"\n[CAR ACTION] Executing command: {cmd.type}({cmd.value})")
        await asyncio.sleep(0.1) # 模拟执行延迟
        
    async def run_comm_test():
        manager = CommManager(mock_control_handler)
        
        # 1. 建立连接
        conn = await manager.establish_connection()
        if not conn:
            return

        print("\n--- Sending mock data ---")
        # 2. 模拟 MicClient 上传音频数据
        await manager.audio_control_client.send_audio_chunk(b'\x00' * 4096)
        
        # 3. 模拟发送心跳/状态
        await manager.audio_control_client.send_json({"type": "heartbeat", "timestamp": time.time()})
        
        # 4. 保持连接并等待服务端指令 (Listener Task 已经在后台运行)
        print("\nWaiting 3 seconds for server commands (Requires mock server to run)...")
        await asyncio.sleep(3) 

        # 5. 关闭连接
        await manager.close_connection()

    import time
    print("--- Running CommManager Mock Test ---")
    # asyncio.run(run_comm_test())
    print("Test skipped. Please run with 'car/main.py' after setting up hardware and server.")
