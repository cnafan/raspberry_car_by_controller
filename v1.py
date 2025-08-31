import RPi.GPIO as GPIO
import time
import threading
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

# --- GPIO Pin Definitions ---
# 根据您的GPIO接线方案配置引脚
# Wiring according to the Raspberry Pi GPIO pinout diagram you provided
# BCM Pin numbers
IN1 = 17  # Left Motor Forward
IN2 = 18  # Left Motor Backward
IN3 = 27  # Right Motor Forward
IN4 = 22  # Right Motor Backward
ENA = 12  # Left Motor PWM (Speed)
ENB = 13  # Right Motor PWM (Speed)

# --- Flask and Socket.IO Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key' # Use a random, secure key
socketio = SocketIO(app)

# --- Car Control Variables ---
car_status = {
    'left_speed': 0,
    'right_speed': 0,
    'direction': 'stop'
}
last_command_time = time.time()
STOP_TIMEOUT = 0.5  # Stop the car if no command is received for this duration

# --- GPIO Initialization ---
GPIO.setmode(GPIO.BCM)
GPIO.setup([IN1, IN2, IN3, IN4], GPIO.OUT)
GPIO.setup([ENA, ENB], GPIO.OUT)

# Create PWM instances
pwm_a = GPIO.PWM(ENA, 100) # PWM frequency: 100 Hz
pwm_b = GPIO.PWM(ENB, 100)
pwm_a.start(0)
pwm_b.start(0)

# --- Motor Control Functions ---
def set_motor_speed(motor_pwm, speed):
    """Set the speed of a motor using PWM. Speed is a value from -100 to 100."""
    duty_cycle = abs(speed)
    motor_pwm.ChangeDutyCycle(duty_cycle)

def move_car(left_speed, right_speed):
    """
    Control the direction and speed of the car.
    Speeds are values from -100 (full backward) to 100 (full forward).
    """
    # Left motor direction
    if left_speed > 0:
        GPIO.output(IN1, GPIO.HIGH)
        GPIO.output(IN2, GPIO.LOW)
    elif left_speed < 0:
        GPIO.output(IN1, GPIO.LOW)
        GPIO.output(IN2, GPIO.HIGH)
    else:
        GPIO.output(IN1, GPIO.LOW)
        GPIO.output(IN2, GPIO.LOW)

    # Right motor direction
    if right_speed > 0:
        GPIO.output(IN3, GPIO.HIGH)
        GPIO.output(IN4, GPIO.LOW)
    elif right_speed < 0:
        GPIO.output(IN3, GPIO.LOW)
        GPIO.output(IN4, GPIO.HIGH)
    else:
        GPIO.output(IN3, GPIO.LOW)
        GPIO.output(IN4, GPIO.LOW)

    # Set speeds
    set_motor_speed(pwm_a, left_speed)
    set_motor_speed(pwm_b, right_speed)

    # Update car status dictionary for the frontend
    car_status['left_speed'] = int(abs(left_speed))
    car_status['right_speed'] = int(abs(right_speed))

    if left_speed == 0 and right_speed == 0:
        car_status['direction'] = 'stop'
    elif left_speed > 0 and right_speed > 0:
        car_status['direction'] = 'forward'
    elif left_speed < 0 and right_speed < 0:
        car_status['direction'] = 'backward'
    elif left_speed > 0 and right_speed <= 0:
        car_status['direction'] = 'forward-right' if abs(left_speed) > abs(right_speed) else 'pivot-right'
    elif left_speed <= 0 and right_speed > 0:
        car_status['direction'] = 'forward-left' if abs(right_speed) > abs(left_speed) else 'pivot-left'
    elif left_speed < 0 and right_speed >= 0:
        car_status['direction'] = 'backward-left' if abs(left_speed) > abs(right_speed) else 'pivot-left'
    elif left_speed >= 0 and right_speed < 0:
        car_status['direction'] = 'backward-right' if abs(right_speed) > abs(left_speed) else 'pivot-right'

    # Send status update to all connected clients
    socketio.emit('car_status', car_status)

# --- Scheduled Car Stop Function ---
def check_for_stop():
    """
    A scheduled function to stop the car if no commands are received for a while.
    This is a safety feature to prevent the car from running away if the connection is lost.
    """
    global last_command_time
    while True:
        if time.time() - last_command_time > STOP_TIMEOUT:
            if car_status['left_speed'] != 0 or car_status['right_speed'] != 0:
                print("Connection lost or command timeout. Stopping car.")
                move_car(0, 0)
        time.sleep(STOP_TIMEOUT / 2)

# Start the scheduled stop checker in a separate thread
stop_thread = threading.Thread(target=check_for_stop)
stop_thread.daemon = True
stop_thread.start()

# --- Flask Routes ---
@app.route('/')
def index():
    """Serve the frontend HTML page."""
    return render_template('index.html')

# --- Socket.IO Event Handlers ---
@socketio.on('connect')
def handle_connect():
    print('Client connected:', car_status)
    # Send initial status to the new client
    emit('car_status', car_status)

@socketio.on('command')
def handle_command(data):
    """Handle incoming control commands from the frontend."""
    global last_command_time
    last_command_time = time.time()
    left_speed = data['left_speed']
    right_speed = data['right_speed']
    
    # Ensure speed values are within the valid range
    left_speed = min(100, max(-100, left_speed))
    right_speed = min(100, max(-100, right_speed))
    
    print(f"Received command: left={left_speed}, right={right_speed}")
    move_car(left_speed, right_speed)

# --- Main Execution Block ---
if __name__ == '__main__':
    try:
        # Run the Flask server and Socket.IO on port 5000
        # To make it accessible from other devices on the network, use host='0.0.0.0'
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("Stopping server and cleaning up GPIO.")
    finally:
        pwm_a.stop()
        pwm_b.stop()
        GPIO.cleanup()
