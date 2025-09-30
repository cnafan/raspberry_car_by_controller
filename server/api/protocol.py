import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

# 定义 PetCar AI 项目的通信数据协议。
# 所有数据帧都应能被 JSON 序列化和反序列化，
# 以便通过 WebSocket 传输。

# --- 音频传输相关常量 ---
# 音频帧的序列号起始值
INITIAL_SEQ = 0 
# 小车端上传音频的采样率 (ASR 输入)
AUDIO_IN_RATE = 16000 
# 服务端下发音频的采样率 (TTS 输出)
AUDIO_OUT_RATE = 24000 
# 采样精度 (16-bit)
AUDIO_DTYPE = 'int16' 

# --- 数据帧定义 ---

@dataclass
class AudioFrame:
    """
    用于传输音频 PCM 数据的帧结构。
    小车 -> 服务端 (上传麦克风数据)
    服务端 -> 小车 (下发合成语音数据)
    """
    # 序列号，用于保证数据包顺序
    seq: int 
    # PCM 音频数据，通常是 base64 编码的 bytes 或直接的 bytes (依赖 WebSocket 模式)
    # 在 Python 中，我们暂时用 bytes 类型表示，在实际传输时再进行编码处理。
    pcm_data: bytes 
    # 是否是流的最后一帧 (可选)
    is_final: bool = False 

    def to_json(self) -> str:
        """将 AudioFrame 序列化为 JSON 字符串，其中 pcm_data 为 base64 编码。"""
        # Note: 实际应用中，音频流通常直接通过 WebSocket 的 binary 消息传输，
        # 只有控制信息（如 seq, is_final）可能通过 JSON header 传输。
        # 这里的实现是简化版，假设控制信息通过 JSON 传输。
        data = asdict(self)
        # 移除 pcm_data，因为它通常作为二进制消息的 payload 独立传输
        del data['pcm_data'] 
        return json.dumps(data)

@dataclass
class TextFrame:
    """
    用于传输文本信息，如 ASR 结果、LLM 回复或系统消息。
    服务端 -> 小车端
    """
    # 序列号
    seq: int 
    # 文本内容
    text: str 
    # 文本类型 ('asr_interim', 'asr_final', 'llm_interim', 'llm_final', 'system')
    type: str 
    # 是否是流的最后一帧
    is_final: bool = False

    def to_json(self) -> str:
        """将 TextFrame 序列化为 JSON 字符串。"""
        return json.dumps(asdict(self))


@dataclass
class ControlCmd:
    """
    用于传输小车动作指令或系统控制命令。
    服务端 -> 小车端 (小车动作指令)
    小车端 -> 服务端 (连接控制, 心跳等 - 较少用)
    """
    # 命令类型，如 'action', 'heartbeat', 'system_reset'
    type: str 
    # 命令值或参数，例如动作指令 'forward(5)', 'turn_left(90)'
    value: str 
    # 可选的额外参数
    extra: Optional[Dict[str, Any]] = None

    def to_json(self) -> str:
        """将 ControlCmd 序列化为 JSON 字符串。"""
        return json.dumps(asdict(self))


@dataclass
class StatusMsg:
    """
    用于传输状态或错误信息。
    服务端 <-> 小车端 (双向)
    """
    # 状态码，如 200 (OK), 400 (Bad Request), 500 (Internal Error)
    code: int 
    # 消息内容
    message: str 
    # 关联的请求序列号 (可选)
    ref_seq: Optional[int] = None

    def to_json(self) -> str:
        """将 StatusMsg 序列化为 JSON 字符串。"""
        return json.dumps(asdict(self))


def parse_frame(data: str) -> Optional[Any]:
    """
    尝试解析传入的 JSON 字符串为对应的协议对象。
    
    :param data: JSON 格式的字符串。
    :return: 对应的协议 dataclass 实例或 None。
    """
    try:
        data_dict = json.loads(data)
        
        # 简单的类型判断，根据关键字段区分帧类型
        if 'pcm_data' in data_dict:
             # 注意：由于 pcm_data 通常是二进制，这个逻辑需要根据实际WebSocket传输模式调整
             # 假设客户端只发送控制 JSON 头
             return AudioFrame(**data_dict)
        elif 'text' in data_dict and 'type' in data_dict:
            return TextFrame(**data_dict)
        elif 'type' in data_dict and 'value' in data_dict:
            return ControlCmd(**data_dict)
        elif 'code' in data_dict and 'message' in data_dict:
            return StatusMsg(**data_dict)
            
        return None
        
    except json.JSONDecodeError:
        print(f"Protocol Error: Cannot decode JSON data: {data[:50]}...")
        return None
    except TypeError as e:
        print(f"Protocol Error: Missing fields in data ({e}). Data: {data_dict}")
        return None


if __name__ == '__main__':
    # 示例用法
    
    # 1. 模拟小车上传音频帧的控制信息
    audio_cmd = AudioFrame(seq=10, pcm_data=b'', is_final=False)
    audio_json = audio_cmd.to_json()
    print(f"Audio Cmd (JSON): {audio_json}")
    
    # 2. 模拟服务端下发动作指令
    control_cmd = ControlCmd(type='action', value='forward(5)', extra={'speed': 0.5})
    control_json = control_cmd.to_json()
    print(f"Control Cmd (JSON): {control_json}")
    
    # 3. 模拟服务端下发 LLM 文本片段
    text_frame = TextFrame(seq=1, text="好的，", type='llm_interim')
    text_json = text_frame.to_json()
    print(f"Text Frame (JSON): {text_json}")

    # 4. 模拟解析
    parsed_control = parse_frame(control_json)
    print(f"\nParsed ControlCmd: {parsed_control.type}, {parsed_control.value}")
    
    parsed_text = parse_frame(text_json)
    print(f"Parsed TextFrame: {parsed_text.text}, {parsed_text.type}")
