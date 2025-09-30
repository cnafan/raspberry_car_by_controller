import asyncio
import websockets
from websockets.server import WebSocketServerProtocol
from typing import Dict, Any, Optional

# 导入协议和核心逻辑
from server.api.protocol import ControlCmd, AudioFrame, StatusMsg
from server.pipeline.conversation import ConversationPipeline
from server.pipeline.streaming_manager import AudioQueue, PCMQueue

# 假设 AudioFrame 的 PCM 数据是作为单独的二进制消息发送的。
# 我们只通过 JSON 消息来传输控制信息（如 seq, is_final）。
# 实际的 pcm_data 会通过 WebSocket 的 Message.data 二进制部分获取。

class PetCarServer:
    """
    PetCar AI 项目的 WebSocket 服务器。
    负责处理小车端的连接、音频流接收、语音流推送和控制指令下发。
    """
    
    def __init__(self, host: str, port: int, pipeline: ConversationPipeline):
        self.host = host
        self.port = port
        self.pipeline = pipeline
        # 存储当前活动的连接 (小车端连接)
        self.car_connection: Optional[WebSocketServerProtocol] = None 
        # 存储当前的音频输入队列 (如果有活跃会话)
        self.current_audio_queue: Optional[AudioQueue] = None 
        # 存储当前的 PCM 输出队列 (如果有活跃会话)
        self.current_pcm_queue: Optional[PCMQueue] = None 
        print(f"PetCarServer initialized at {host}:{port}")

    async def _handle_connection(self, websocket: WebSocketServerProtocol, path: str):
        """
        处理新的 WebSocket 连接，并根据路径路由数据流。
        """
        if self.car_connection:
            print("Refusing new connection: Car is already connected.")
            await websocket.close(code=1008, reason="Already connected")
            return

        print(f"New connection established on path: {path}")
        self.car_connection = websocket
        
        try:
            if path == "/audio/in":
                await self._audio_in_handler(websocket)
            elif path == "/audio/out":
                # Note: 在实际应用中，通常只有一个连接来处理双向流。
                # 这里的结构是为了匹配文档中的 /audio/in 和 /audio/out 概念。
                await self._audio_out_handler(websocket)
            elif path == "/control":
                await self._control_handler(websocket)
            else:
                await websocket.close(code=1000, reason="Unknown path")
                
        except websockets.exceptions.ConnectionClosed:
            print(f"Connection closed by client on path: {path}")
        finally:
            self.car_connection = None
            # 确保流被清理
            if self.pipeline.is_active():
                self.pipeline.manager.close_all()
            print(f"Connection handler for {path} finished.")


    async def _audio_in_handler(self, websocket: WebSocketServerProtocol):
        """
        处理 /audio/in 路径：接收小车端的麦克风音频流。
        """
        print("Starting audio input handler...")
        
        # 1. 启动新的对话会话和流式队列
        await self.pipeline.start_new_session()
        self.current_audio_queue = self.pipeline.get_audio_input_queue()
        self.current_pcm_queue = self.pipeline.get_pcm_output_queue() # TTS 输出队列也在此处获取
        
        # 2. 启动核心流水线任务（ASR -> LLM -> TTS）
        pipeline_task = asyncio.create_task(self._run_conversation_pipeline(websocket))

        # 3. 实时接收音频数据
        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    # PCM 数据通过二进制消息直接传输
                    if self.current_audio_queue:
                        await self.current_audio_queue.put(message)
                elif isinstance(message, str):
                    # 也可以处理 JSON 控制消息，例如 AudioFrame 的 is_final 标记
                    # 实际操作中，通常是客户端发送一个 control frame
                    pass # 忽略本例中的 JSON 消息
                
        finally:
            print("Audio input stream ended.")
            if self.current_audio_queue:
                self.current_audio_queue.close() # 标记音频输入流结束
            
            # 等待流水线任务完成，获取动作指令
            try:
                success, action_cmd = await pipeline_task
                print(f"Pipeline result: Success={success}, Action={action_cmd}")
                
                if success and action_cmd:
                    await self._send_control_cmd(action_cmd)
                    
            except asyncio.CancelledError:
                print("Pipeline task cancelled.")
            except Exception as e:
                print(f"Error during pipeline execution cleanup: {e}")


    async def _run_conversation_pipeline(self, audio_in_websocket: WebSocketServerProtocol):
        """
        辅助任务：运行核心的 ASR/LLM/TTS 流程，并同步启动 TTS 输出的推送任务。
        """
        # 在 pipeline 运行的同时，启动 TTS PCM 推送任务
        pcm_push_task = asyncio.create_task(self._push_pcm_stream(audio_in_websocket, self.current_pcm_queue))
        
        try:
            # 运行核心逻辑
            success, action_cmd = await self.pipeline.run_pipeline()
            return success, action_cmd
        finally:
            # 无论流水线成功与否，都确保推送任务被取消或完成
            pcm_push_task.cancel()
            await asyncio.gather(pcm_push_task, return_exceptions=True)
            

    async def _push_pcm_stream(self, websocket: WebSocketServerProtocol, pcm_queue: PCMQueue):
        """
        将 TTS 生成的 PCM 音频流推送到小车端。
        """
        print("Starting PCM output stream pusher...")
        seq_counter = 0
        try:
            async for pcm_chunk in pcm_queue:
                # 1. 发送控制信息（JSON 文本）
                # 这里假设控制信息（如 seq）是可选的，直接发送二进制 PCM
                # control_frame = AudioFrame(seq=seq_counter, pcm_data=b'', is_final=False)
                # await websocket.send(control_frame.to_json())
                
                # 2. 发送 PCM 数据（二进制）
                await websocket.send(pcm_chunk)
                seq_counter += 1
                
        except asyncio.CancelledError:
            print("PCM pusher task cancelled.")
            raise # 重新抛出，让 finally 块执行
        except websockets.exceptions.ConnectionClosed:
            print("Client closed connection during PCM push.")
        finally:
            # 发送一个最终帧标记（可选，如果客户端需要明确知道流结束）
            # final_frame = AudioFrame(seq=seq_counter, pcm_data=b'', is_final=True)
            # await websocket.send(final_frame.to_json())
            print("PCM output stream pusher finished.")


    async def _send_control_cmd(self, action_cmd_value: str):
        """
        将 LLM 提取的动作指令发送给小车端。
        """
        if self.car_connection:
            try:
                # 构造动作指令帧
                cmd = ControlCmd(type='action', value=action_cmd_value)
                await self.car_connection.send(cmd.to_json())
                print(f"ControlCmd sent: {cmd.value}")
            except websockets.exceptions.ConnectionClosed:
                print("Cannot send ControlCmd: Connection is closed.")
        else:
            print("ControlCmd failed: Car connection not found.")


    async def _audio_out_handler(self, websocket: WebSocketServerProtocol):
        """
        处理 /audio/out 路径：如果客户端使用分离的连接接收 TTS 音频，则在此处实现。
        但为了简化和小车端通信，我们假设 /audio/in 连接同时用于接收 PCM 输出 (双向流)。
        """
        # 这里的实现是等待直到主 /audio/in 连接结束
        await websocket.wait_closed()
        
    async def _control_handler(self, websocket: WebSocketServerProtocol):
        """
        处理 /control 路径：用于接收小车端的心跳或状态报告。
        """
        async for message in websocket:
            # 接收并打印小车的控制信息
            if isinstance(message, str):
                print(f"[CAR CONTROL] Received: {message}")
                # 假设这里是小车的心跳或状态报告
                
        await websocket.wait_closed()


    def start(self):
        """
        启动 WebSocket 服务器。
        """
        # 使用 websockets.serve 启动服务器
        start_server = websockets.serve(
            self._handle_connection, 
            self.host, 
            self.port
        )
        print(f"WebSocket Server starting at ws://{self.host}:{self.port}")
        
        # 启动 asyncio 事件循环
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()


if __name__ == '__main__':
    # 示例用法 (需要先启动 LLM/ASR/TTS 引擎)
    print("--- Mock Server Startup ---")
    
    # 假设模型的 mock 实例已经创建
    class MockASR:
        def __init__(self, *args, **kwargs): self.wakeup_word="小车小车"
        def start_stream(self): pass
        def transcribe_stream(self, chunk: bytes) -> Optional[str]: 
            return "小车小车，前进。" if len(chunk) > 4096 * 5 else None
        def end_stream(self) -> Optional[str]: return "最终识别结果"
        def detect_wakeup_word(self, text: str) -> bool: return self.wakeup_word in text
    class MockLLM:
        def __init__(self, *args, **kwargs): self.history = []
        def chat_stream(self, text: str) -> Generator[str, None, None]: 
            import time
            response = "好的，我这就向前走五步。[ACTION:forward(5)]"
            for char in response:
                time.sleep(0.01)
                yield char
        def clear_history(self): pass
    class MockTTS:
        def __init__(self, *args, **kwargs): pass
        def synthesize_stream(self, text: str) -> Generator[bytes, None, None]:
            import time
            for _ in range(5):
                time.sleep(0.02)
                yield b'\x00' * 4096
            
    from server.pipeline.conversation import ConversationPipeline as MockPipeline
    mock_pipeline = MockPipeline(MockASR(), MockLLM(), MockTTS())

    # 启动服务器 (注意：在真实环境中，这是阻塞的)
    # server = PetCarServer("127.0.0.1", 8765, mock_pipeline)
    # server.start() 

    # 为了不阻塞笔记本，这里只打印提示
    print("To run, uncomment the server.start() call and ensure all dependencies are mocked or installed.")
    print("Server implementation complete.")
