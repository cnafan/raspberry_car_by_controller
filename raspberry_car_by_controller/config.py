# app/config.py
import os

# --- 项目配置 ---
# 是否在没有硬件的情况下运行（用于开发和测试）
# 设置为 True 后，GPIO 操作将被模拟，避免在非树莓派环境下报错
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "False").lower() == "true"

# --- GPIO 引脚映射 (BCM 模式) ---
# 使用两个 TB6612FNG 驱动板：
# - 驱动板 1：控制左前轮（A通道）和左后轮（B通道）
# - 驱动板 2：控制右前轮（A通道）和右后轮（B通道）

# === 驱动板 1（左侧：左前 + 左后） ===
DRIVER1_PWMA = 12   # 左前轮 PWM
DRIVER1_AIN1 = 6    # 左前轮方向1
DRIVER1_AIN2 = 5    # 左前轮方向2

DRIVER1_PWMB = 13   # 左后轮 PWM
DRIVER1_BIN1 = 19   # 左后轮方向1
DRIVER1_BIN2 = 26   # 左后轮方向2

DRIVER1_STBY = 4    # 驱动板1使能引脚

# === 驱动板 2（右侧：右前 + 右后） ===
DRIVER2_PWMA = 18   # 右前轮 PWM
DRIVER2_AIN1 = 20   # 右前轮方向1
DRIVER2_AIN2 = 21   # 右前轮方向2

DRIVER2_PWMB = 23   # 右后轮 PWM
DRIVER2_BIN1 = 24   # 右后轮方向1
DRIVER2_BIN2 = 25   # 右后轮方向2

DRIVER2_STBY = 17   # 驱动板2使能引脚

# --- 速度和控制参数 ---
# PWM 频率 (Hz)，影响电机响应速度和平稳性
PWM_FREQUENCY = 1000

# 最大速度限制 (0.0 - 1.0)
MAX_SPEED = 0.8

# 加速/减速步长（每帧更新的速度增量）
SPEED_STEP = 0.05

# 自动停止超时时间 (秒)
# 如果在规定时间内没有收到新的控制指令，则自动停止小车
TIMEOUT_SECONDS = 1.0

# --- 通信参数 ---
# WebSocket 广播频率 (Hz)
WS_BROADCAST_RATE = 20
