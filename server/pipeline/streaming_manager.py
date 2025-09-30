import asyncio
from typing import Optional, List, Dict, Any

# 定义音频参数常量 (与 ASR/TTS 引擎保持一致)
AUDIO_SAMPLE_RATE = 16000 # ASR 输入常用 16kHz
PCM_SAMPLE_RATE = 24000   # TTS 输出常用 24kHz
BYTES_PER_SAMPLE = 2      # 16-bit PCM

class AudioQueue:
    """
    用于缓存客户端上传的原始音频 PCM 数据块的异步队列。
    作为 ASR 引擎的输入来源。
    """
    def __init__(self):
        # 存储 bytes 数据块
        self.queue = asyncio.Queue()
        self.is_finished = False
        print("AudioQueue initialized.")

    async def put(self, chunk: bytes):
        """将音频数据块放入队列。"""
        if not self.is_finished:
            await self.queue.put(chunk)
            
    async def get(self) -> bytes:
        """从队列中取出音频数据块。"""
        return await self.queue.get()

    def task_done(self):
        """通知队列数据块已被处理。"""
        self.queue.task_done()

    def close(self):
        """标记输入流已结束，防止新的数据进入。"""
        self.is_finished = True
        # 放入一个特殊标记，让消费者知道流已结束
        # None 作为流结束标记是常用的异步队列模式
        self.queue.put_nowait(None)
        print("AudioQueue closed and marked as finished.")

    def __aiter__(self):
        return self

    async def __anext__(self):
        """实现异步迭代器协议，方便在 'async for' 中使用。"""
        chunk = await self.get()
        if chunk is None:
            raise StopAsyncIteration
        return chunk

    def is_empty(self) -> bool:
        """检查队列是否为空。"""
        return self.queue.empty()


class TextQueue:
    """
    用于缓存 LLM 的流式文本输出的异步队列。
    作为 TTS 引擎的输入来源。
    """
    def __init__(self):
        # 存储 str 文本块
        self.queue = asyncio.Queue()
        self.is_finished = False
        print("TextQueue initialized.")

    async def put(self, text_chunk: str):
        """将文本块放入队列。"""
        if not self.is_finished:
            await self.queue.put(text_chunk)
            
    async def get(self) -> str:
        """从队列中取出文本块。"""
        return await self.queue.get()

    def close(self):
        """标记文本流已结束，放入特殊标记。"""
        self.is_finished = True
        self.queue.put_nowait(None)
        print("TextQueue closed and marked as finished.")

    def __aiter__(self):
        return self

    async def __anext__(self):
        """实现异步迭代器协议。"""
        chunk = await self.get()
        if chunk is None:
            raise StopAsyncIteration
        return chunk


class PCMQueue:
    """
    用于缓存 TTS 合成后的 PCM 音频数据块的异步队列。
    作为 WebSocket 服务端推送给小车客户端的输出来源。
    """
    def __init__(self):
        # 存储 bytes 数据块
        self.queue = asyncio.Queue()
        self.is_finished = False
        self.queue_id = id(self)
        print(f"PCMQueue (ID: {self.queue_id}) initialized.")

    async def put(self, pcm_chunk: bytes):
        """将 PCM 音频数据块放入队列。"""
        if not self.is_finished:
            await self.queue.put(pcm_chunk)
            
    async def get(self) -> bytes:
        """从队列中取出 PCM 音频数据块。"""
        return await self.queue.get()

    def close(self):
        """标记 PCM 流已结束，放入特殊标记。"""
        self.is_finished = True
        self.queue.put_nowait(None)
        print(f"PCMQueue (ID: {self.queue_id}) closed and marked as finished.")

    def __aiter__(self):
        return self

    async def __anext__(self):
        """实现异步迭代器协议。"""
        chunk = await self.get()
        if chunk is None:
            raise StopAsyncIteration
        return chunk


class StreamingManager:
    """
    管理 PetCar AI 语音交互流水线中的所有流式数据队列。
    """
    def __init__(self):
        # ASR 输入队列
        self.audio_in_queue: Optional[AudioQueue] = None
        # LLM 输出 / TTS 输入队列
        self.llm_text_out_queue: Optional[TextQueue] = None
        # TTS 输出 / Car 播放队列
        self.pcm_out_queue: Optional[PCMQueue] = None
        
    def start_new_conversation(self):
        """启动新一轮对话流，创建所有新的队列。"""
        self.audio_in_queue = AudioQueue()
        self.llm_text_out_queue = TextQueue()
        self.pcm_out_queue = PCMQueue()
        print("StreamingManager started a new conversation stream.")

    def get_queues(self) -> Dict[str, Any]:
        """返回所有活动队列，供 Conversation Pipeline 使用。"""
        if not all([self.audio_in_queue, self.llm_text_out_queue, self.pcm_out_queue]):
            raise RuntimeError("Conversation streams not initialized. Call start_new_conversation().")
            
        return {
            "audio_in": self.audio_in_queue,
            "text_out": self.llm_text_out_queue,
            "pcm_out": self.pcm_out_queue,
        }

    def close_all(self):
        """关闭所有队列。"""
        if self.audio_in_queue:
            self.audio_in_queue.close()
        if self.llm_text_out_queue:
            self.llm_text_out_queue.close()
        if self.pcm_out_queue:
            self.pcm_out_queue.close()
        
        self.audio_in_queue = None
        self.llm_text_out_queue = None
        self.pcm_out_queue = None
        print("StreamingManager closed all queues.")


if __name__ == '__main__':
    # 示例用法
    async def run_mock_pipeline():
        manager = StreamingManager()
        manager.start_new_conversation()
        queues = manager.get_queues()
        
        audio_in = queues["audio_in"]
        text_out = queues["text_out"]
        pcm_out = queues["pcm_out"]

        # 1. 模拟 ASR 任务 (从 audio_in 读取，写入 text_out)
        async def mock_asr_task():
            print("\n[ASR Task] Started.")
            audio_data_received = 0
            async for chunk in audio_in:
                audio_data_received += len(chunk)
                if audio_data_received > 4096 * 5: # 假设收到一定音频后产生文本
                    text_chunk = "正在识别中..."
                    await text_out.put(text_chunk)
                    # print(f"[ASR Task] Put text: '{text_chunk}'")
                    audio_data_received = 0
            await text_out.put("你好，小车已识别到你的指令。")
            text_out.close()
            print("[ASR Task] Finished and closed TextQueue.")

        # 2. 模拟 TTS 任务 (从 text_out 读取，写入 pcm_out)
        async def mock_tts_task():
            print("\n[TTS Task] Started.")
            async for text_chunk in text_out:
                # 模拟文本被合成并产生 PCM
                pcm_chunk = b'\x00\x00' * 2048 # 模拟 2048 样本 (4096 bytes)
                await pcm_out.put(pcm_chunk)
                # print(f"[TTS Task] Put {len(pcm_chunk)} bytes of PCM.")
            pcm_out.close()
            print("[TTS Task] Finished and closed PCMQueue.")

        # 3. 模拟 Car 客户端音频上传
        async def mock_car_upload():
            print("\n[Car Upload] Started.")
            for i in range(10):
                await audio_in.put(b'\xaa' * 4096)
                await asyncio.sleep(0.1) # 模拟上传延迟
            audio_in.close()
            print("[Car Upload] Finished and closed AudioQueue.")
            
        # 4. 模拟 Car 客户端音频播放
        async def mock_car_playback():
            print("\n[Car Playback] Started.")
            total_bytes_played = 0
            async for pcm_chunk in pcm_out:
                total_bytes_played += len(pcm_chunk)
                # 模拟播放延迟
                await asyncio.sleep(len(pcm_chunk) / (PCM_SAMPLE_RATE * BYTES_PER_SAMPLE))
                # print(f"[Car Playback] Played {len(pcm_chunk)} bytes.")
            print(f"[Car Playback] Finished. Total bytes played: {total_bytes_played}.")

        # 启动所有任务
        await asyncio.gather(
            mock_car_upload(),
            mock_asr_task(),
            mock_tts_task(),
            mock_car_playback()
        )
        
        manager.close_all()
        print("\nMock pipeline finished.")

    # 运行模拟
    try:
        asyncio.run(run_mock_pipeline())
    except KeyboardInterrupt:
        print("Pipeline interrupted.")
