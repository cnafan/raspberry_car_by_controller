import collections
import numpy as np
import time
from typing import Optional, List, Deque

# 假设使用 WebRTC VAD 的 Python 封装
try:
    # pip install webrtcvad
    import webrtcvad 
except ImportError:
    print("Warning: webrtcvad library not found. VADDetector will use mock implementation.")
    class MockWebRTCVAD:
        def __init__(self, mode):
            self.mode = mode
            self.counter = 0
        def is_speech(self, audio_chunk, sample_rate):
            # 模拟 VAD 结果：前 10 块为语音，中间 10 块为静音，后 10 块为语音
            self.counter += 1
            if self.counter < 10 or (self.counter > 20 and self.counter < 30):
                return True
            return False

# VAD 配置常量
# WebRTC VAD 仅支持 8000, 16000, 32000, 48000 Hz 采样率
SUPPORTED_VAD_RATES = [8000, 16000, 32000, 48000] 
VAD_MODE = 3 # 0: 最不激进, 3: 最激进/准确
SILENCE_TIMEOUT_MS = 1500 # 语音结束后，等待 1.5 秒静音后判断传输结束
SILENCE_CHUNK_COUNT = 50 # 粗略估计：16k/20ms -> 50 chunks/sec, 1.5s -> 75 chunks (这里取保守值)


class VADDetector:
    """
    基于 WebRTC VAD 的语音活动检测器。
    用于在客户端过滤静音，只上传包含语音的部分。
    """

    def __init__(self, sample_rate: int, chunk_duration_ms: int = 20, aggressiveness: int = VAD_MODE):
        """
        初始化 VAD 检测器。
        
        :param sample_rate: 音频采样率 (必须是 WebRTC VAD 支持的值)。
        :param chunk_duration_ms: 每个音频块的持续时间 (WebRTC VAD 建议 10, 20, 30 ms)。
        :param aggressiveness: VAD 积极性模式 (0-3)。
        """
        if sample_rate not in SUPPORTED_VAD_RATES:
            raise ValueError(f"Sample rate {sample_rate} not supported by WebRTC VAD. Must be one of {SUPPORTED_VAD_RATES}")

        self.sample_rate = sample_rate
        self.chunk_duration_ms = chunk_duration_ms
        self.chunk_size = int((sample_rate * chunk_duration_ms * 2) / 1000) # 16bit = 2 bytes

        try:
            self._vad = webrtcvad.Vad(aggressiveness)
            self.is_mock = False
        except NameError:
            self._vad = MockWebRTCVAD(aggressiveness)
            self.is_mock = True

        # 用于判断语音结束的静音帧计数器
        self.silence_chunks_count = 0
        self.active_speech_detected = False

        # 缓冲队列：用于存储语音开始前的少量静音帧 (leading silence)
        self.frame_buffer: Deque[bytes] = collections.deque(maxlen=SILENCE_CHUNK_COUNT // 2) 

        print(f"VADDetector initialized. Rate: {sample_rate}Hz, Chunk: {chunk_duration_ms}ms, Mode: {aggressiveness}")


    def process_chunk(self, audio_chunk: bytes) -> bool:
        """
        处理单个音频数据块，返回当前块是否是语音。
        
        :param audio_chunk: 16-bit PCM 音频数据块。
        :return: True 如果检测到语音，False 否则。
        """
        if len(audio_chunk) != self.chunk_size:
            print(f"Warning: Audio chunk size mismatch. Expected {self.chunk_size}, Got {len(audio_chunk)}")
            # 尝试截断或填充，但 WebRTC VAD 对大小要求严格
            # 这里简单返回 False
            return False 

        # 1. 检测当前帧是否是语音
        is_speech = self._vad.is_speech(audio_chunk, self.sample_rate)

        if is_speech:
            self.active_speech_detected = True
            self.silence_chunks_count = 0
            # 当检测到语音时，将缓冲区中的帧发送出去
            # Note: 实际传输逻辑在 MicClient 中实现，这里只返回状态
        else:
            if self.active_speech_detected:
                # 处于语音检测后，计算静音帧数
                self.silence_chunks_count += 1
                
            # 尚未检测到语音时，缓存帧
            # 否则，如果是语音后的静音，我们将其作为 trailing silence 缓存
            self.frame_buffer.append(audio_chunk)

        return is_speech


    def is_silence_end(self) -> bool:
        """
        检查是否满足静音超时条件，即语音已结束。
        
        :return: True 如果满足静音超时条件。
        """
        if self.active_speech_detected and self.silence_chunks_count > SILENCE_CHUNK_COUNT:
            # 重置状态，准备下一次检测
            self.active_speech_detected = False
            self.silence_chunks_count = 0
            self.frame_buffer.clear()
            return True
        return False

    def get_buffered_frames(self) -> List[bytes]:
        """
        返回当前缓冲区中的帧 (用于在语音开始时发送 leading silence)。
        """
        frames = list(self.frame_buffer)
        self.frame_buffer.clear()
        return frames

    def reset(self):
        """重置 VAD 状态。"""
        self.silence_chunks_count = 0
        self.active_speech_detected = False
        self.frame_buffer.clear()
        print("VAD state reset.")


if __name__ == '__main__':
    # 示例用法
    VAD_RATE = 16000
    CHUNK_MS = 20
    
    vad_detector = VADDetector(sample_rate=VAD_RATE, chunk_duration_ms=CHUNK_MS)
    
    # 模拟一个静音 + 语音 + 静音的场景
    # 模拟帧大小 (16kHz, 16bit, 20ms) -> 16000 * 0.020 * 2 = 640 bytes
    SPEECH_CHUNK_SIZE = 640
    SILENCE_CHUNK = b'\x00' * SPEECH_CHUNK_SIZE # 纯静音
    NOISE_CHUNK = b'\x55' * SPEECH_CHUNK_SIZE # 噪音/语音
    
    print("\n--- VAD Simulation Start ---")
    
    frames_to_send: List[bytes] = []

    def simulate_processing(chunk, label):
        is_speech = vad_detector.process_chunk(chunk)
        
        # 实时发送逻辑
        if is_speech:
            # 如果是语音，先发送缓冲区中的 leading silence
            if vad_detector.active_speech_detected: # 确保 VAD 已被触发
                frames_to_send.extend(vad_detector.get_buffered_frames())
            # 发送当前语音帧
            frames_to_send.append(chunk)
        elif vad_detector.active_speech_detected:
            # 语音后的静音，放入缓冲区 (trailing silence)
            frames_to_send.append(chunk)

        # 检查是否结束
        is_end = vad_detector.is_silence_end()
        
        status = f"Speech: {is_speech}, Active: {vad_detector.active_speech_detected}, Silence Cnt: {vad_detector.silence_chunks_count}"
        
        if is_end:
            print(f"[{label}] VAD END DETECTED. Total chunks to send: {len(frames_to_send)}")
            frames_to_send.clear()
        
        return status

    # 1. 初始静音 (Leading Silence)
    print("\n[Phase 1] Initial Silence (Should not trigger)")
    for i in range(10):
        status = simulate_processing(SILENCE_CHUNK, f"S{i}")
        # print(f"S{i}: {status}")

    # 2. 语音开始
    print("\n[Phase 2] Speech Start (Should trigger 'Active' and flush buffer)")
    for i in range(20):
        status = simulate_processing(NOISE_CHUNK, f"N{i}")
        # print(f"N{i}: {status}")

    # 3. 语音后的静音 (Trailing Silence + Timeout Check)
    print("\n[Phase 3] Trailing Silence (Should count up and then END)")
    for i in range(SILENCE_CHUNK_COUNT + 10):
        status = simulate_processing(SILENCE_CHUNK, f"S{i+10}")
        # print(f"S{i+10}: {status}")
        if not vad_detector.active_speech_detected:
            break
            
    print("--- VAD Simulation Finished ---")
