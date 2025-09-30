import os

# --- 通信配置 ---
# 服务端 WebSocket 地址 (请根据实际部署修改)
SERVER_HOST = os.environ.get("PETCAR_SERVER_HOST", "192.168.1.100") 
SERVER_PORT = int(os.environ.get("PETCAR_SERVER_PORT", 8765))
SERVER_URL = f"ws://{SERVER_HOST}:{SERVER_PORT}"

# WebSocket 路径
AUDIO_IN_PATH = "/audio/in"   # 麦克风音频流上传路径
AUDIO_OUT_PATH = "/audio/in"  # TTS 语音流接收路径 (假设使用同一连接的双向流)
CONTROL_PATH = "/control"     # 动作指令和心跳路径 (假设也用同一连接)

# --- 音频设备配置 (与服务端模型匹配) ---
# 麦克风输入 (ASR 输入)
AUDIO_RATE = 16000         # 采样率 (Hz)
AUDIO_CHANNELS = 1         # 声道数 (单声道)
AUDIO_FORMAT = 8           # PyAudio.paInt16 对应的数字
AUDIO_CHUNK_SIZE = 1024    # 每次从麦克风读取的帧大小 (bytes)

# 扬声器输出 (TTS 输出)
AUDIO_OUT_RATE = 24000         # 服务端 CosyVoice 模型的输出采样率
AUDIO_OUT_CHANNELS = 1

# --- VAD 配置 ---
VAD_ENABLED = True             # 是否启用本地语音活动检测 (建议启用)
VAD_AGGRESSIVENESS = 3         # WebRTC VAD 积极性 (0-3)
VAD_TIMEOUT_MS = 1500          # 语音结束后多久判断为静音结束 (毫秒)


# --- 硬件/GPIO 配置 (树莓派) ---
# 假设使用 L298N 或类似电机驱动板
MOTOR_PINS = {
    "LEFT_FORWARD": 17,
    "LEFT_BACKWARD": 18,
    "RIGHT_FORWARD": 27,
    "RIGHT_BACKWARD": 22,
    "ENABLE_PIN": 25, # PWM 调速引脚 (可选)
}

# 其他硬件配置 (例如灯光、传感器)
STATUS_LED_PIN = 4 # 状态指示灯 (例如，对话激活时亮起)
ULTRASONIC_SENSOR = {
    "TRIGGER": 5,
    "ECHO": 6,
}


# --- 主配置字典 ---
CONFIG = {
    "COMMUNICATION": {
        "SERVER_URL": SERVER_URL,
        "AUDIO_IN_PATH": AUDIO_IN_PATH,
        "AUDIO_OUT_PATH": AUDIO_OUT_PATH,
    },
    "AUDIO_DEVICE": {
        "RATE_IN": AUDIO_RATE,
        "RATE_OUT": AUDIO_OUT_RATE,
        "CHUNK_SIZE": AUDIO_CHUNK_SIZE,
        "VAD_ENABLED": VAD_ENABLED,
    },
    "HARDWARE": {
        "MOTOR_PINS": MOTOR_PINS,
        "STATUS_LED_PIN": STATUS_LED_PIN,
    }
}


if __name__ == '__main__':
    # 打印配置以供检查
    print("--- PetCar AI Client Configuration ---")
    for section, settings in CONFIG.items():
        print(f"\n[{section}]")
        for key, value in settings.items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for sub_key, sub_value in value.items():
                     print(f"    {sub_key:<15}: {sub_value}")
            else:
                print(f"  {key:<20}: {value}")
