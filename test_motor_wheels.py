from raspberry_car_by_controller.motor_controller import MotorController
import time

def test_wheel(name, in1, in2, pwm):
    print(f"Testing {name} forward at 50% speed", flush=True)
    pwm.value = 0.5
    in1.on()
    in2.off()
    time.sleep(2)

    print(f"Testing {name} backward at 50% speed", flush=True)
    pwm.value = 0.5
    in1.off()
    in2.on()
    time.sleep(2)

    print(f"Stopping {name}", flush=True)
    pwm.value = 0
    in1.off()
    in2.off()
    time.sleep(1)

def main():
    motor = MotorController()
    motor.start()
    print("MotorController thread started.", flush=True)

    try:
        # 测试每个轮子
        test_wheel("Left Front", motor.lf_in1, motor.lf_in2, motor.lf_pwm)
        test_wheel("Left Back", motor.lb_in1, motor.lb_in2, motor.lb_pwm)
        test_wheel("Right Front", motor.rf_in1, motor.rf_in2, motor.rf_pwm)
        test_wheel("Right Back", motor.rb_in1, motor.rb_in2, motor.rb_pwm)

        print("All wheels tested.", flush=True)

    finally:
        motor.stop()
        print("MotorController stopped.", flush=True)

if __name__ == "__main__":
    main()
