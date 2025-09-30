import os
import time
from typing import Generator, Optional

# 假设 SenseVoice SDK 的导入方式
# 实际部署时，可能需要替换为真实的 SenseVoice Python SDK
try:
    from sensevoice_sdk import SenseVoiceModel
except ImportError:
    print("Warning: sensevoice_sdk not found. Using mock implementation.")
    class SenseVoiceModel:
        def __init__(self, model_path):
            print(f"Mock ASR Model loaded from: {model_path}")
            self.model_path = model_path
            self.stream_state = None

        def create_stream(self, sample_rate, channels):
            # 模拟创建流式识别会话
            self.stream_state = {"buffer": b"", "timestamp": time.time()}
            return self

        def process_chunk(self, audio_chunk) -> Optional[str]:
            # 模拟流式识别
            self.stream_state["buffer"] += audio_chunk
            # 假设每处理 4096 字节音频，就可能产生一个结果
            if len(self.stream_state["buffer"]) >= 4096 * 4: # 假设 16k 16bit mono, 4096*4 约 512ms
                self.stream_state["buffer"] = b"" # 清空缓冲区
                if time.time() - self.stream_state["timestamp"] < 5:
                    return None # 模拟中间结果
                else:
                    self.stream_state["timestamp"] = time.time() # 重置时间
                    # 模拟 ASR 结果，包含触发词和命令
                    mock_results = [
                        "小车小车",
                        "小车小车，今天天气怎么样",
                        "请向前走五步",
                        "再见",
                        "停一下"
                    ]
                    # 简单轮询模拟结果
                    idx = int(time.time() * 10) % len(mock_results)
                    return mock_results[idx] + "。"
            return None

        def end_stream(self) -> Optional[str]:
            # 模拟流结束时的最终结果
            self.stream_state = None
            return "最终结果"
    
class ASREngine:
    """
    SenseVoice (ASR) 模型引擎。
    负责流式语音转写和触发词检测。
    """
    
    def __init__(self, model_path: str, wakeup_word: str = "小车小车"):
        """
        初始化 ASR 引擎。
        :param model_path: SenseVoice 模型文件路径。
        :param wakeup_word: 唤醒词。
        """
        print(f"Initializing ASREngine with model: {model_path}")
        # 在真实环境中，这里会加载 SenseVoice 模型
        self.model = SenseVoiceModel(model_path) 
        self.wakeup_word = wakeup_word
        # 设置音频参数
        self.sample_rate = 16000
        self.channels = 1
        self.stream_instance = None


    def start_stream(self):
        """
        开始一个新的流式转写会话。
        """
        if self.stream_instance:
            self.end_stream()
        
        # 实际调用 SenseVoice 的 create_stream 方法
        self.stream_instance = self.model.create_stream(
            sample_rate=self.sample_rate, 
            channels=self.channels
        )
        print("ASR Stream started.")


    def transcribe_stream(self, audio_chunk: bytes) -> Optional[str]:
        """
        处理一段音频数据，返回转写文本（可能是中间结果或最终结果）。
        
        :param audio_chunk: PCM 格式音频数据块。
        :return: 转写出的文本，如果没有新结果则返回 None。
        """
        if not self.stream_instance:
            raise RuntimeError("ASR stream not started. Call start_stream() first.")
        
        # 实际调用 SenseVoice 的 process_chunk 方法
        text = self.stream_instance.process_chunk(audio_chunk)
        
        return text


    def end_stream(self) -> Optional[str]:
        """
        结束当前的流式转写会话，获取最终结果。
        """
        if not self.stream_instance:
            return None
        
        # 实际调用 SenseVoice 的 end_stream 方法
        final_text = self.stream_instance.end_stream()
        self.stream_instance = None
        print("ASR Stream ended.")
        return final_text
    
    
    def detect_wakeup_word(self, text: str) -> bool:
        """
        检测文本中是否包含唤醒词。
        
        :param text: ASR 转写出的文本。
        :return: 如果包含唤醒词则返回 True。
        """
        if not text:
            return False
            
        # 简单的字符串匹配
        is_detected = self.wakeup_word in text.replace('，', '').replace('。', '').replace(' ', '')
        
        if is_detected:
            print(f"Wakeup word '{self.wakeup_word}' detected in: '{text}'")
            
        return is_detected


if __name__ == '__main__':
    # 示例用法
    # 假设模型的配置在 config.py 中
    MOCK_ASR_MODEL_PATH = "/path/to/sensevoice/model"
    
    asr_engine = ASREngine(model_path=MOCK_ASR_MODEL_PATH, wakeup_word="小车小车")
    
    # 模拟流式输入
    asr_engine.start_stream()
    
    # 假设音频采样率为 16000 Hz, 16-bit PCM, 单声道
    # 1024 字节约为 32ms 的音频
    audio_chunk = b'\x00' * 1024
    
    print("\n--- Simulating 10 seconds of streaming audio ---")
    for i in range(300): # 300 chunks * 32ms ~= 9.6 seconds
        time.sleep(0.032) # 模拟实时输入
        
        # 模拟中间结果的生成
        result = asr_engine.transcribe_stream(audio_chunk)
        
        if result:
            print(f"[{i*0.032:.2f}s] Interim/Final Result: {result.strip()}")
            if asr_engine.detect_wakeup_word(result):
                print(">>> ASR DETECTED WAKEUP WORD. READY FOR COMMAND.")

    final_result = asr_engine.end_stream()
    print(f"\nFinal ASR Result after stream end: {final_result}")
