# app/joystick_handler.py
import threading
import time
import pygame
from .car_state import car_state
from .config import MAX_SPEED

class JoystickHandler(threading.Thread):
    """
    负责监听手柄输入并更新小车状态的线程类。
    使用 Pygame 的 joystick 模块来读取手柄事件。
    """
    def __init__(self):
        super().__init__(name="JoystickHandlerThread", daemon=True)
        self.running = True
        self.joystick = None
        
        # 初始化 Pygame
        try:
            pygame.init()
            pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
                print(f"Joystick '{self.joystick.get_name()}' found.")
            else:
                print("No joystick found. Joystick handler will not run.")
                self.running = False
        except Exception as e:
            print(f"Error initializing Pygame or joystick: {e}")
            self.running = False

    def _get_direction_and_speed(self, axis_x: float, axis_y: float):
        """
        根据摇杆的 x, y 轴值，计算小车的方向和速度。
        """
        speed = 0.0
        direction = "stop"

        # 使用 y 轴（通常是左右摇杆控制前进后退）
        # 排除摇杆中心点的微小抖动
        if abs(axis_y) > 0.1:
            speed = abs(axis_y) * MAX_SPEED
            if axis_y < 0:
                direction = "forward"
            else:
                direction = "backward"

        # 使用 x 轴（通常是左右摇杆控制转向）
        # 这里为了简化，我们只处理前进后退，转向可以通过其他按键实现
        # 如果需要更复杂的混合控制，可以调整这里的逻辑
        if abs(axis_x) > 0.1:
            if axis_x < 0:
                direction = "left"
            else:
                direction = "right"
                
        return direction, speed

    def run(self):
        """
        线程主循环，持续监听手柄事件。
        """
        if not self.running:
            return

        print("Joystick handler thread started.")
        try:
            while self.running:
                pygame.event.pump()
                
                # 获取摇杆的轴值
                axis_x = self.joystick.get_axis(0)
                axis_y = self.joystick.get_axis(1)
                
                # 根据摇杆值更新状态
                direction, speed = self._get_direction_and_speed(axis_x, axis_y)

                # 检查是否按下了停止键（例如，'X' 键）
                if self.joystick.get_button(0): # 假设按钮0是停止键
                    direction = "stop"
                    speed = 0.0

                car_state.update_state(
                    direction=direction,
                    speed=speed,
                    source="joystick"
                )
                
                time.sleep(1/60) # 约 60Hz 更新频率

        except pygame.error as e:
            print(f"Pygame error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            self.stop()

    def stop(self):
        """
        安全停止线程。
        """
        print("Stopping joystick handler thread.")
        self.running = False
        pygame.quit()
