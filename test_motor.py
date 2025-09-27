
from raspberry_car_by_controller.motor_controller import MotorController
from raspberry_car_by_controller.car_state import car_state
import time

def main():
    # 创建并启动电机控制线程
    motor = MotorController()
    motor.start()
    print("MotorController thread started.", flush=True)

    try:
        # 测试不同方向和速度
        test_commands = [
            {"direction": "forward", "speed": 0.5, "duration": 3},
            {"direction": "backward", "speed": 0.5, "duration": 3},
            {"direction": "left", "speed": 0.5, "duration": 3},
            {"direction": "right", "speed": 0.5, "duration": 3},
            {"direction": "stop", "speed": 0.0, "duration": 2},
        ]

        for cmd in test_commands:
            print(f"Setting state: {cmd}", flush=True)
            car_state.update_state(direction=cmd["direction"], speed=cmd["speed"])
            start = time.time()
            while time.time() - start < cmd["duration"]:
                state = car_state.get_state()
                print(f"[DEBUG] direction={state['direction']}, speed={state['speed']}", flush=True)

                time.sleep(0.5)

    except KeyboardInterrupt:
        print("KeyboardInterrupt: stopping...", flush=True)
    finally:
        motor.stop()
        print("MotorController stopped.", flush=True)

if __name__ == "__main__":
    main()
