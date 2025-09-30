import asyncio
import sys
import os

# 将项目根目录添加到 Python 路径，以便导入模块
# 假设 run.py 位于 petcar-ai/server/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    # 导入配置
    from server.config import CONFIG, ASR_CONFIG, LLM_CONFIG, TTS_CONFIG, DEVICE
    
    # 导入模型引擎
    from server.models.asr_engine import ASREngine
    from server.models.llm_engine import LLMEngine
    from server.models.tts_engine import TTSEngine
    
    # 导入流水线和服务器
    from server.pipeline.conversation import ConversationPipeline
    from server.api.server import PetCarServer
    
except ImportError as e:
    print(f"FATAL ERROR: Failed to import necessary modules: {e}")
    print("Please ensure your project structure and Python path are correctly set up.")
    print("Exiting.")
    sys.exit(1)


def initialize_models():
    """
    初始化所有 AI 模型引擎。
    """
    print("\n--- 1. Initializing AI Models ---")
    
    # 1. ASR Engine
    try:
        asr_engine = ASREngine(
            model_path=ASR_CONFIG["model_path"],
            wakeup_word=ASR_CONFIG["wakeup_word"]
        )
    except Exception as e:
        print(f"ERROR: Failed to initialize ASR Engine: {e}")
        asr_engine = None

    # 2. LLM Engine
    try:
        llm_engine = LLMEngine(
            model_path=LLM_CONFIG["model_path"],
            quantization_config=LLM_CONFIG["quantization_config"]
        )
    except Exception as e:
        print(f"ERROR: Failed to initialize LLM Engine: {e}")
        llm_engine = None

    # 3. TTS Engine
    try:
        tts_engine = TTSEngine(
            model_path=TTS_CONFIG["model_path"],
            device=TTS_CONFIG["device"]
        )
    except Exception as e:
        print(f"ERROR: Failed to initialize TTS Engine: {e}")
        tts_engine = None
        
    if not all([asr_engine, llm_engine, tts_engine]):
        print("Warning: One or more critical AI models failed to load. The system may run in partial or mock mode.")

    return asr_engine, llm_engine, tts_engine


def main():
    """
    主函数：加载模型，创建流水线，并启动 API 服务。
    """
    # 1. 初始化模型
    asr_engine, llm_engine, tts_engine = initialize_models()

    if not all([asr_engine, llm_engine, tts_engine]):
        print("\nFATAL: Not all required AI engines initialized successfully. Cannot start full service.")
        # 在实际部署中，这里应该优雅地退出或进入调试/Mock模式
        # For demo purposes, we exit if models fail to load
        # return 

    # 2. 创建核心交互流水线
    print("\n--- 2. Creating Conversation Pipeline ---")
    pipeline = ConversationPipeline(asr_engine, llm_engine, tts_engine)

    # 3. 创建并启动 WebSocket 服务器
    host = CONFIG["SYSTEM"]["HOST"]
    port = CONFIG["SYSTEM"]["PORT"]
    
    server = PetCarServer(host, port, pipeline)
    
    print("\n--- 3. Starting PetCar AI WebSocket Server ---")
    print(f"Server Host: {host}, Port: {port}")
    print("Ready to accept connections from the PetCar client.")

    try:
        server.start()
    except KeyboardInterrupt:
        print("\nServer shutting down by user request (Ctrl+C).")
    except Exception as e:
        print(f"\nFATAL SERVER ERROR: {e}")
    finally:
        # 清理工作，如关闭模型连接等（如果 SDK 需要）
        print("Server shutdown complete.")


if __name__ == '__main__':
    # 检查是否在 GPU 设备上运行
    if 'cuda' in DEVICE:
        print(f"*** Running on GPU: {DEVICE} ***")
    
    main()
