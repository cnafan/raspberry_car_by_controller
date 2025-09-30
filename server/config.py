import os
from typing import Dict, Any

# --- 系统配置 ---
SERVER_HOST = "0.0.0.0"  # 监听所有网络接口
SERVER_PORT = 8765       # WebSocket 端口

# --- 硬件配置 ---
# 假设 CUDA 设备 ID 为 0
DEVICE = "cuda:0" 
if not os.path.exists('/dev/nvidia0'): # 简单的检查 CUDA 是否可用
    DEVICE = "cpu"
    print(f"Warning: CUDA not found. Running models on {DEVICE}.")
else:
    print(f"Running models on {DEVICE}.")


# --- 模型路径配置 (请替换为您的实际路径) ---

# 基础模型目录，所有模型都放在这个目录下
MODEL_DIR = os.environ.get("PETCAR_MODEL_DIR", "/data/petcar_models")

# 1. ASR 模型配置 (SenseVoice)
ASR_CONFIG: Dict[str, Any] = {
    "model_path": os.path.join(MODEL_DIR, "sensevoice/sensevoice-trigger"),
    "wakeup_word": "小车小车",
    "sample_rate": 16000,
    "channels": 1,
}

# 2. LLM 模型配置 (Qwen3-1.7B 量化版)
LLM_CONFIG: Dict[str, Any] = {
    "model_path": os.path.join(MODEL_DIR, "qwen3/Qwen3-1.8B-Int4"),
    "quantization_config": {
        "load_in_4bit": True,      # 启用 4-bit 量化加载
        "bnb_4bit_compute_dtype": "torch.bfloat16",
        # ... 其他量化参数
    },
    "max_length": 512,            # 最大生成长度
    "temperature": 0.7,           # 采样温度
}

# 3. TTS 模型配置 (CosyVoice)
TTS_CONFIG: Dict[str, Any] = {
    "model_path": os.path.join(MODEL_DIR, "cosyvoice/cosyvoice-24k"),
    "device": DEVICE,
    "sample_rate": 24000,
    "voice_role": "petcar_default_role", # 默认音色 ID
}

# --- 运行时配置 ---

RUNTIME_CONFIG: Dict[str, Any] = {
    # 如果 ASR 检测到唤醒词后，允许的最长静音时间 (秒)
    "asr_timeout": 5.0, 
    # LLM 回复的最大等待时间 (秒)
    "llm_response_timeout": 30.0,
    # 小车端需要监听的动作指令前缀 (用于 LLM 解析)
    "action_command_prefix": "[ACTION:", 
}


# --- 主配置字典 ---
CONFIG = {
    "SYSTEM": {
        "HOST": SERVER_HOST,
        "PORT": SERVER_PORT,
        "DEVICE": DEVICE
    },
    "ASR": ASR_CONFIG,
    "LLM": LLM_CONFIG,
    "TTS": TTS_CONFIG,
    "RUNTIME": RUNTIME_CONFIG,
}


if __name__ == '__main__':
    # 打印配置以供检查
    print("--- PetCar AI Server Configuration ---")
    for section, settings in CONFIG.items():
        print(f"\n[{section}]")
        for key, value in settings.items():
            print(f"  {key:<20}: {value}")
