import asyncio
import sys
import os
import time

# 将项目根目录添加到 Python 路径，以便导入模块
# 假设 main.py 位于 petcar-ai/car/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入所有客户端组件和配置
try:
    from car.config import CONFIG, SERVER_URL, AUDIO_IN_PATH, MOTOR_PINS, STATUS_LED_PIN
    from car.comm.client import CommManager, ControlCmd
    from car.audio.mic_client import MicClient
    from car.audio.speaker_client import SpeakerClient
    
    # 假设有一个硬件控制模块 (可能需要安装 RPi.GPIO)
    try:
        import RPi.GPIO as GPIO
    except ImportError:
        print("Warning: RPi.GPIO not found. Using mock hardware control.")
        class MockGPIO:
            BCM = 0; OUT = 0; LOW = 0; HIGH = 1; PWM = lambda: None
            def setmode(*args): pass
            def setup(*args): pass
            def output(*args): pass
            def cleanup(*args): pass
            def PWM(*args): 
                class MockPWM:
                    def start(*args): pass
                    def ChangeDutyCycle(*args): pass
                    def stop(*args): pass
                return MockPWM()
        GPIO = MockGPIO()
        
except ImportError as e:
    print(f"FATAL ERROR: Failed to import necessary modules: {e}")
    sys.exit(1)


class CarController:
    """
    PetCar 小车端的主控制器。
    管理通信、音频 I/O 和硬件动作执行。
    """
    
    def __init__(self):
        self.mic_client = MicClient(SERVER_URL + AUDIO_IN_PATH)
        self.speaker_client = SpeakerClient()
        self.comm_manager = CommManager(control_handler=self.execute_action_command)
        self.hardware_initialized = False
        
        self.mic_stream_task: Optional[asyncio.Task] = None
        self.speaker_stream_task: Optional[asyncio.Task] = None
        
        print("\n--- PetCar AI Client Initialized ---")
        
    def _init_hardware(self):
        """初始化树莓派 GPIO 和电机引脚。"""
        try:
            GPIO.setmode(GPIO.BCM)
            
            # 设置电机引脚
            for pin in MOTOR_PINS.values():
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)
                
            # 设置状态 LED
            if STATUS_LED_PIN:
                GPIO.setup(STATUS_LED_PIN, GPIO.OUT)
                GPIO.output(STATUS_LED_PIN, GPIO.LOW)
                
            self.hardware_initialized = True
            print("Hardware (GPIO) initialized successfully.")
        except Exception as e:
            print(f"Hardware initialization failed: {e}. Running in non-motor control mode.")
            GPIO.cleanup() # 确保在失败时清理

    def _cleanup_hardware(self):
        """清理 GPIO 设置。"""
        if self.hardware_initialized:
            GPIO.cleanup()
            print("Hardware (GPIO) cleaned up.")

    async def execute_action_command(self, cmd: ControlCmd):
        """
        接收服务端下发的动作指令，并执行相应的硬件操作。
        
        :param cmd: 包含动作类型和参数的 ControlCmd 对象。
        """
        if cmd.type != 'action':
            print(f"[ACTION] Ignoring non-action command: {cmd.type}")
            return
            
        action_str = cmd.value.strip()
        print(f"[ACTION] Received command: {action_str}")

        # 1. 解析动作指令 (例如: forward(5), turn_left(90))
        try:
            # 简单解析：获取动作名和参数
            action_name = action_str.split('(')[0]
            params = action_str.split('(')[1].rstrip(')').split(',')
            
            # 2. 执行硬件操作
            if action_name == 'forward':
                steps = int(params[0]) if params and params[0] else 1
                self._move_car(direction='forward', duration_steps=steps)
            elif action_name == 'backward':
                steps = int(params[0]) if params and params[0] else 1
                self._move_car(direction='backward', duration_steps=steps)
            elif action_name == 'turn_left':
                degrees = int(params[0]) if params and params[0] else 90
                self._turn_car(direction='left', duration_degrees=degrees)
            elif action_name == 'turn_right':
                degrees = int(params[0]) if params and params[0] else 90
                self._turn_car(direction='right', duration_degrees=degrees)
            elif action_name == 'stop':
                self._stop_car()
            else:
                print(f"[ACTION] Unknown action: {action_name}")

        except Exception as e:
            print(f"[ACTION] Error executing action '{action_str}': {e}")
            self._stop_car()


    def _move_car(self, direction: str, duration_steps: int):
        """模拟/执行小车前进或后退的硬件控制。"""
        if not self.hardware_initialized:
            print(f"Mocking move car: {direction} for {duration_steps} steps.")
            return

        print(f"Moving car: {direction}...")
        
        # 简化硬件控制：仅使用数字输出
        if direction == 'forward':
            GPIO.output(MOTOR_PINS["LEFT_FORWARD"], GPIO.HIGH)
            GPIO.output(MOTOR_PINS["RIGHT_FORWARD"], GPIO.HIGH)
        elif direction == 'backward':
            GPIO.output(MOTOR_PINS["LEFT_BACKWARD"], GPIO.HIGH)
            GPIO.output(MOTOR_PINS["RIGHT_BACKWARD"], GPIO.HIGH)
        
        # 假设 1 步约 0.5 秒
        move_time = duration_steps * 0.5
        asyncio.create_task(self._delay_stop(move_time))
        
    def _turn_car(self, direction: str, duration_degrees: int):
        """模拟/执行小车转向的硬件控制。"""
        if not self.hardware_initialized:
            print(f"Mocking turn car: {direction} for {duration_degrees} degrees.")
            return

        print(f"Turning car: {direction}...")
        
        if direction == 'left':
            # 左轮后退，右轮前进
            GPIO.output(MOTOR_PINS["LEFT_BACKWARD"], GPIO.HIGH)
            GPIO.output(MOTOR_PINS["RIGHT_FORWARD"], GPIO.HIGH)
        elif direction == 'right':
            # 左轮前进，右轮后退
            GPIO.output(MOTOR_PINS["LEFT_FORWARD"], GPIO.HIGH)
            GPIO.output(MOTOR_PINS["RIGHT_BACKWARD"], GPIO.HIGH)

        # 假设 90 度约 0.8 秒
        turn_time = duration_degrees / 90 * 0.8
        asyncio.create_task(self._delay_stop(turn_time))

    def _stop_car(self):
        """停止所有电机。"""
        print("Stopping car.")
        if self.hardware_initialized:
            for pin in MOTOR_PINS.values():
                GPIO.output(pin, GPIO.LOW)
    
    async def _delay_stop(self, delay: float):
        """异步延迟后停止电机。"""
        await asyncio.sleep(delay)
        self._stop_car()

    async def run_client(self):
        """启动小车端的主循环。"""
        self._init_hardware()

        # 1. 连接服务端
        conn = await self.comm_manager.establish_connection()
        if not conn:
            print("Failed to establish connection. Retrying in 5 seconds...")
            await asyncio.sleep(5)
            # 简化处理：这里直接退出，实际应实现重连逻辑
            return

        # 2. 启动音频流 I/O
        self.mic_client.start_stream() 
        self.mic_stream_task = asyncio.create_task(
            self.mic_client.stream_audio_to_server(conn)
        )
        # TTS 语音流接收在 CommManager 的 listener_task 中，通过 SpeakerClient 的 receive_and_play_audio 处理
        # Note: 由于 websockets API 的限制，我们不能在一个连接上同时跑 listen_for_control_commands 和 MicClient.stream_audio_to_server 
        # 并用另一个 Task 来处理二进制消息。这里我们假设 conn.recv() 会在 comm_client 内部处理控制消息，
        # 而 MicClient.stream_audio_to_server 仅负责发送。
        # 实际 websockets 双向流中，conn 既能 send 也能在 async for message in conn 中接收。
        
        # 为了让 SpeakerClient 接收二进制消息 (PCM)，我们需要让 CommManager 的 listener task 
        # 将接收到的二进制消息转发给 SpeakerClient。
        # **为了匹配文档结构和简化，我们重写一个 Task 来处理 Speaker/Control 接收：**
        self.speaker_stream_task = asyncio.create_task(
            self._handle_incoming_messages(conn)
        )
        
        print("PetCar client started. Waiting for user interaction...")
        
        # 3. 保持运行，直到连接关闭或用户中断
        try:
            # 保持主循环运行
            while self.comm_manager.audio_control_client.is_connected:
                await asyncio.sleep(1) 
        except asyncio.CancelledError:
            print("Main loop cancelled.")
        finally:
            await self._shutdown()
            
    async def _handle_incoming_messages(self, conn):
        """替代 CommManager.listen_for_control_commands，处理所有接收消息。"""
        try:
            async for message in conn:
                if isinstance(message, bytes):
                    # PCM 音频流，交给 SpeakerClient 播放
                    # Note: 这里必须用 loop.run_in_executor 来包装阻塞的 stream.write()
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self.speaker_client.stream.write, message)
                elif isinstance(message, str):
                    # JSON 控制/文本消息
                    frame = parse_frame(message)
                    if isinstance(frame, ControlCmd):
                        await self.execute_action_command(frame)
                    # elif isinstance(frame, StatusMsg): ...
        except websockets.exceptions.ConnectionClosed:
            print("Incoming message handler detected connection closed.")
        except Exception as e:
            print(f"Error in incoming message handler: {e}")
        
    async def _shutdown(self):
        """清理资源并优雅退出。"""
        print("\nInitiating client shutdown...")
        
        if self.mic_stream_task:
            self.mic_stream_task.cancel()
        if self.speaker_stream_task:
            self.speaker_stream_task.cancel()
            
        await self.comm_manager.close_connection()
        self.mic_client.stop_stream()
        self.speaker_client.terminate()
        self._cleanup_hardware()
        print("PetCar client shutdown complete.")


if __name__ == '__main__':
    controller = CarController()
    try:
        asyncio.run(controller.run_client())
    except KeyboardInterrupt:
        print("\nClient interrupted by user.")
        # 确保在 KeyboardInterrupt 发生时执行清理
        asyncio.run(controller._shutdown())
    except Exception as e:
        print(f"Unhandled exception in main: {e}")
