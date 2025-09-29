# app/motor_controller.py
import threading
import time
from gpiozero import DigitalOutputDevice, PWMOutputDevice
from gpiozero.pins.mock import MockFactory
from .car_state import car_state
from .config import (
    SIMULATION_MODE,
    DRIVER1_STBY,
    DRIVER1_AIN1, DRIVER1_AIN2, DRIVER1_PWMA,  # 左组 PWM 用 DRIVER1_PWMA
    DRIVER1_BIN1, DRIVER1_BIN2, DRIVER1_PWMB,  # 右组 PWM 用 DRIVER1_PWMB
    DRIVER2_STBY,
    DRIVER2_AIN1, DRIVER2_AIN2,
    DRIVER2_BIN1, DRIVER2_BIN2,
    PWM_FREQUENCY,
    TIMEOUT_SECONDS,
    SPEED_STEP
)

if SIMULATION_MODE:
    from gpiozero import Device
    Device.pin_factory = MockFactory()
    print("WARNING: Running in simulation mode. No real GPIO control.")


class MotorController(threading.Thread):
    def __init__(self):
        super().__init__(name="MotorControllerThread", daemon=True)
        self.running = True

        # === 左侧（共用一个 PWM） ===
        self.left_pwm = PWMOutputDevice(DRIVER1_PWMA, frequency=PWM_FREQUENCY, initial_value=0)
        self.lf_in1 = DigitalOutputDevice(DRIVER1_AIN1)
        self.lf_in2 = DigitalOutputDevice(DRIVER1_AIN2)
        self.lb_in1 = DigitalOutputDevice(DRIVER1_BIN1)
        self.lb_in2 = DigitalOutputDevice(DRIVER1_BIN2)

        # === 右侧（共用一个 PWM） ===
        self.right_pwm = PWMOutputDevice(DRIVER1_PWMB, frequency=PWM_FREQUENCY, initial_value=0)
        self.rf_in1 = DigitalOutputDevice(DRIVER2_AIN1)
        self.rf_in2 = DigitalOutputDevice(DRIVER2_AIN2)
        self.rb_in1 = DigitalOutputDevice(DRIVER2_BIN1)
        self.rb_in2 = DigitalOutputDevice(DRIVER2_BIN2)

        # STBY 引脚
        self.stby1 = DigitalOutputDevice(DRIVER1_STBY, initial_value=True)
        self.stby2 = DigitalOutputDevice(DRIVER2_STBY, initial_value=True)

    def _set_wheel(self, name, in1, in2, speed):
        if speed > 0:
            in1.on()
            in2.off()
        elif speed < 0:
            in1.off()
            in2.on()
        else:
            in1.off()
            in2.off()

    def _set_motors(self, left_speed: float, right_speed: float):
        # 左侧方向
        self._set_wheel("LF", self.lf_in1, self.lf_in2, left_speed)
        self._set_wheel("LB", self.lb_in1, self.lb_in2, left_speed)
        self.left_pwm.value = abs(left_speed)

        # 右侧方向
        self._set_wheel("RF", self.rf_in1, self.rf_in2, right_speed)
        self._set_wheel("RB", self.rb_in1, self.rb_in2, right_speed)
        self.right_pwm.value = abs(right_speed)

    def _calculate_speed(self, current_speed, target_speed):
        if abs(current_speed - target_speed) > SPEED_STEP:
            if current_speed < target_speed:
                return current_speed + SPEED_STEP
            else:
                return current_speed - SPEED_STEP
        return target_speed

    def run(self):
        print("Motor controller thread started.")
        current_speed = 0.0
        while self.running:
            state = car_state.get_state()
            # 获取前端传来的左右轮速度
            left_speed = state.get("leftSpeed", 0.0)
            right_speed = state.get("rightSpeed", 0.0)

            # 超时保护
            if time.time() - state["timestamp"] > TIMEOUT_SECONDS:
                left_speed = 0.0
                right_speed = 0.0
                car_state.update_state(leftSpeed=0.0, rightSpeed=0.0)

            self._set_motors(left_speed, right_speed)
            time.sleep(1 / 60)

    def stop(self):
        print("Stopping motor controller thread and motors.")
        self.running = False
        self._set_motors(0, 0)
