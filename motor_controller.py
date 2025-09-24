# app/motor_controller.py
import threading
import time
from gpiozero import DigitalOutputDevice, PWMOutputDevice
from gpiozero.pins.mock import MockFactory
from .car_state import car_state
from .config import (
    SIMULATION_MODE,
    DRIVER1_STBY,
    DRIVER1_AIN1, DRIVER1_AIN2, DRIVER1_PWMA,  # 左前
    DRIVER1_BIN1, DRIVER1_BIN2, DRIVER1_PWMB,  # 左后
    DRIVER2_STBY,
    DRIVER2_AIN1, DRIVER2_AIN2, DRIVER2_PWMA,  # 右前
    DRIVER2_BIN1, DRIVER2_BIN2, DRIVER2_PWMB,  # 右后
    PWM_FREQUENCY,
    TIMEOUT_SECONDS,
    SPEED_STEP
)

# 如果处于模拟模式，使用模拟引脚
if SIMULATION_MODE:
    from gpiozero import Device
    Device.pin_factory = MockFactory()
    print("WARNING: Running in simulation mode. No real GPIO control.")


class MotorController(threading.Thread):
    """
    负责驱动电机逻辑的线程类。
    它会持续读取 CarState，并根据状态控制四个轮子。
    """
    def __init__(self):
        super().__init__(name="MotorControllerThread", daemon=True)
        self.running = True

        # --- 左前轮 ---
        self.lf_in1 = DigitalOutputDevice(DRIVER1_AIN1)
        self.lf_in2 = DigitalOutputDevice(DRIVER1_AIN2)
        self.lf_pwm = PWMOutputDevice(DRIVER1_PWMA, frequency=PWM_FREQUENCY, initial_value=0)

        # --- 左后轮 ---
        self.lb_in1 = DigitalOutputDevice(DRIVER1_BIN1)
        self.lb_in2 = DigitalOutputDevice(DRIVER1_BIN2)
        self.lb_pwm = PWMOutputDevice(DRIVER1_PWMB, frequency=PWM_FREQUENCY, initial_value=0)

        # --- 右前轮 ---
        self.rf_in1 = DigitalOutputDevice(DRIVER2_AIN1)
        self.rf_in2 = DigitalOutputDevice(DRIVER2_AIN2)
        self.rf_pwm = PWMOutputDevice(DRIVER2_PWMA, frequency=PWM_FREQUENCY, initial_value=0)

        # --- 右后轮 ---
        self.rb_in1 = DigitalOutputDevice(DRIVER2_BIN1)
        self.rb_in2 = DigitalOutputDevice(DRIVER2_BIN2)
        self.rb_pwm = PWMOutputDevice(DRIVER2_PWMB, frequency=PWM_FREQUENCY, initial_value=0)

        # --- STBY 引脚（使能两个驱动板） ---
        self.stby1 = DigitalOutputDevice(DRIVER1_STBY, initial_value=True)  # 高电平使能
        self.stby2 = DigitalOutputDevice(DRIVER2_STBY, initial_value=True)

    def _set_wheel(self, in1, in2, pwm, speed):
        """
        控制单个轮子。
        speed: -1.0 ~ 1.0
        """
        if speed > 0:
            in1.on()
            in2.off()
        elif speed < 0:
            in1.off()
            in2.on()
        else:
            in1.off()
            in2.off()
        pwm.value = abs(speed)

    def _set_motors(self, left_speed: float, right_speed: float):
        """
        同步设置左右轮组：
        - 左轮组 = 左前 + 左后
        - 右轮组 = 右前 + 右后
        """
        # 左侧两个轮子
        self._set_wheel(self.lf_in1, self.lf_in2, self.lf_pwm, left_speed)
        self._set_wheel(self.lb_in1, self.lb_in2, self.lb_pwm, left_speed)

        # 右侧两个轮子
        self._set_wheel(self.rf_in1, self.rf_in2, self.rf_pwm, right_speed)
        self._set_wheel(self.rb_in1, self.rb_in2, self.rb_pwm, right_speed)

    def _calculate_speed(self, current_speed, target_speed):
        """
        平滑地过渡速度，避免瞬间加速/减速。
        """
        if abs(current_speed - target_speed) > SPEED_STEP:
            if current_speed < target_speed:
                return current_speed + SPEED_STEP
            else:
                return current_speed - SPEED_STEP
        return target_speed

    def run(self):
        """
        线程主循环，持续监控并控制电机。
        """
        print("Motor controller thread started.")
        current_speed = 0.0
        while self.running:
            state = car_state.get_state()
            target_speed = state["speed"]
            direction = state["direction"]

            # 处理超时自动停止
            if time.time() - state["timestamp"] > TIMEOUT_SECONDS:
                target_speed = 0.0
                if state["direction"] != "stop":
                    print("Timeout: No control signal received. Stopping car.")
                    car_state.update_state(direction="stop")

            # 平滑地过渡到目标速度
            current_speed = self._calculate_speed(current_speed, target_speed)

            # 根据方向和速度设置左右轮组
            if direction == "forward":
                self._set_motors(current_speed, current_speed)
            elif direction == "backward":
                self._set_motors(-current_speed, -current_speed)
            elif direction == "left":
                self._set_motors(0, current_speed)      # 左停，右转
            elif direction == "right":
                self._set_motors(current_speed, 0)      # 左转，右停
            elif direction == "stop":
                self._set_motors(0, 0)
                current_speed = 0.0  # 停止时将当前速度归零

            time.sleep(1 / 60)  # ~60Hz 控制频率

    def stop(self):
        """
        安全停止线程和电机。
        """
        print("Stopping motor controller thread and motors.")
        self.running = False
        self._set_motors(0, 0)
        # 可选：禁用驱动板（低电平）
        self.stby1.off()
        self.stby2.off()
