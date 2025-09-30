import asyncio
import re
from typing import Dict, Any, Tuple, Optional

# 导入上一节定义的流式管理类
from server.pipeline.streaming_manager import StreamingManager, AudioQueue, TextQueue, PCMQueue
# 导入模型引擎（此处使用相对导入，实际项目中需确保路径正确）
try:
    from server.models.asr_engine import ASREngine
    from server.models.llm_engine import LLMEngine
    from server.models.tts_engine import TTSEngine
except ImportError:
    # 允许在不配置环境的情况下运行 mock
    class ASREngine:
        def __init__(self, *args, **kwargs): pass
        def start_stream(self): print("Mock ASR stream started.")
        def transcribe_stream(self, chunk: bytes) -> Optional[str]: 
            # 简单的模拟识别逻辑
            if len(chunk) > 4096 * 5:
                return "小车小车，请向前走。"
            return None
        def end_stream(self) -> Optional[str]: return "最终识别结果。"
        def detect_wakeup_word(self, text: str) -> bool: return "小车小车" in text
    class LLMEngine:
        def __init__(self, *args, **kwargs): self.history = []; print("Mock LLM initialized.")
        def chat_stream(self, text: str) -> Generator[str, None, None]: 
            import time
            response = "好的，我这就向前走五步。 [ACTION:forward(5)]"
            for char in response:
                time.sleep(0.02)
                yield char
        def clear_history(self): self.history = []
    class TTSEngine:
        def __init__(self, *args, **kwargs): pass
        def synthesize_stream(self, text: str) -> Generator[bytes, None, None]:
            import time
            chunk_size = 4096
            for _ in range(5):
                time.sleep(0.05)
                yield b'\x01' * chunk_size
            

# 定义 LLM 动作指令的正则模式
ACTION_PATTERN = re.compile(r"\[ACTION:([a-zA-Z_]+\([\w\d\s,.]*\))]")

class ConversationPipeline:
    """
    语音交互流水线的主控制逻辑。
    负责协调 ASR -> LLM -> TTS 的流式数据传输和处理。
    """

    def __init__(self, asr_engine: ASREngine, llm_engine: LLMEngine, tts_engine: TTSEngine):
        self.asr_engine = asr_engine
        self.llm_engine = llm_engine
        self.tts_engine = tts_engine
        self.manager = StreamingManager()
        self.conversation_active = False # 标志对话是否处于激活状态（已触发唤醒词）
        
        print("Conversation Pipeline initialized.")

    async def start_new_session(self):
        """
        开始一个新的语音会话，创建新的流式队列，并重置 LLM 历史。
        """
        self.manager.close_all() # 确保关闭上一个会话
        self.manager.start_new_conversation()
        self.llm_engine.clear_history()
        self.asr_engine.start_stream()
        self.conversation_active = False
        print("New conversation session started. Awaiting wakeup word...")

    async def run_pipeline(self) -> Tuple[bool, Optional[str]]:
        """
        运行整个语音交互流水线：ASR -> LLM -> TTS。
        
        :return: (bool: 是否成功执行 LLM 对话, Optional[str]: 提取到的动作指令)
        """
        print("\n--- Pipeline Execution Started ---")
        queues = self.manager.get_queues()
        audio_in = queues["audio_in"]
        text_out = queues["text_out"]
        pcm_out = queues["pcm_out"]

        # 1. 启动 ASR 和 LLM/TTS 的任务
        asr_task = asyncio.create_task(self._asr_to_llm(audio_in, text_out))
        tts_task = asyncio.create_task(self._llm_to_tts(text_out, pcm_out))
        
        try:
            # 等待 ASR/LLM 流程完成 (即 ASR 任务完成后关闭了 TextQueue)
            final_result = await asr_task 
            action_command = final_result["action_command"]
            
            # 2. 等待 TTS 任务完成
            await tts_task
            
            print("Pipeline completed successfully.")
            return True, action_command

        except Exception as e:
            print(f"Pipeline error: {e}")
            # 确保流被关闭
            asr_task.cancel()
            tts_task.cancel()
            return False, None
        finally:
            self.manager.close_all() # 确保所有队列关闭
            print("--- Pipeline Execution Finished ---")


    async def _asr_to_llm(self, audio_in: AudioQueue, text_out: TextQueue) -> Dict[str, Any]:
        """
        处理 ASR 阶段：从音频流转写，触发对话，并启动 LLM 流式生成。
        """
        full_transcription = ""
        action_command: Optional[str] = None
        
        async for audio_chunk in audio_in:
            # 1. 流式 ASR 转写
            interim_text = self.asr_engine.transcribe_stream(audio_chunk)
            
            if interim_text:
                full_transcription += interim_text
                print(f"[ASR] Interim Text: {interim_text}")
                
                # 2. 唤醒词检测
                if not self.conversation_active and self.asr_engine.detect_wakeup_word(full_transcription):
                    self.conversation_active = True
                    # 清除唤醒词，只保留命令
                    command_text = full_transcription.replace(self.asr_engine.wakeup_word, "", 1).strip()
                    print(f"[LLM] Wakeup triggered. Command: '{command_text}'")
                    
                    # 3. 触发 LLM 流式生成
                    # 注意：这是最关键的一步，必须是非阻塞的
                    asyncio.create_task(self._llm_chat_and_parse(command_text, text_out))
                    
                    # ASR 转写继续，但LLM只处理触发后的第一段完整命令。
                    # 在简单模式下，我们假设唤醒词触发后，ASR流的后续内容是 LLM 的输入。
                    # 简化处理：一旦唤醒词触发，ASR任务继续接收音频直到流关闭。
                    
        # ASR 输入流结束
        final_text = self.asr_engine.end_stream()
        if final_text and not self.conversation_active:
            print(f"[ASR] Final result (Not triggered): {final_text}")
            
        # 4. 如果 LLM 任务已经启动，它会自己关闭 text_out 队列。
        # 如果 ASR 结束了但 LLM 没有被触发，我们也要关闭 TextQueue 以结束 TTS 任务
        if not self.conversation_active:
            await text_out.put("对不起，我没有听到唤醒词，请再说一次。")
            text_out.close()
            
        return {"final_transcription": full_transcription, "action_command": action_command}


    async def _llm_chat_and_parse(self, command_text: str, text_out: TextQueue):
        """
        处理 LLM 阶段：流式生成回复，解析动作指令，并将回复文本传给 TTS。
        """
        full_response = ""
        action_command: Optional[str] = None
        
        # 1. 获取 LLM 的流式生成器
        llm_stream = self.llm_engine.chat_stream(command_text)
        
        # 2. 异步处理 LLM 输出
        try:
            # 由于 llm_stream 是同步生成器，我们需要在一个单独的线程/进程中运行它
            # 或者将其包装成异步迭代器。这里我们用一个简单的循环来模拟异步处理。
            for chunk in llm_stream:
                full_response += chunk
                
                # 3. 实时解析动作指令 (指令可能在回复的开头、中间或结尾)
                match = ACTION_PATTERN.search(full_response)
                if match and not action_command:
                    action_command = match.group(1)
                    print(f"[LLM] ACTION PARSED: {action_command}")
                    # 提取指令后，我们把指令从 LLM 文本中移除，不让 TTS 读出来
                    clean_chunk = re.sub(ACTION_PATTERN, "", chunk)
                else:
                    clean_chunk = chunk
                
                # 4. 将清理后的文本块传给 TTS (通过 text_out 队列)
                if clean_chunk:
                    await text_out.put(clean_chunk)
                    
        except Exception as e:
            print(f"LLM streaming error: {e}")
        finally:
            # LLM 生成完成后，关闭 TextQueue
            text_out.close()
            print(f"[LLM] Full Response: {full_response.strip()}")
            print("[LLM] TextQueue closed.")


    async def _llm_to_tts(self, text_in: TextQueue, pcm_out: PCMQueue):
        """
        处理 TTS 阶段：从 LLM 文本流实时合成 PCM 音频。
        """
        full_text_to_synthesize = ""
        
        # 1. 从 TextQueue 获取完整的文本流
        async for text_chunk in text_in:
            full_text_to_synthesize += text_chunk
            # 2. 将文本块传入 TTS 引擎进行流式合成
            
            # NOTE: 实际 CosyVoice SDK 需要设计为可以接收持续的文本输入
            # 并根据标点符号或固定时间间隔进行分段合成。
            # 在简化实现中，我们假设 TTS 引擎可以处理累计的文本，并实时流出 PCM。
            
            # 假设 TTS 引擎是流式生成器
            pcm_stream = self.tts_engine.synthesize_stream(text_chunk) 
            
            # 3. 将 TTS 生成的 PCM 块放入 PCMQueue
            for pcm_chunk in pcm_stream:
                await pcm_out.put(pcm_chunk)
                
        # 4. 文本流结束，TTS 完成所有合成后，关闭 PCMQueue
        pcm_out.close()
        print(f"[TTS] Synthesis finished. Total text: '{full_text_to_synthesize[:50]}...'")
        print("[TTS] PCMQueue closed.")


    def get_pcm_output_queue(self) -> PCMQueue:
        """提供给 API Server 用于推送音频流到客户端的接口。"""
        queues = self.manager.get_queues()
        return queues["pcm_out"]

    def get_audio_input_queue(self) -> AudioQueue:
        """提供给 API Server 用于接收客户端音频流的接口。"""
        queues = self.manager.get_queues()
        return queues["audio_in"]
    
    def is_active(self) -> bool:
        """检查是否有正在进行的对话。"""
        return self.manager.audio_in_queue is not None
    

if __name__ == '__main__':
    # 示例用法
    # 假设模型已经实例化 (使用上面的 mock 类)
    mock_asr = ASREngine(model_path="mock")
    mock_llm = LLMEngine(model_path="mock")
    mock_tts = TTSEngine(model_path="mock")
    
    pipeline = ConversationPipeline(mock_asr, mock_llm, mock_tts)

    async def mock_input_task(audio_queue: AudioQueue):
        """模拟客户端上传音频"""
        print("\n[Mock Client] Starting audio upload...")
        # 1. 模拟唤醒词和命令
        for _ in range(20):
            await audio_queue.put(b'\xaa' * 1024) # 传输唤醒词
            await asyncio.sleep(0.03)
            
        # 2. 模拟后续语音/沉默
        for _ in range(30):
            await audio_queue.put(b'\xbb' * 1024)
            await asyncio.sleep(0.03)

        audio_queue.close()
        print("[Mock Client] Audio upload finished.")

    async def mock_output_task(pcm_queue: PCMQueue):
        """模拟客户端播放音频"""
        print("\n[Mock Client] Starting PCM playback download...")
        total_bytes = 0
        async for chunk in pcm_queue:
            total_bytes += len(chunk)
            # 模拟播放
            await asyncio.sleep(len(chunk) / 48000)
        print(f"[Mock Client] Playback finished. Total PCM bytes received: {total_bytes}.")

    async def main_test():
        await pipeline.start_new_session()
        
        audio_in = pipeline.get_audio_input_queue()
        pcm_out = pipeline.get_pcm_output_queue()

        input_task = asyncio.create_task(mock_input_task(audio_in))
        output_task = asyncio.create_task(mock_output_task(pcm_out))
        pipeline_task = asyncio.create_task(pipeline.run_pipeline())
        
        await asyncio.gather(input_task, output_task, pipeline_task)
        
        success, action_cmd = pipeline_task.result()
        print(f"\n--- TEST SUMMARY ---")
        print(f"Pipeline Success: {success}")
        print(f"Action Command Extracted: {action_cmd}")

    try:
        asyncio.run(main_test())
    except KeyboardInterrupt:
        print("Test interrupted.")
