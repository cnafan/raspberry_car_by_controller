# app/car_state.py
import threading
import time

class CarState:
    """
    一个线程安全的全局状态管理类。
    用于在不同线程（如手柄监听、WebSocket广播）之间共享小车状态。
    支持方向、速度以及左右轮速度。
    """
    def __init__(self):
        self._state = {
            "direction": "stop",   # forward, backward, left, right, stop
            "speed": 0.0,          # 0.0 ~ 1.0
            "leftSpeed": 0.0,      # 左轮速度
            "rightSpeed": 0.0,     # 右轮速度
            "source": "web",       # "web" / "joystick"
            "timestamp": time.time()
        }
        self._lock = threading.Lock()

    def update_state(self, **kwargs):
        """
        线程安全地更新小车状态。
        可以更新 direction, speed, leftSpeed, rightSpeed 等字段。
        """
        with self._lock:
            for key, value in kwargs.items():
                if key in self._state:
                    self._state[key] = value
            # 每次更新状态时更新时间戳
            self._state["timestamp"] = time.time()

    def get_state(self):
        """
        线程安全地获取当前小车状态的副本。
        """
        with self._lock:
            return self._state.copy()

# 全局单例对象
car_state = CarState()
