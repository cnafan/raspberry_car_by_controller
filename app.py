import RPi.GPIO as GPIO
import time
import threading
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import pygame

# --- GPIO Pin Definitions (BCM编号) ---
# 根据你提供的树莓派引脚图和接线方案
IN1 = 17  # 左侧电机正转
IN2 = 18  # 左侧电机反转
IN3 = 27  # 右侧电机正转
IN4 = 22  # 右侧电机反转
ENA = 12  # 左侧电机PWM (速度)
ENB = 13  # 右侧电机PWM (速度)

# --- Flask and Socket.IO Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key' # 请修改为一个随机、安全的密钥
socketio = SocketIO(app)

# --- Car Control Variables ---
car_status = {
    'left_speed': 0,
    'right_speed': 0,
    'direction': 'stop'
}
last_command_time = time.time()
STOP_TIMEOUT = 0.5  # 0.5秒没有收到指令，则停止小车

# --- GPIO Initialization ---
GPIO.setmode(GPIO.BCM)
GPIO.setup([IN1, IN2, IN3, IN4], GPIO.OUT)
GPIO.setup([ENA, ENB], GPIO.OUT)

pwm_a = GPIO.PWM(ENA, 100) # PWM频率: 100 Hz
pwm_b = GPIO.PWM(ENB, 100)
pwm_a.start(0)
pwm_b.start(0)

# --- USB Gamepad Initialization ---
joystick = None
try:
    pygame.init()
    pygame.joystick.init()
    if pygame.joystick.get_count() > 0:
        joystick = pygame.joystick.Joystick(0)
        joystick.init()
        print(f"Detected Joystick: {joystick.get_name()}")
    else:
        print("No joystick detected. Using web interface control only.")
except Exception as e:
    print(f"Error initializing joystick: {e}")
    joystick = None

# --- Motor Control Functions ---
def set_motor_speed(motor_pwm, speed):
    """设置电机速度，速度值范围为 -100 到 100。"""
    duty_cycle = abs(speed)
    motor_pwm.ChangeDutyCycle(duty_cycle)

def move_car(left_speed, right_speed):
    """
    控制小车的方向和速度。
    速度值为 -100 (全速后退) 到 100 (全速前进)。
    """
    # 左侧电机方向
    if left_speed > 0:
        GPIO.output(IN1, GPIO.HIGH)
        GPIO.output(IN2, GPIO.LOW)
    elif left_speed < 0:
        GPIO.output(IN1, GPIO.LOW)
        GPIO.output(IN2, GPIO.HIGH)
    else:
        GPIO.output(IN1, GPIO.LOW)
        GPIO.output(IN2, GPIO.LOW)

    # 右侧电机方向
    if right_speed > 0:
        GPIO.output(IN3, GPIO.HIGH)
        GPIO.output(IN4, GPIO.LOW)
    elif right_speed < 0:
        GPIO.output(IN3, GPIO.LOW)
        GPIO.output(IN4, GPIO.HIGH)
    else:
        GPIO.output(IN3, GPIO.LOW)
        GPIO.output(IN4, GPIO.LOW)

    # 设置速度
    set_motor_speed(pwm_a, left_speed)
    set_motor_speed(pwm_b, right_speed)

    # 更新小车状态字典并发送给前端
    car_status['left_speed'] = int(abs(left_speed))
    car_status['right_speed'] = int(abs(right_speed))

    if left_speed == 0 and right_speed == 0:
        car_status['direction'] = 'stop'
    elif left_speed > 0 and right_speed > 0:
        car_status['direction'] = 'forward'
    elif left_speed < 0 and right_speed < 0:
        car_status['direction'] = 'backward'
    elif abs(left_speed) > abs(right_speed):
        car_status['direction'] = 'forward-right' if left_speed > 0 else 'backward-left'
    elif abs(right_speed) > abs(left_speed):
        car_status['direction'] = 'forward-left' if right_speed > 0 else 'backward-right'
    elif left_speed > 0 and right_speed < 0:
        car_status['direction'] = 'pivot-right'
    elif left_speed < 0 and right_speed > 0:
        car_status['direction'] = 'pivot-left'

    socketio.emit('car_status', car_status)

# --- Scheduled Car Stop Function ---
def check_for_stop():
    """在连接或指令超时时停止小车，以确保安全。"""
    global last_command_time
    while True:
        if time.time() - last_command_time > STOP_TIMEOUT:
            if car_status['left_speed'] != 0 or car_status['right_speed'] != 0:
                print("Connection lost or command timeout. Stopping car.")
                move_car(0, 0)
        time.sleep(STOP_TIMEOUT / 2)

# --- Joystick Control Thread ---
def joystick_thread():
    """在单独的线程中处理手柄事件。"""
    global last_command_time
    if joystick is None:
        return

    while True:
        try:
            pygame.event.pump()
            x_axis = joystick.get_axis(0) # 通常是左摇杆的X轴
            y_axis = joystick.get_axis(1) # 通常是左摇杆的Y轴

            # 将摇杆值 (-1 to 1) 转换为速度值 (-100 to 100)
            left_speed = -int(y_axis * 100)
            right_speed = -int(y_axis * 100)
            turn_speed = int(x_axis * 100)

            final_left_speed = left_speed + turn_speed
            final_right_speed = right_speed - turn_speed
            
            # 限制速度在有效范围内
            final_left_speed = min(100, max(-100, final_left_speed))
            final_right_speed = min(100, max(-100, final_right_speed))
            
            # 如果摇杆有明显移动，则发送指令
            if abs(y_axis) > 0.1 or abs(x_axis) > 0.1:
                last_command_time = time.time()
                move_car(final_left_speed, final_right_speed)
            elif abs(y_axis) < 0.1 and abs(x_axis) < 0.1 and (car_status['left_speed'] != 0 or car_status['right_speed'] != 0):
                # 如果摇杆回到原位，且小车还在动，则发送停止指令
                last_command_time = time.time()
                move_car(0, 0)
        except Exception as e:
            print(f"Joystick error: {e}")
            break
        time.sleep(0.05) # 每50毫秒轮询一次

# --- Flask Routes ---
@app.route('/')
def index():
    """提供网页界面。"""
    return render_template('index.html')

# --- Socket.IO Event Handlers ---
@socketio.on('connect')
def handle_connect():
    print('Client connected:', car_status)
    emit('car_status', car_status)

@socketio.on('command')
def handle_command(data):
    """处理来自前端的控制指令。"""
    global last_command_time
    last_command_time = time.time()
    left_speed = data['left_speed']
    right_speed = data['right_speed']
    
    left_speed = min(100, max(-100, left_speed))
    right_speed = min(100, max(-100, right_speed))
    
    print(f"Web command: left={left_speed}, right={right_speed}")
    move_car(left_speed, right_speed)

# --- Main Execution Block ---
if __name__ == '__main__':
    try:
        # 启动安全停车线程
        stop_thread = threading.Thread(target=check_for_stop)
        stop_thread.daemon = True
        stop_thread.start()

        # 启动手柄控制线程
        if joystick is not None:
            joystick_control_thread = threading.Thread(target=joystick_thread)
            joystick_control_thread.daemon = True
            joystick_control_thread.start()

        # 运行Flask服务器和Socket.IO
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("Stopping server and cleaning up GPIO.")
    finally:
        pwm_a.stop()
        pwm_b.stop()
        GPIO.cleanup()
        pygame.quit()
