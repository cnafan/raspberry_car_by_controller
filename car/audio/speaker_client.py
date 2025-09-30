import pyaudio
import asyncio
import websockets
import time
from typing import Optional

# 导入小车端配置 (假设 config.py 已经定义)
try:
    from car.config import AUDIO_OUT_RATE, AUDIO_OUT_CHANNELS, AUDIO_FORMAT
except ImportError:
    print("Warning: car.config not found. Using default speaker settings.")
    AUDIO_OUT_RATE = 24000         # 服务端 TTS 输出的采样率 (CosyVoice 常用)
    AUDIO_OUT_CHANNELS = 1         # 单声道
    AUDIO_FORMAT = pyaudio.paInt16 # 16-bit PCM


class SpeakerClient:
    """
    扬声器客户端：负责从服务端接收 PCM 音频流，并实时写入本地播放设备。
    """

    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        self.is_playing = False
        self.open_stream() # 在初始化时打开音频流

    def open_stream(self):
        """打开 PyAudio 输出流准备播放。"""
        if self.stream:
            self.close_stream()
            
        # 找到输出设备 (可能需要根据实际树莓派的音频设备ID进行调整)
        # output_device_index=...
        self.stream = self.p.open(
            format=AUDIO_FORMAT,
            channels=AUDIO_OUT_CHANNELS,
            rate=AUDIO_OUT_RATE,
            output=True,
            # frames_per_buffer 可以设置为较小值以降低播放延迟
            frames_per_buffer=1024 
        )
        self.is_playing = True
        print(f"PyAudio speaker stream opened. Rate: {AUDIO_OUT_RATE}Hz")


    def close_stream(self):
        """关闭 PyAudio 输出流。"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        self.is_playing = False
        print("PyAudio speaker stream closed.")
        
    def terminate(self):
        """终止 PyAudio 实例。"""
        self.close_stream()
        self.p.terminate()
        print("PyAudio instance terminated.")


    async def receive_and_play_audio(self, ws_conn: websockets.WebSocketClientProtocol):
        """
        核心方法：持续从 WebSocket 连接接收音频数据，并实时播放。
        
        :param ws_conn: 已建立的 WebSocket 连接对象。
        """
        if not self.is_playing or not self.stream:
            print("Error: Speaker stream not open. Attempting to reopen.")
            self.open_stream()
            
        print("Starting audio playback receiver...")
        
        try:
            # 持续监听 WebSocket 消息
            async for message in ws_conn:
                if isinstance(message, bytes):
                    # 收到 PCM 数据块，立即写入播放流
                    audio_chunk = message
                    
                    # 异步地执行阻塞的 write 操作
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        None, self.stream.write, audio_chunk
                    )
                    
                # 可以根据需要处理 JSON 消息（例如 AudioFrame 的 is_final 标记）
                # elif isinstance(message, str):
                #     pass 

        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed, stopping playback.")
        except Exception as e:
            print(f"An error occurred during audio playback: {e}")
        finally:
            print("Audio playback receiver finished.")
            # 注意：不关闭 stream，等待下一次播放，但可以停止播放流
            self.stream.stop_stream()
            
            # 为了减少内存占用，可以在长时间闲置后关闭流
            # self.close_stream()


if __name__ == '__main__':
    # 示例用法 (通常由 main.py 统一管理连接)
    MOCK_SERVER_URL = "ws://127.0.0.1:8765/audio/out" # 假设的服务端地址
    
    async def run_speaker_test():
        speaker_client = SpeakerClient()
        print(f"Connecting to {MOCK_SERVER_URL}...")
        
        try:
            # 假设连接的是一个能推流的 WebSocket 路径
            async with websockets.connect(MOCK_SERVER_URL) as ws:
                print("WebSocket connected. Waiting for audio stream...")
                # 模拟长时间运行
                await speaker_client.receive_and_play_audio(ws)
                
        except ConnectionRefusedError:
            print("Connection refused. Make sure the server is running.")
        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            speaker_client.terminate()

    print("--- Running SpeakerClient Mock Test ---")
    print("Test skipped. Please run with 'car/main.py' after setting up hardware.")
    # try:
    #     asyncio.run(run_speaker_test())
    # except KeyboardInterrupt:
    #     print("Test stopped by user.")
