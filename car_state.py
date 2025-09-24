# app/car_state.py
import threading
import time

class CarState:
    """
    一个线程安全的全局状态管理类。
    用于在不同线程（如手柄监听、WebSocket广播）之间共享小车状态。
    """
    def __init__(self):
        # 初始化状态字典，包含方向、速度、控制来源和时间戳
        self._state = {
            "direction": "stop",  # forward, backward, left, right, stop
            "speed": 0.0,         # 0.0 ~ 1.0
            "source": "web",      # "web" / "joystick"
            "timestamp": time.time() # 状态更新时间戳
        }
        # 使用 threading.Lock 保证线程安全
        self._lock = threading.Lock()

    def update_state(self, **kwargs):
        """
        线程安全地更新小车状态。
        传入键值对参数，例如：update_state(direction="forward", speed=0.5)
        """
        with self._lock:
            for key, value in kwargs.items():
                if key in self._state:
                    self._state[key] = value
            # 每次更新状态时，同时更新时间戳
            self._state["timestamp"] = time.time()

    def get_state(self):
        """
        线程安全地获取当前小车的状态。
        返回一个状态字典的副本。
        """
        with self._lock:
            return self._state.copy()

# 实例化一个全局的 CarState 对象，供其他模块调用
car_state = CarState()
