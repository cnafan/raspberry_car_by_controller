import pyaudio
import asyncio
import websockets
import time
from typing import Optional

# 导入小车端配置 (假设 config.py 已经定义)
try:
    from car.config import AUDIO_CHUNK_SIZE, AUDIO_FORMAT, AUDIO_CHANNELS, AUDIO_RATE, VAD_ENABLED
except ImportError:
    print("Warning: car.config not found. Using default audio settings.")
    AUDIO_CHUNK_SIZE = 1024       # 每次读取的音频帧大小 (字节)
    AUDIO_FORMAT = pyaudio.paInt16 # 16-bit PCM
    AUDIO_CHANNELS = 1             # 单声道
    AUDIO_RATE = 16000             # 16kHz 采样率
    VAD_ENABLED = False            # 默认不启用 VAD

# 导入 VAD 模块 (如果启用)
if VAD_ENABLED:
    try:
        from car.audio.vad import VADDetector
        print("VAD enabled and imported.")
    except ImportError:
        print("Warning: VAD is enabled in config but car.audio.vad not found. Running without VAD.")
        VAD_ENABLED = False


class MicClient:
    """
    麦克风客户端：负责采集音频数据，并将其以流式方式通过 WebSocket 发送到服务端。
    支持可选的 VAD (语音活动检测) 以减少空闲传输。
    """

    def __init__(self, websocket_url: str):
        self.url = websocket_url
        self.p = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        self.is_recording = False
        self.vad: Optional[VADDetector] = None
        
        if VAD_ENABLED:
            # 初始化 VAD (假设 VADDetector 接收采样率和帧长)
            self.vad = VADDetector(AUDIO_RATE, chunk_duration_ms=(AUDIO_CHUNK_SIZE * 1000) // (AUDIO_RATE * 2))
        
        print(f"MicClient initialized. Target URL: {self.url}, VAD: {VAD_ENABLED}")

    def start_stream(self):
        """打开 PyAudio 流准备录音。"""
        if self.is_recording:
            print("Audio stream is already open.")
            return

        # 找到输入设备 (可能需要根据实际树莓派的音频设备ID进行调整)
        # input_device_index=...
        self.stream = self.p.open(
            format=AUDIO_FORMAT,
            channels=AUDIO_CHANNELS,
            rate=AUDIO_RATE,
            input=True,
            frames_per_buffer=AUDIO_CHUNK_SIZE,
            stream_callback=None # 使用阻塞模式读取
        )
        self.is_recording = True
        print("PyAudio stream opened.")

    def stop_stream(self):
        """关闭 PyAudio 流。"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        self.is_recording = False
        print("PyAudio stream closed.")

    async def stream_audio_to_server(self, ws_conn: websockets.WebSocketClientProtocol):
        """
        核心方法：持续从麦克风读取数据，并推送到 WebSocket 服务器。
        
        :param ws_conn: 已建立的 WebSocket 连接对象。
        """
        if not self.is_recording or not self.stream:
            print("Error: Audio stream not started. Calling start_stream().")
            self.start_stream()

        print("Starting microphone data transmission...")
        
        voice_active = False # VAD 状态
        
        try:
            while self.is_recording:
                # 1. 从麦克风读取 PCM 数据
                # 使用 run_in_executor 将阻塞的 read 操作放到线程池中，避免阻塞 asyncio
                loop = asyncio.get_running_loop()
                # stream.read() 是阻塞操作
                audio_chunk = await loop.run_in_executor(
                    None, self.stream.read, AUDIO_CHUNK_SIZE, False
                )
                
                if not audio_chunk:
                    continue
                
                # 2. VAD 处理逻辑
                if VAD_ENABLED and self.vad:
                    is_speech = self.vad.process_chunk(audio_chunk)
                    
                    if not voice_active and is_speech:
                        voice_active = True
                        print("[VAD] Voice activity detected. Starting stream.")
                        # 如果需要，可以在这里发送一个 'stream_start' 的控制帧
                        
                    elif voice_active and not is_speech:
                        # 持续静音，判断是否结束
                        if self.vad.is_silence_end():
                            voice_active = False
                            print("[VAD] End of speech detected. Pausing stream.")
                            # 发送一个 'stream_end' 的控制帧，让服务端知道这段语音结束了
                            # await ws_conn.send(json.dumps({"is_final": True}))
                            # 忽略后续静音数据
                            continue 
                    
                    if not voice_active:
                        # VAD 禁用时，所有数据都发送
                        continue
                        
                # 3. 发送音频数据 (直接发送二进制 PCM 数据)
                await ws_conn.send(audio_chunk)

        except websockets.exceptions.ConnectionClosedOK:
            print("WebSocket connection closed normally.")
        except Exception as e:
            print(f"An error occurred during audio streaming: {e}")
        finally:
            print("Microphone data transmission finished.")
            self.stop_stream()


if __name__ == '__main__':
    # 示例用法
    
    # 导入客户端配置 (这里需要 client.py 才能启动连接，先跳过)
    # from car.comm.client import COMM_SERVER_URL 
    MOCK_SERVER_URL = "ws://127.0.0.1:8765/audio/in"
    
    async def run_mic_test():
        mic_client = MicClient(MOCK_SERVER_URL)
        mic_client.start_stream() # 先打开麦克风

        print(f"Connecting to {MOCK_SERVER_URL}...")
        try:
            async with websockets.connect(MOCK_SERVER_URL) as ws:
                print("WebSocket connected. Starting audio stream...")
                await mic_client.stream_audio_to_server(ws)
                
        except ConnectionRefusedError:
            print("Connection refused. Make sure the server is running on 127.0.0.1:8765.")
        except Exception as e:
            print(f"Connection error: {e}")

    print("--- Running MicClient Mock Test ---")
    print("Press Ctrl+C to stop the test.")
    try:
        # 注意：此处的 run_mic_test 需要真实的 PyAudio 设备
        # asyncio.run(run_mic_test())
        print("Test skipped. Please run with 'car/main.py' after setting up hardware.")
    except KeyboardInterrupt:
        print("Test stopped by user.")
